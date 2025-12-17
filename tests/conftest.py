"""Define fixtures for WiFi Geolocation tests."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wifi_geolocation.const import (
    CONF_GOOGLE_GEOLOCATION_API_KEY,
    DOMAIN,
)

API_KEY = "test_google_geolocation_api_key"

# Test WiFi access points data
WIFI_APS_1 = [
    {"macAddress": "AA:BB:CC:DD:EE:01", "signalStrength": -45},
    {"macAddress": "AA:BB:CC:DD:EE:02", "signalStrength": -67},
    {"macAddress": "AA:BB:CC:DD:EE:03", "signalStrength": -72},
]

WIFI_APS_2 = [
    {"macAddress": "11:22:33:44:55:66", "signalStrength": -50},
    {"macAddress": "AA:BB:CC:DD:EE:02", "signalStrength": -60},
]

# Google Geolocation API response for WIFI_APS_1
GOOGLE_RESPONSE_1 = {
    "location": {"lat": 37.7749, "lng": -122.4194},
    "accuracy": 25.0,
}

# Google Geolocation API response for WIFI_APS_2
GOOGLE_RESPONSE_2 = {
    "location": {"lat": 51.5074, "lng": -0.1278},
    "accuracy": 30.0,
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="WiFi Geolocation",
        data={
            CONF_GOOGLE_GEOLOCATION_API_KEY: API_KEY,
        },
    )


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp client session."""
    with patch(
        "custom_components.wifi_geolocation.config_flow.async_get_clientsession"
    ) as mock_get_session, patch(
        "custom_components.wifi_geolocation.async_get_clientsession"
    ) as mock_get_session_init:
        session = AsyncMock()
        mock_get_session.return_value = session
        mock_get_session_init.return_value = session
        yield session
