"""Config flow for WiFi Geolocation integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError, ClientTimeout
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_GOOGLE_GEOLOCATION_API_KEY, DOMAIN, GOOGLE_GEOLOCATION_API_URL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GOOGLE_GEOLOCATION_API_KEY): str,
    }
)


async def validate_api_key(hass: HomeAssistant, api_key: str) -> dict[str, Any]:
    """Validate the Google API key by making a test request.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    url = f"{GOOGLE_GEOLOCATION_API_URL}?key={api_key}"

    # Test with an empty request (no WiFi access points)
    # Google will return an error, but we can verify the API key is valid
    try:
        async with session.post(
            url,
            json={},
            timeout=ClientTimeout(total=10),
        ) as response:
            # API key is valid if we get any response (even error responses)
            # Invalid API key returns 400 with specific error
            if response.status == 400:
                error_data = await response.json()
                error_message = error_data.get("error", {}).get("message", "")

                # Check for API key errors
                if "API key" in error_message or "invalid" in error_message.lower():
                    raise InvalidAuth(f"Invalid API key: {error_message}")

                # Other 400 errors are fine (e.g., missing wifi data)
                # This means the API key itself is valid
                return {"title": "WiFi Geolocation"}

            if response.status == 403:
                error_text = await response.text()
                raise InvalidAuth(f"API key authentication failed: {error_text}")

            # Any other response means API key is working
            return {"title": "WiFi Geolocation"}

    except ClientError as err:
        raise CannotConnect(f"Failed to connect to Google API: {err}") from err


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class WiFiGeolocationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WiFi Geolocation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Only allow one instance of this integration
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            try:
                info = await validate_api_key(self.hass, user_input[CONF_GOOGLE_GEOLOCATION_API_KEY])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth upon API key failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_api_key(self.hass, user_input[CONF_GOOGLE_GEOLOCATION_API_KEY])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"error": "API key authentication failed"},
        )
