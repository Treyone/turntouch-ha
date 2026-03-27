"""BLE connection coordinator for Turn Touch."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from bleak import BleakClient, BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback

from .const import (
    BATTERY_CHAR_UUID,
    BUTTON_CHAR_UUID,
    BUTTON_CODES,
    CODE_OFF,
    EVENT_PRESS,
    MAX_RECONNECT_DELAY,
    PRESS_DEBOUNCE_DELAY,
    RECONNECT_DELAY,
)

_LOGGER = logging.getLogger(__name__)

ButtonCallback = Callable[[str, str], None]


class TurnTouchCoordinator:
    """Manages the active BLE connection to a Turn Touch device."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
    ) -> None:
        self.hass = hass
        self.address = address
        self.name = name
        self.battery_level: int | None = None

        self._client: BleakClient | None = None
        self._button_callbacks: list[ButtonCallback] = []
        self._battery_callbacks: list[Callable[[int], None]] = []
        self._reconnect_delay = RECONNECT_DELAY
        self._stop_event = asyncio.Event()
        self._reconnect_task: asyncio.Task | None = None
        # Pending "press" timers keyed by button name. A press is held for
        # PRESS_DEBOUNCE_DELAY so that a hold/double_tap arriving shortly after
        # can cancel it before it fires.
        self._pending_press: dict[str, asyncio.TimerHandle] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def async_start(self) -> None:
        """Start the coordinator: connect and subscribe."""
        self._stop_event.clear()
        await self._async_connect()

    async def async_stop(self) -> None:
        """Stop the coordinator and disconnect."""
        self._stop_event.set()
        for button in list(self._pending_press):
            self._cancel_pending_press(button)
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass
        self._client = None

    @callback
    def register_button_callback(self, cb: ButtonCallback) -> Callable[[], None]:
        """Register a callback for button events. Returns an unregister function."""
        self._button_callbacks.append(cb)

        @callback
        def unregister() -> None:
            self._button_callbacks.remove(cb)

        return unregister

    @callback
    def register_battery_callback(
        self, cb: Callable[[int], None]
    ) -> Callable[[], None]:
        """Register a callback for battery level updates."""
        self._battery_callbacks.append(cb)

        @callback
        def unregister() -> None:
            self._battery_callbacks.remove(cb)

        return unregister

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _async_connect(self) -> None:
        """Establish BLE connection and subscribe to notifications."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            _LOGGER.warning(
                "Turn Touch %s (%s) not found via bluetooth, will retry",
                self.name,
                self.address,
            )
            self._schedule_reconnect()
            return

        try:
            _LOGGER.debug("Connecting to Turn Touch %s (%s)", self.name, self.address)
            client = await establish_connection(
                BleakClient,
                ble_device,
                self.name,
                disconnected_callback=self._handle_disconnect,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Failed to connect to Turn Touch %s: %s. Will retry.",
                self.address,
                err,
            )
            self._schedule_reconnect()
            return

        self._client = client
        self._reconnect_delay = RECONNECT_DELAY  # reset backoff on success

        try:
            await client.start_notify(BUTTON_CHAR_UUID, self._handle_button_notification)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to subscribe to button notifications: %s", err)
            await client.disconnect()
            self._client = None
            self._schedule_reconnect()
            return

        _LOGGER.info("Connected to Turn Touch %s (%s)", self.name, self.address)
        await self._async_setup_battery(client)

    def _handle_disconnect(self, client: BleakClient) -> None:
        """Handle an unexpected BLE disconnection."""
        _LOGGER.warning("Turn Touch %s disconnected", self.address)
        self._client = None
        if not self._stop_event.is_set():
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        if self._stop_event.is_set():
            return
        _LOGGER.debug(
            "Scheduling reconnect for %s in %ss", self.address, self._reconnect_delay
        )
        self._reconnect_task = asyncio.ensure_future(self._async_reconnect_after_delay())

    async def _async_reconnect_after_delay(self) -> None:
        try:
            await asyncio.wait_for(
                self._stop_event.wait(), timeout=self._reconnect_delay
            )
        except asyncio.TimeoutError:
            pass
        else:
            return  # stop was requested

        self._reconnect_delay = min(self._reconnect_delay * 2, MAX_RECONNECT_DELAY)
        await self._async_connect()

    def _handle_button_notification(self, sender: Any, data: bytearray) -> None:
        """Parse a 2-byte BLE notification and fire button callbacks."""
        if len(data) < 2:
            return
        code = int.from_bytes(data[:2], byteorder="big")
        if code == CODE_OFF:
            return
        result = BUTTON_CODES.get(code)
        if result is None:
            _LOGGER.debug("Unknown button code: 0x%04X", code)
            return
        button, event_type = result
        _LOGGER.debug("Button event: %s %s", button, event_type)

        if event_type == EVENT_PRESS:
            # Delay firing; a hold/double_tap arriving within PRESS_DEBOUNCE_DELAY
            # will cancel this and fire itself instead.
            self._cancel_pending_press(button)
            loop = asyncio.get_event_loop()
            self._pending_press[button] = loop.call_later(
                PRESS_DEBOUNCE_DELAY,
                self._fire_event,
                button,
                event_type,
            )
        else:
            # hold or double_tap: cancel any buffered press for this button first.
            self._cancel_pending_press(button)
            self._fire_event(button, event_type)

    def _cancel_pending_press(self, button: str) -> None:
        handle = self._pending_press.pop(button, None)
        if handle is not None:
            handle.cancel()

    def _fire_event(self, button: str, event_type: str) -> None:
        self._pending_press.pop(button, None)
        for cb in list(self._button_callbacks):
            cb(button, event_type)

    async def _async_setup_battery(self, client: BleakClient) -> None:
        """Subscribe to battery notifications, or read once if not supported."""
        try:
            await client.start_notify(BATTERY_CHAR_UUID, self._handle_battery_notification)
            _LOGGER.debug("Subscribed to battery notifications")
        except BleakError:
            # Device does not support battery notifications — read once on connect
            _LOGGER.debug("Battery notifications not supported, reading once")
            await self._async_read_battery(client)

    def _handle_battery_notification(self, sender: Any, data: bytearray) -> None:
        """Handle a battery level notification from the device."""
        if data:
            self._update_battery(int(data[0]))

    async def _async_read_battery(self, client: BleakClient) -> None:
        """Read battery level once from the device."""
        try:
            data = await client.read_gatt_char(BATTERY_CHAR_UUID)
            self._update_battery(int(data[0]))
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Could not read battery level: %s", err)

    def _update_battery(self, level: int) -> None:
        self.battery_level = level
        _LOGGER.debug("Battery level: %d%%", level)
        for cb in list(self._battery_callbacks):
            cb(level)
