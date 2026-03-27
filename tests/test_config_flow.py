"""Tests for Turn Touch config flow."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResultType

from custom_components.turntouch.const import DOMAIN, SERVICE_UUID

from .conftest import ADDRESS, DEVICE_NAME


def _make_service_info(address: str, name: str, include_service_uuid: bool = True):
    """Build a minimal BluetoothServiceInfoBleak-like mock."""
    info = MagicMock()
    info.address = address
    info.name = name
    info.service_uuids = [SERVICE_UUID] if include_service_uuid else []
    return info


# ---------------------------------------------------------------------------
# Bluetooth auto-discovery flow
# ---------------------------------------------------------------------------


async def test_bluetooth_step_shows_confirm_form(hass):
    """async_step_bluetooth shows a confirmation form."""
    discovery = _make_service_info(ADDRESS, DEVICE_NAME)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=discovery,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"


async def test_bluetooth_confirm_creates_entry(hass):
    """Confirming bluetooth discovery creates a config entry."""
    discovery = _make_service_info(ADDRESS, DEVICE_NAME)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=discovery,
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == ADDRESS
    assert result["data"][CONF_NAME] == DEVICE_NAME


async def test_bluetooth_already_configured_aborts(hass):
    """A second discovery for the same device aborts with already_configured."""
    discovery = _make_service_info(ADDRESS, DEVICE_NAME)

    # First setup
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=discovery,
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    # Second attempt for the same address
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=discovery,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Manual user flow
# ---------------------------------------------------------------------------


async def test_user_step_no_devices_aborts(hass):
    """When no Turn Touch devices are discovered, the flow aborts."""
    with patch(
        "custom_components.turntouch.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_shows_device_list(hass):
    """When devices are found, a form with a device selector is shown."""
    service_info = _make_service_info(ADDRESS, DEVICE_NAME)

    with patch(
        "custom_components.turntouch.config_flow.async_discovered_service_info",
        return_value=[service_info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_ignores_non_turntouch_devices(hass):
    """Devices without the Turn Touch service UUID are not shown."""
    other_device = _make_service_info("11:22:33:44:55:66", "SomeOtherDevice", include_service_uuid=False)

    with patch(
        "custom_components.turntouch.config_flow.async_discovered_service_info",
        return_value=[other_device],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_creates_entry_on_selection(hass):
    """Selecting a device from the list creates a config entry."""
    service_info = _make_service_info(ADDRESS, DEVICE_NAME)

    with patch(
        "custom_components.turntouch.config_flow.async_discovered_service_info",
        return_value=[service_info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device": ADDRESS}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == ADDRESS
    assert result["data"][CONF_NAME] == DEVICE_NAME


async def test_user_step_uses_address_as_name_when_no_name(hass):
    """A device with no name uses its address as the entry title."""
    service_info = _make_service_info(ADDRESS, name="")
    service_info.name = None  # simulate missing name

    with patch(
        "custom_components.turntouch.config_flow.async_discovered_service_info",
        return_value=[service_info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device": ADDRESS}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_NAME] == ADDRESS
