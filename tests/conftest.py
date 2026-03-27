"""Shared fixtures for Turn Touch tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak import BleakClient

from custom_components.turntouch.coordinator import TurnTouchCoordinator

# Required by pytest-homeassistant-custom-component
pytest_plugins = ["pytest_homeassistant_custom_component"]

ADDRESS = "AA:BB:CC:DD:EE:FF"
DEVICE_NAME = "Turn Touch Remote"


@pytest.fixture
def mock_hass():
    """Return a minimal mock HomeAssistant instance."""
    return MagicMock()


@pytest.fixture
def mock_ble_device():
    """Return a mock BLEDevice."""
    device = MagicMock()
    device.address = ADDRESS
    device.name = DEVICE_NAME
    return device


@pytest.fixture
def mock_bleak_client():
    """Return a mock BleakClient that is connected."""
    client = MagicMock(spec=BleakClient)
    client.is_connected = True
    client.start_notify = AsyncMock()
    client.stop_notify = AsyncMock()
    client.read_gatt_char = AsyncMock(return_value=bytearray([85]))
    client.disconnect = AsyncMock()
    return client


@pytest.fixture
def coordinator(mock_hass):
    """Return a TurnTouchCoordinator with a mock hass."""
    return TurnTouchCoordinator(mock_hass, ADDRESS, DEVICE_NAME)


@pytest.fixture
def connected_coordinator(coordinator, mock_ble_device, mock_bleak_client):
    """Return a coordinator that has already completed _async_connect."""
    coordinator._client = mock_bleak_client
    coordinator._reconnect_delay = 5
    return coordinator
