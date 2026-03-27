"""Device triggers for Turn Touch button events."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import BUTTONS, DOMAIN, EVENT_TYPES

TRIGGER_TYPES = {f"{b}_{e}" for b in BUTTONS for e in EVENT_TYPES}

TRIGGER_SCHEMA = vol.All(
    DEVICE_TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
        }
    )
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate the trigger config."""
    return TRIGGER_SCHEMA(config)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Turn Touch buttons."""
    registry = er.async_get(hass)
    triggers = []

    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain != EVENT_DOMAIN or entry.platform != DOMAIN:
            continue
        button = next((b for b in BUTTONS if entry.unique_id.endswith(f"_{b}")), None)
        if button is None:
            continue
        for event_type in EVENT_TYPES:
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DOMAIN: DOMAIN,
                    CONF_DEVICE_ID: device_id,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: f"{button}_{event_type}",
                }
            )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger for a Turn Touch button event."""
    trigger_type: str = config[CONF_TYPE]
    button = next(b for b in BUTTONS if trigger_type.startswith(f"{b}_"))
    event_type = trigger_type[len(button) + 1:]
    entity_id: str = config[CONF_ENTITY_ID]
    trigger_data: dict[str, Any] = trigger_info.get("trigger_data", {})  # type: ignore[assignment]

    @callback
    def _state_changed(event: Event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        if new_state.attributes.get("event_type") != event_type:
            return
        hass.async_run_job(
            action,
            {
                "trigger": {
                    **trigger_data,
                    CONF_PLATFORM: "device",
                    CONF_DOMAIN: DOMAIN,
                    CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                    CONF_ENTITY_ID: entity_id,
                    CONF_TYPE: trigger_type,
                }
            },
        )

    return async_track_state_change_event(hass, [entity_id], _state_changed)
