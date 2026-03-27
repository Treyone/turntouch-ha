"""Event platform for Turn Touch buttons."""

from __future__ import annotations

import logging

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BUTTONS, DOMAIN, EVENT_TYPES
from .coordinator import TurnTouchCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Turn Touch button event entities."""
    coordinator: TurnTouchCoordinator = hass.data[DOMAIN][entry.entry_id]
    address: str = entry.data[CONF_ADDRESS]
    name: str = entry.data[CONF_NAME]

    entities = [
        TurnTouchButtonEvent(coordinator, entry.entry_id, address, name, button)
        for button in BUTTONS
    ]
    async_add_entities(entities)


class TurnTouchButtonEvent(EventEntity):
    """Represents a single directional button on the Turn Touch remote."""

    _attr_has_entity_name = True
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = EVENT_TYPES
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: TurnTouchCoordinator,
        entry_id: str,
        address: str,
        device_name: str,
        button: str,
    ) -> None:
        self._coordinator = coordinator
        self._button = button
        self._attr_unique_id = f"{address}_{button}"
        self._attr_name = f"{button.capitalize()} Button"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=device_name,
            manufacturer="Turn Touch",
            model="Turn Touch Remote",
        )
        self._unregister_callback: callback | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to button events when entity is added."""
        self._unregister_callback = self._coordinator.register_button_callback(
            self._handle_button_event
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe when entity is removed."""
        if self._unregister_callback is not None:
            self._unregister_callback()

    @callback
    def _handle_button_event(self, button: str, event_type: str) -> None:
        """Fire a HA event if this entity's button was pressed."""
        if button == self._button:
            self._trigger_event(event_type)
            self.async_write_ha_state()
