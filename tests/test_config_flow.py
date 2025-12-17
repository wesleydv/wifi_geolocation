"""Test the WiFi Geolocation config flow."""

from unittest.mock import AsyncMock

from aiohttp import ClientError

from custom_components.wifi_geolocation.const import (
    CONF_GOOGLE_GEOLOCATION_API_KEY,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import API_KEY


async def test_user_flow_success(hass: HomeAssistant, mock_aiohttp_session) -> None:
    """Test successful user flow."""
    # Mock successful API response (400 with non-auth error means API key is valid)
    response = AsyncMock()
    response.status = 400
    response.json = AsyncMock(return_value={"error": {"message": "Invalid request"}})
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test form submission
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_GOOGLE_GEOLOCATION_API_KEY: API_KEY},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "WiFi Geolocation"
    assert result["data"] == {CONF_GOOGLE_GEOLOCATION_API_KEY: API_KEY}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry, mock_aiohttp_session
) -> None:
    """Test already configured."""
    mock_config_entry.add_to_hass(hass)

    # Mock successful API response
    response = AsyncMock()
    response.status = 400
    response.json = AsyncMock(return_value={"error": {"message": "Invalid request"}})
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_GOOGLE_GEOLOCATION_API_KEY: API_KEY},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, mock_aiohttp_session
) -> None:
    """Test invalid auth error handling."""
    # Mock invalid API key response
    response = AsyncMock()
    response.status = 400
    response.json = AsyncMock(return_value={"error": {"message": "API key not valid"}})
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_GOOGLE_GEOLOCATION_API_KEY: "invalid_key"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_forbidden(hass: HomeAssistant, mock_aiohttp_session) -> None:
    """Test 403 forbidden error handling."""
    # Mock 403 response
    response = AsyncMock()
    response.status = 403
    response.text = AsyncMock(return_value="Forbidden")
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_GOOGLE_GEOLOCATION_API_KEY: API_KEY},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_aiohttp_session
) -> None:
    """Test connection error handling."""
    # Mock connection error
    mock_aiohttp_session.post.side_effect = ClientError("Connection failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_GOOGLE_GEOLOCATION_API_KEY: API_KEY},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry, mock_aiohttp_session
) -> None:
    """Test reauth flow."""
    mock_config_entry.add_to_hass(hass)

    # Mock successful API response
    response = AsyncMock()
    response.status = 400
    response.json = AsyncMock(return_value={"error": {"message": "Invalid request"}})
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_GOOGLE_GEOLOCATION_API_KEY: "new_api_key"},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, mock_config_entry, mock_aiohttp_session
) -> None:
    """Test reauth flow with invalid auth."""
    mock_config_entry.add_to_hass(hass)

    # Mock invalid API key response
    response = AsyncMock()
    response.status = 400
    response.json = AsyncMock(return_value={"error": {"message": "API key not valid"}})
    mock_aiohttp_session.post.return_value.__aenter__.return_value = response

    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_GOOGLE_GEOLOCATION_API_KEY: "invalid_key"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
