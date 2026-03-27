"""Battery sensor for Turn Touch."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TurnTouchCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Turn Touch battery sensor."""
    coordinator: TurnTouchCoordinator = hass.data[DOMAIN][entry.entry_id]
    address: str = entry.data[CONF_ADDRESS]
    name: str = entry.data[CONF_NAME]
    async_add_entities([TurnTouchBatterySensor(coordinator, address, name)])


class TurnTouchBatterySensor(SensorEntity):
    """Battery level sensor for the Turn Touch remote."""

    _attr_has_entity_name = True
    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: TurnTouchCoordinator,
        address: str,
        device_name: str,
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{address}_battery"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=device_name,
            manufacturer="Turn Touch",
            model="Turn Touch Remote",
        )
        self._unregister_callback: callback | None = None

    @property
    def native_value(self) -> int | None:
        return self._coordinator.battery_level

    async def async_added_to_hass(self) -> None:
        """Subscribe to battery updates."""
        self._unregister_callback = self._coordinator.register_battery_callback(
            self._handle_battery_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe when entity is removed."""
        if self._unregister_callback is not None:
            self._unregister_callback()

    @callback
    def _handle_battery_update(self, level: int) -> None:
        self.async_write_ha_state()
