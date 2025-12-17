"""WiFi Geolocation integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError, ClientTimeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import (
    ATTR_FORCE,
    CONF_GOOGLE_GEOLOCATION_API_KEY,
    DOMAIN,
    GOOGLE_GEOLOCATION_API_URL,
    SERVICE_GEOLOCATE,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

GEOLOCATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_FORCE, default=False): cv.boolean,
    }
)


def bssid_set_to_key(bssids: frozenset[str]) -> str:
    """Convert BSSID frozenset to cache key string."""
    return "|".join(sorted(bssids))


def key_to_bssid_set(key: str) -> frozenset[str]:
    """Convert cache key string back to BSSID frozenset."""
    return frozenset(key.split("|"))


async def _call_geolocation_api(
    hass: HomeAssistant,
    api_key: str,
    entity_id: str,
    wifi_aps: list,
    current_bssids: frozenset[str],
) -> tuple[float, float, float]:
    """Call Google Geolocation API and return (latitude, longitude, accuracy)."""
    _LOGGER.info(
        "Calling Google API for %s using %d Wi-Fi access points",
        entity_id,
        len(wifi_aps),
    )

    session = async_get_clientsession(hass)
    url = f"{GOOGLE_GEOLOCATION_API_URL}?key={api_key}"

    try:
        async with session.post(
            url,
            json={"wifiAccessPoints": wifi_aps},
            timeout=ClientTimeout(total=10),
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise HomeAssistantError(
                    f"Google API error ({response.status}): {error_text}"
                )

            result = await response.json()

    except ClientError as err:
        raise HomeAssistantError(f"Failed to call Google API: {err}") from err

    # Extract location
    location = result.get("location")
    if not location:
        raise HomeAssistantError("No location in Google API response")

    latitude = location["lat"]
    longitude = location["lng"]
    accuracy = result.get("accuracy", 0)

    _LOGGER.warning(
        "========================================\n"
        "✓ GEOCODING SUCCESS!\n"
        "  Entity: %s\n"
        "  Latitude: %s\n"
        "  Longitude: %s\n"
        "  Accuracy: %s meters\n"
        "  Wi-Fi APs used: %d\n"
        "  BSSIDs: %s\n"
        "========================================",
        entity_id,
        latitude,
        longitude,
        accuracy,
        len(wifi_aps),
        len(current_bssids),
    )

    return latitude, longitude, accuracy


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WiFi Geolocation from a config entry."""

    # Initialize storage for persistent location cache
    store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    # Load cached locations from storage (survives restarts)
    stored_data = await store.async_load()
    location_cache = stored_data.get("location_cache", {}) if stored_data else {}

    # Store config entry and data in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "store": store,
        "location_cache": location_cache,
        "last_bssids": {},
        "api_key": entry.data[CONF_GOOGLE_GEOLOCATION_API_KEY],
    }

    async def async_geolocate(call: ServiceCall) -> None:
        """Geolocate device using Wi-Fi access points from entity attributes."""
        entity_id = call.data[ATTR_ENTITY_ID]
        force = call.data[ATTR_FORCE]

        # Get the entity state
        state = hass.states.get(entity_id)
        if not state:
            raise ServiceValidationError(f"Entity {entity_id} not found")

        # Get Wi-Fi access points from attributes
        wifi_aps = state.attributes.get("wifi_access_points")
        if not wifi_aps:
            raise ServiceValidationError(
                f"No 'wifi_access_points' attribute found for {entity_id}. "
                "Entity must have wifi_access_points in Google Geolocation API format."
            )

        # Get config entry data
        entry_data = hass.data[DOMAIN][entry.entry_id]
        api_key = entry_data["api_key"]

        # Extract current BSSIDs (MAC addresses) from Wi-Fi access points
        # Use frozenset for order-independent comparison and hashing
        current_bssids = frozenset(
            ap.get("macAddress") for ap in wifi_aps if ap.get("macAddress")
        )
        cache_key = bssid_set_to_key(current_bssids)

        # Get cache references from entry data
        location_cache = entry_data["location_cache"]
        last_bssids = entry_data["last_bssids"]
        store = entry_data["store"]

        # Check if we have this location cached (unless force=True)
        if not force and cache_key in location_cache:
            cached = location_cache[cache_key]
            _LOGGER.info(
                "Using cached location for %s (%d BSSIDs) - "
                "lat: %s, lon: %s, accuracy: %s meters",
                entity_id,
                len(current_bssids),
                cached["latitude"],
                cached["longitude"],
                cached["accuracy"],
            )
            latitude = cached["latitude"]
            longitude = cached["longitude"]
            accuracy = cached["accuracy"]

        # Check if BSSIDs have changed since last call (unless force=True)
        elif not force and entity_id in last_bssids:
            if current_bssids == last_bssids[entity_id]:
                _LOGGER.info(
                    "Skipping geolocation for %s - BSSIDs unchanged (%d access points). "
                    "Use force=true to override",
                    entity_id,
                    len(current_bssids),
                )
                return
            # BSSIDs changed, need to call API
            latitude, longitude, accuracy = await _call_geolocation_api(
                hass, api_key, entity_id, wifi_aps, current_bssids
            )
        else:
            # Force=True or first time seeing this entity
            latitude, longitude, accuracy = await _call_geolocation_api(
                hass, api_key, entity_id, wifi_aps, current_bssids
            )

        # If we called the API (not using cache), store the result
        if cache_key not in location_cache or force:
            location_cache[cache_key] = {
                "latitude": latitude,
                "longitude": longitude,
                "accuracy": accuracy,
            }
            # Persist to disk
            await store.async_save({"location_cache": location_cache})
            _LOGGER.debug("Saved location to cache: %s", cache_key)

        # Store current BSSIDs for next comparison
        last_bssids[entity_id] = current_bssids

        # Find the actual device tracker entity and update it
        # Get the device_tracker component
        component = hass.data.get("entity_components", {}).get("device_tracker")
        if not component:
            raise ServiceValidationError("Device tracker component not loaded")

        # Find the entity object
        entity_obj = component.get_entity(entity_id)
        if not entity_obj:
            raise ServiceValidationError(
                f"Could not find entity object for {entity_id}. "
                "Make sure the entity is fully loaded."
            )

        # Check if the entity has the set_geocoded_location method
        if not hasattr(entity_obj, "set_geocoded_location"):
            raise ServiceValidationError(
                f"Entity {entity_id} does not support geocoded location updates. "
                "Only TTN device trackers with Wi-Fi scan data support this."
            )

        # Update the entity with geocoded location
        entity_obj.set_geocoded_location(latitude, longitude, accuracy)

        _LOGGER.info("✓ Updated %s with geocoded location", entity_id)

    # Register service
    hass.services.async_register(
        DOMAIN,
        SERVICE_GEOLOCATE,
        async_geolocate,
        schema=GEOLOCATE_SCHEMA,
    )

    @callback
    def async_state_changed_listener(event: Event) -> None:
        """Listen for device tracker state changes with wifi_access_points."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        # Only process device_tracker entities
        if not entity_id or not entity_id.startswith("device_tracker."):
            return

        # Check if entity has wifi_access_points attribute
        if not new_state or "wifi_access_points" not in new_state.attributes:
            return

        # Get the wifi access points
        new_wifi_aps = new_state.attributes.get("wifi_access_points")
        old_wifi_aps = old_state.attributes.get("wifi_access_points") if old_state else None

        # Check if wifi_access_points actually changed
        if old_wifi_aps is not None:
            # Compare by extracting MAC addresses
            new_macs = {ap.get("macAddress") for ap in new_wifi_aps} if new_wifi_aps else set()
            old_macs = {ap.get("macAddress") for ap in old_wifi_aps} if old_wifi_aps else set()

            if new_macs == old_macs:
                return

        # Call geolocation service automatically
        _LOGGER.info(
            "Auto-triggering geolocation for %s (wifi_access_points changed)",
            entity_id
        )
        hass.async_create_task(
            hass.services.async_call(
                DOMAIN,
                SERVICE_GEOLOCATE,
                {ATTR_ENTITY_ID: entity_id, ATTR_FORCE: False},
            )
        )

    # Set up automatic state change listener for all device trackers
    # Listen directly to state_changed events on the event bus
    # Store the unsubscribe callback for cleanup
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_STATE_CHANGED, async_state_changed_listener)  # type: ignore[arg-type]
    )

    _LOGGER.info(
        "WiFi Geolocation loaded. "
        "Automatically geolocating device trackers with Wi-Fi data"
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Remove the config entry data
    hass.data[DOMAIN].pop(entry.entry_id)

    return True
