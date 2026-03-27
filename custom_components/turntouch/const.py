"""Constants for the Turn Touch integration."""

DOMAIN = "turntouch"

# BLE UUIDs
SERVICE_UUID = "99c31523-dc4f-41b1-bb04-4e4deb81fadd"
BUTTON_CHAR_UUID = "99c31525-dc4f-41b1-bb04-4e4deb81fadd"
NICKNAME_CHAR_UUID = "99c31526-dc4f-41b1-bb04-4e4deb81fadd"
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_CHAR_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

DEVICE_NAME = "Turn Touch Remote"

# Button names
BUTTON_NORTH = "north"
BUTTON_EAST = "east"
BUTTON_WEST = "west"
BUTTON_SOUTH = "south"

BUTTONS = [BUTTON_NORTH, BUTTON_EAST, BUTTON_WEST, BUTTON_SOUTH]

# Event types
EVENT_PRESS = "press"
EVENT_DOUBLE_TAP = "double_tap"
EVENT_HOLD = "hold"

EVENT_TYPES = [EVENT_PRESS, EVENT_DOUBLE_TAP, EVENT_HOLD]

# Button codes: 2-byte big-endian int from BLE notification → (button, event_type)
BUTTON_CODES: dict[int, tuple[str, str]] = {
    0xFE00: (BUTTON_NORTH, EVENT_PRESS),
    0xEF00: (BUTTON_NORTH, EVENT_DOUBLE_TAP),
    0xFEFF: (BUTTON_NORTH, EVENT_HOLD),
    0xFD00: (BUTTON_EAST, EVENT_PRESS),
    0xDF00: (BUTTON_EAST, EVENT_DOUBLE_TAP),
    0xFDFF: (BUTTON_EAST, EVENT_HOLD),
    0xFB00: (BUTTON_WEST, EVENT_PRESS),
    0xBF00: (BUTTON_WEST, EVENT_DOUBLE_TAP),
    0xFBFF: (BUTTON_WEST, EVENT_HOLD),
    0xF700: (BUTTON_SOUTH, EVENT_PRESS),
    0x7F00: (BUTTON_SOUTH, EVENT_DOUBLE_TAP),
    0xF7FF: (BUTTON_SOUTH, EVENT_HOLD),
}

# Off / release code (no action)
CODE_OFF = 0xFF00

# Reconnect settings
RECONNECT_DELAY = 5  # seconds before first reconnect attempt
MAX_RECONNECT_DELAY = 60  # max seconds between reconnect attempts

# Debounce: how long to wait after a "press" before firing it, to allow a
# "hold" or "double_tap" follow-up notification to arrive and cancel it.
PRESS_DEBOUNCE_DELAY = 0.4  # seconds

