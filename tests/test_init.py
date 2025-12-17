"""Test the WiFi Geolocation integration."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest

from custom_components.wifi_geolocation.const import (
    ATTR_FORCE,
    DOMAIN,
    SERVICE_GEOLOCATE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import (
    GOOGLE_RESPONSE_1,
    GOOGLE_RESPONSE_2,
    WIFI_APS_1,
    WIFI_APS_2,
)


async def test_setup_unload_entry(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test setting up and unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify service is registered
    assert hass.services.has_service(DOMAIN, SERVICE_GEOLOCATE)

    # Test unload
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Service should still exist (registered in async_setup, not async_setup_entry)
    assert hass.services.has_service(DOMAIN, SERVICE_GEOLOCATE)


async def test_geolocate_service_success(
    hass: HomeAssistant, mock_config_entry, mock_aiohttp_session
) -> None:
    """Test geolocate service call success."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Create a device tracker entity with wifi_access_points attribute
    hass.states.async_set(
        "device_tracker.test_device",
        "home",
        {"wifi_access_points": WIFI_APS_1},
    )

    # Mock successful Google API response
    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value=GOOGLE_RESPONSE_1)
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response

    # Mock the entity component
    component = AsyncMock()
    entity = AsyncMock()
    entity.set_geocoded_location = AsyncMock()
    component.get_entity.return_value = entity
    hass.data.setdefault("entity_components", {})["device_tracker"] = component

    # Call the service
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GEOLOCATE,
        {ATTR_ENTITY_ID: "device_tracker.test_device", ATTR_FORCE: False},
        blocking=True,
    )

    # Verify entity was updated
    entity.set_geocoded_location.assert_called_once_with(
        37.7749, -122.4194, 25.0
    )


async def test_geolocate_service_entity_not_found(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test geolocate service with non-existent entity."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="Entity .* not found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GEOLOCATE,
            {ATTR_ENTITY_ID: "device_tracker.nonexistent", ATTR_FORCE: False},
            blocking=True,
        )


async def test_geolocate_service_no_wifi_attribute(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test geolocate service with entity missing wifi_access_points."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Create entity without wifi_access_points
    hass.states.async_set("device_tracker.test_device", "home", {})

    with pytest.raises(
        ServiceValidationError, match="No 'wifi_access_points' attribute"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GEOLOCATE,
            {ATTR_ENTITY_ID: "device_tracker.test_device", ATTR_FORCE: False},
            blocking=True,
        )


async def test_geolocate_caching(
    hass: HomeAssistant, mock_config_entry, mock_aiohttp_session
) -> None:
    """Test that caching prevents duplicate API calls."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Create entity with wifi_access_points
    hass.states.async_set(
        "device_tracker.test_device",
        "home",
        {"wifi_access_points": WIFI_APS_1},
    )

    # Mock successful Google API response
    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value=GOOGLE_RESPONSE_1)
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response

    # Mock the entity component
    component = AsyncMock()
    entity = AsyncMock()
    entity.set_geocoded_location = AsyncMock()
    component.get_entity.return_value = entity
    hass.data.setdefault("entity_components", {})["device_tracker"] = component

    # First call - should hit API
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GEOLOCATE,
        {ATTR_ENTITY_ID: "device_tracker.test_device", ATTR_FORCE: False},
        blocking=True,
    )

    assert mock_aiohttp_session.post.call_count == 1

    # Second call with same BSSIDs - should use cache
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GEOLOCATE,
        {ATTR_ENTITY_ID: "device_tracker.test_device", ATTR_FORCE: False},
        blocking=True,
    )

    # API should not be called again
    assert mock_aiohttp_session.post.call_count == 1

    # Third call with force=True - should bypass cache
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GEOLOCATE,
        {ATTR_ENTITY_ID: "device_tracker.test_device", ATTR_FORCE: True},
        blocking=True,
    )

    # API should be called again
    assert mock_aiohttp_session.post.call_count == 2


async def test_geolocate_different_bssids(
    hass: HomeAssistant, mock_config_entry, mock_aiohttp_session
) -> None:
    """Test that different BSSIDs trigger new API calls."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Mock the entity component
    component = AsyncMock()
    entity = AsyncMock()
    entity.set_geocoded_location = AsyncMock()
    component.get_entity.return_value = entity
    hass.data.setdefault("entity_components", {})["device_tracker"] = component

    # First call with WIFI_APS_1
    hass.states.async_set(
        "device_tracker.test_device",
        "home",
        {"wifi_access_points": WIFI_APS_1},
    )

    response1 = AsyncMock()
    response1.status = 200
    response1.json = AsyncMock(return_value=GOOGLE_RESPONSE_1)
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_GEOLOCATE,
        {ATTR_ENTITY_ID: "device_tracker.test_device", ATTR_FORCE: False},
        blocking=True,
    )

    assert mock_aiohttp_session.post.call_count == 1

    # Second call with WIFI_APS_2 (different BSSIDs)
    hass.states.async_set(
        "device_tracker.test_device",
        "home",
        {"wifi_access_points": WIFI_APS_2},
    )

    response2 = AsyncMock()
    response2.status = 200
    response2.json = AsyncMock(return_value=GOOGLE_RESPONSE_2)
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response2

    await hass.services.async_call(
        DOMAIN,
        SERVICE_GEOLOCATE,
        {ATTR_ENTITY_ID: "device_tracker.test_device", ATTR_FORCE: False},
        blocking=True,
    )

    # API should be called again for different BSSIDs
    assert mock_aiohttp_session.post.call_count == 2


async def test_geolocate_api_error(
    hass: HomeAssistant, mock_config_entry, mock_aiohttp_session
) -> None:
    """Test handling of API errors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        "device_tracker.test_device",
        "home",
        {"wifi_access_points": WIFI_APS_1},
    )

    # Mock API error response
    response = AsyncMock()
    response.status = 500
    response.text = AsyncMock(return_value="Internal Server Error")
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response

    # Mock the entity component
    component = AsyncMock()
    entity = AsyncMock()
    component.get_entity.return_value = entity
    hass.data.setdefault("entity_components", {})["device_tracker"] = component

    with pytest.raises(HomeAssistantError, match="Google API error"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GEOLOCATE,
            {ATTR_ENTITY_ID: "device_tracker.test_device", ATTR_FORCE: False},
            blocking=True,
        )


async def test_geolocate_connection_error(
    hass: HomeAssistant, mock_config_entry, mock_aiohttp_session
) -> None:
    """Test handling of connection errors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        "device_tracker.test_device",
        "home",
        {"wifi_access_points": WIFI_APS_1},
    )

    # Mock connection error
    mock_aiohttp_session.post.side_effect = ClientError("Connection failed")

    # Mock the entity component
    component = AsyncMock()
    entity = AsyncMock()
    component.get_entity.return_value = entity
    hass.data.setdefault("entity_components", {})["device_tracker"] = component

    with pytest.raises(HomeAssistantError, match="Failed to call Google API"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GEOLOCATE,
            {ATTR_ENTITY_ID: "device_tracker.test_device", ATTR_FORCE: False},
            blocking=True,
        )


async def test_state_change_listener(
    hass: HomeAssistant, mock_config_entry, mock_aiohttp_session
) -> None:
    """Test automatic geolocation on state changes."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Mock successful Google API response
    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value=GOOGLE_RESPONSE_1)
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response

    # Mock the entity component
    component = AsyncMock()
    entity = AsyncMock()
    entity.set_geocoded_location = AsyncMock()
    component.get_entity.return_value = entity
    hass.data.setdefault("entity_components", {})["device_tracker"] = component

    # Create entity with wifi_access_points
    hass.states.async_set(
        "device_tracker.test_device",
        "home",
        {"wifi_access_points": WIFI_APS_1},
    )
    await hass.async_block_till_done()

    # State change should trigger automatic geolocation
    assert mock_aiohttp_session.post.call_count == 1

    # Update with same wifi_access_points - should not trigger
    hass.states.async_set(
        "device_tracker.test_device",
        "home",
        {"wifi_access_points": WIFI_APS_1},
    )
    await hass.async_block_till_done()

    # Should not call API again (same BSSIDs)
    assert mock_aiohttp_session.post.call_count == 1

    # Update with different wifi_access_points - should trigger
    response2 = AsyncMock()
    response2.status = 200
    response2.json = AsyncMock(return_value=GOOGLE_RESPONSE_2)
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response2

    hass.states.async_set(
        "device_tracker.test_device",
        "home",
        {"wifi_access_points": WIFI_APS_2},
    )
    await hass.async_block_till_done()

    # Should call API for new BSSIDs
    assert mock_aiohttp_session.post.call_count == 2


async def test_geolocate_no_location_in_response(
    hass: HomeAssistant, mock_config_entry, mock_aiohttp_session
) -> None:
    """Test handling of API response without location."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        "device_tracker.test_device",
        "home",
        {"wifi_access_points": WIFI_APS_1},
    )

    # Mock API response without location
    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value={})
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response

    # Mock the entity component
    component = AsyncMock()
    entity = AsyncMock()
    component.get_entity.return_value = entity
    hass.data.setdefault("entity_components", {})["device_tracker"] = component

    with pytest.raises(HomeAssistantError, match="No location in Google API response"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GEOLOCATE,
            {ATTR_ENTITY_ID: "device_tracker.test_device", ATTR_FORCE: False},
            blocking=True,
        )
