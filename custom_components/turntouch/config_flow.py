"""Config flow for Turn Touch integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow

try:
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:  # HA < 2024.3
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import DOMAIN, SERVICE_UUID

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE = "device"


class TurnTouchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Turn Touch."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, str] = {}  # address → name

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm bluetooth discovery."""
        assert self._discovery_info is not None
        info = self._discovery_info

        if user_input is not None:
            return self.async_create_entry(
                title=info.name or info.address,
                data={
                    CONF_ADDRESS: info.address,
                    CONF_NAME: info.name or info.address,
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": info.name or info.address,
                "address": info.address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manually initiated setup — scan for nearby devices."""
        if user_input is not None:
            address = user_input[CONF_DEVICE]
            name = self._discovered_devices.get(address, address)
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=name,
                data={CONF_ADDRESS: address, CONF_NAME: name},
            )

        # Discover nearby Turn Touch devices.
        # Match by service UUID *or* by device name — the Turn Touch may not
        # include the service UUID in its advertisement packets (only in the
        # GATT table after connecting), so name matching is the reliable path.
        self._discovered_devices = {}
        for service_info in async_discovered_service_info(self.hass):
            name = service_info.name or ""
            has_service_uuid = SERVICE_UUID.lower() in [
                uuid.lower() for uuid in service_info.service_uuids
            ]
            if has_service_uuid or "turn touch" in name.lower():
                self._discovered_devices[service_info.address] = (
                    name or service_info.address
                )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): vol.In(
                        {
                            addr: f"{name} ({addr})"
                            for addr, name in self._discovered_devices.items()
                        }
                    )
                }
            ),
        )
