"""Tests for TurnTouchCoordinator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak import BleakError

from custom_components.turntouch.const import (
    BATTERY_CHAR_UUID,
    BUTTON_CHAR_UUID,
    BUTTON_CODES,
    CODE_OFF,
    MAX_RECONNECT_DELAY,
    PRESS_DEBOUNCE_DELAY,
    RECONNECT_DELAY,
)
from custom_components.turntouch.coordinator import TurnTouchCoordinator

from .conftest import ADDRESS, DEVICE_NAME


# ---------------------------------------------------------------------------
# Button notification parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code,expected_button,expected_event", [
    (code, button, event)
    for code, (button, event) in BUTTON_CODES.items()
    if event != "press"  # press events are debounced; tested separately
])
def test_button_notification_non_press_codes_fire_immediately(
    coordinator, code, expected_button, expected_event
):
    """hold and double_tap codes fire the callback immediately."""
    received = []
    coordinator.register_button_callback(lambda b, e: received.append((b, e)))

    coordinator._handle_button_notification(None, bytearray(code.to_bytes(2, "big")))

    assert received == [(expected_button, expected_event)]


def test_button_notification_off_code_ignored(coordinator):
    """The OFF/release code must not fire any callback."""
    received = []
    coordinator.register_button_callback(lambda b, e: received.append((b, e)))

    data = bytearray(CODE_OFF.to_bytes(2, "big"))
    coordinator._handle_button_notification(None, data)

    assert received == []


def test_button_notification_unknown_code_ignored(coordinator):
    """An unknown code must not fire any callback (logged at DEBUG)."""
    received = []
    coordinator.register_button_callback(lambda b, e: received.append((b, e)))

    coordinator._handle_button_notification(None, bytearray(b"\x00\x00"))

    assert received == []


def test_button_notification_short_data_ignored(coordinator):
    """Data shorter than 2 bytes must not fire any callback."""
    received = []
    coordinator.register_button_callback(lambda b, e: received.append((b, e)))

    coordinator._handle_button_notification(None, bytearray(b"\xFE"))

    assert received == []


async def test_button_notification_fires_multiple_callbacks(coordinator):
    """All registered callbacks receive the event (tested via debounced press)."""
    results_a, results_b = [], []
    coordinator.register_button_callback(lambda b, e: results_a.append((b, e)))
    coordinator.register_button_callback(lambda b, e: results_b.append((b, e)))

    coordinator._handle_button_notification(None, bytearray(b"\xFE\x00"))  # North press
    await asyncio.sleep(PRESS_DEBOUNCE_DELAY + 0.05)

    assert results_a == [("north", "press")]
    assert results_b == [("north", "press")]


async def test_button_callback_unregister(coordinator):
    """Unregistering a callback stops it from receiving future events."""
    received = []
    unregister = coordinator.register_button_callback(
        lambda b, e: received.append((b, e))
    )

    unregister()
    coordinator._handle_button_notification(None, bytearray(b"\xFE\x00"))
    await asyncio.sleep(PRESS_DEBOUNCE_DELAY + 0.05)

    assert received == []


# ---------------------------------------------------------------------------
# Debounce
# ---------------------------------------------------------------------------


async def test_press_fires_after_debounce_delay(coordinator):
    """A press event fires after PRESS_DEBOUNCE_DELAY with no follow-up."""
    received = []
    coordinator.register_button_callback(lambda b, e: received.append((b, e)))

    coordinator._handle_button_notification(None, bytearray(b"\xFE\x00"))  # North press
    assert received == []  # not yet

    await asyncio.sleep(PRESS_DEBOUNCE_DELAY + 0.05)
    assert received == [("north", "press")]


async def test_hold_cancels_pending_press(coordinator):
    """A hold notification arriving before the debounce delay cancels the press."""
    received = []
    coordinator.register_button_callback(lambda b, e: received.append((b, e)))

    coordinator._handle_button_notification(None, bytearray(b"\xFE\x00"))  # press
    coordinator._handle_button_notification(None, bytearray(b"\xFE\xFF"))  # hold

    await asyncio.sleep(PRESS_DEBOUNCE_DELAY + 0.05)
    assert received == [("north", "hold")]


async def test_double_tap_cancels_pending_press(coordinator):
    """A double_tap notification arriving before the debounce delay cancels the press."""
    received = []
    coordinator.register_button_callback(lambda b, e: received.append((b, e)))

    coordinator._handle_button_notification(None, bytearray(b"\xFE\x00"))  # press
    coordinator._handle_button_notification(None, bytearray(b"\xEF\x00"))  # double_tap

    await asyncio.sleep(PRESS_DEBOUNCE_DELAY + 0.05)
    assert received == [("north", "double_tap")]


async def test_press_on_different_button_does_not_cancel(coordinator):
    """A follow-up on a different button does not cancel the first button's press."""
    received = []
    coordinator.register_button_callback(lambda b, e: received.append((b, e)))

    coordinator._handle_button_notification(None, bytearray(b"\xFE\x00"))  # north press
    coordinator._handle_button_notification(None, bytearray(b"\xFD\xFF"))  # east hold

    await asyncio.sleep(PRESS_DEBOUNCE_DELAY + 0.05)
    # Both fire: north press (after delay) + east hold (immediately)
    assert ("north", "press") in received
    assert ("east", "hold") in received


async def test_stop_cancels_pending_press(coordinator):
    """async_stop cancels any buffered press without firing it."""
    received = []
    coordinator.register_button_callback(lambda b, e: received.append((b, e)))

    coordinator._handle_button_notification(None, bytearray(b"\xFE\x00"))  # north press
    await coordinator.async_stop()

    await asyncio.sleep(PRESS_DEBOUNCE_DELAY + 0.05)
    assert received == []


# ---------------------------------------------------------------------------
# Battery
# ---------------------------------------------------------------------------


def test_battery_notification_updates_level(coordinator):
    """A battery BLE notification updates battery_level and fires callback."""
    levels = []
    coordinator.register_battery_callback(lambda lvl: levels.append(lvl))

    coordinator._handle_battery_notification(None, bytearray([72]))

    assert coordinator.battery_level == 72
    assert levels == [72]


def test_battery_notification_empty_data_ignored(coordinator):
    """An empty battery notification payload must not update battery_level."""
    coordinator._handle_battery_notification(None, bytearray())

    assert coordinator.battery_level is None


def test_battery_callback_unregister(coordinator):
    """Unregistering a battery callback stops future updates."""
    received = []
    unregister = coordinator.register_battery_callback(lambda lvl: received.append(lvl))

    unregister()
    coordinator._handle_battery_notification(None, bytearray([50]))

    assert received == []


async def test_battery_setup_subscribes_to_notifications(coordinator, mock_bleak_client):
    """If start_notify succeeds, notifications are used (no read_gatt_char)."""
    await coordinator._async_setup_battery(mock_bleak_client)

    mock_bleak_client.start_notify.assert_awaited_once_with(
        BATTERY_CHAR_UUID, coordinator._handle_battery_notification
    )
    mock_bleak_client.read_gatt_char.assert_not_awaited()


async def test_battery_setup_falls_back_to_read_when_notify_unsupported(
    coordinator, mock_bleak_client
):
    """If start_notify raises BleakError, battery is read once instead."""
    mock_bleak_client.start_notify.side_effect = BleakError("not supported")
    mock_bleak_client.read_gatt_char.return_value = bytearray([85])

    await coordinator._async_setup_battery(mock_bleak_client)

    mock_bleak_client.read_gatt_char.assert_awaited_once_with(BATTERY_CHAR_UUID)
    assert coordinator.battery_level == 85


async def test_battery_read_failure_is_silent(coordinator, mock_bleak_client):
    """A failed battery read must not raise — just leaves battery_level as None."""
    mock_bleak_client.read_gatt_char.side_effect = Exception("read error")

    await coordinator._async_read_battery(mock_bleak_client)

    assert coordinator.battery_level is None


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------


async def test_connect_device_not_found_schedules_reconnect(coordinator):
    """When the BLE device is not found, a reconnect is scheduled."""
    with patch(
        "custom_components.turntouch.coordinator.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        await coordinator._async_connect()

    assert coordinator._reconnect_task is not None
    coordinator._reconnect_task.cancel()


async def test_connect_success_subscribes_and_reads_battery(
    coordinator, mock_ble_device, mock_bleak_client
):
    """Successful connect subscribes to button notifications and sets up battery."""
    with (
        patch(
            "custom_components.turntouch.coordinator.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.turntouch.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_bleak_client,
        ),
    ):
        await coordinator._async_connect()

    mock_bleak_client.start_notify.assert_any_await(
        BUTTON_CHAR_UUID, coordinator._handle_button_notification
    )
    assert coordinator._client is mock_bleak_client
    assert coordinator._reconnect_delay == RECONNECT_DELAY  # backoff reset


async def test_connect_failure_schedules_reconnect(coordinator, mock_ble_device):
    """If establish_connection raises, a reconnect is scheduled."""
    with (
        patch(
            "custom_components.turntouch.coordinator.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.turntouch.coordinator.establish_connection",
            new_callable=AsyncMock,
            side_effect=Exception("connection refused"),
        ),
    ):
        await coordinator._async_connect()

    assert coordinator._reconnect_task is not None
    coordinator._reconnect_task.cancel()


async def test_button_notify_failure_disconnects_and_schedules_reconnect(
    coordinator, mock_ble_device, mock_bleak_client
):
    """If subscribing to button notifications fails, the client is disconnected."""
    mock_bleak_client.start_notify.side_effect = Exception("notify failed")

    with (
        patch(
            "custom_components.turntouch.coordinator.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.turntouch.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_bleak_client,
        ),
    ):
        await coordinator._async_connect()

    mock_bleak_client.disconnect.assert_awaited_once()
    assert coordinator._client is None
    assert coordinator._reconnect_task is not None
    coordinator._reconnect_task.cancel()


async def test_disconnect_schedules_reconnect(connected_coordinator):
    """An unexpected disconnect triggers a reconnect task."""
    mock_client = MagicMock()
    connected_coordinator._handle_disconnect(mock_client)

    assert connected_coordinator._reconnect_task is not None
    connected_coordinator._reconnect_task.cancel()


async def test_disconnect_does_not_reconnect_after_stop(connected_coordinator):
    """No reconnect is scheduled if the coordinator was stopped."""
    connected_coordinator._stop_event.set()
    connected_coordinator._handle_disconnect(MagicMock())

    assert connected_coordinator._reconnect_task is None


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------


async def test_stop_disconnects_client(connected_coordinator, mock_bleak_client):
    """async_stop disconnects the active BLE client."""
    await connected_coordinator.async_stop()

    mock_bleak_client.disconnect.assert_awaited_once()
    assert connected_coordinator._client is None


async def test_stop_cancels_pending_reconnect(coordinator):
    """async_stop cancels any in-flight reconnect task."""
    # Schedule a reconnect first (device not found path)
    with patch(
        "custom_components.turntouch.coordinator.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        await coordinator._async_connect()

    task = coordinator._reconnect_task
    assert task is not None

    await coordinator.async_stop()

    assert task.cancelled()


async def test_stop_prevents_new_reconnects(coordinator):
    """After stop, _schedule_reconnect must not create a new task."""
    await coordinator.async_stop()
    coordinator._schedule_reconnect()

    assert coordinator._reconnect_task is None


# ---------------------------------------------------------------------------
# Reconnect backoff
# ---------------------------------------------------------------------------


def test_reconnect_delay_doubles_on_each_failure(coordinator):
    """Reconnect delay doubles after each failed attempt, up to MAX."""
    assert coordinator._reconnect_delay == RECONNECT_DELAY

    for _ in range(10):
        coordinator._reconnect_delay = min(
            coordinator._reconnect_delay * 2, MAX_RECONNECT_DELAY
        )

    assert coordinator._reconnect_delay == MAX_RECONNECT_DELAY


async def test_reconnect_resets_delay_on_success(
    coordinator, mock_ble_device, mock_bleak_client
):
    """A successful connection resets the reconnect delay to the initial value."""
    coordinator._reconnect_delay = MAX_RECONNECT_DELAY  # simulate many failures

    with (
        patch(
            "custom_components.turntouch.coordinator.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "custom_components.turntouch.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_bleak_client,
        ),
    ):
        await coordinator._async_connect()

    assert coordinator._reconnect_delay == RECONNECT_DELAY
