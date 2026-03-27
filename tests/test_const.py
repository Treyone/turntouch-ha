"""Tests for Turn Touch constants."""

from custom_components.turntouch.const import (
    BUTTON_CODES,
    BUTTONS,
    CODE_OFF,
    EVENT_TYPES,
)


def test_all_buttons_have_all_event_types():
    """Every button must have press, double_tap, and hold codes."""
    found: dict[str, set[str]] = {b: set() for b in BUTTONS}
    for button, event_type in BUTTON_CODES.values():
        found[button].add(event_type)

    for button in BUTTONS:
        assert found[button] == set(EVENT_TYPES), (
            f"Button '{button}' missing event types: "
            f"{set(EVENT_TYPES) - found[button]}"
        )


def test_button_codes_total_count():
    """There must be exactly 12 codes (4 buttons × 3 event types)."""
    assert len(BUTTON_CODES) == len(BUTTONS) * len(EVENT_TYPES)


def test_no_duplicate_codes():
    """Each code value must map to exactly one action."""
    assert len(BUTTON_CODES) == len(set(BUTTON_CODES.keys()))


def test_code_off_not_in_button_codes():
    """The OFF/release code must not trigger any action."""
    assert CODE_OFF not in BUTTON_CODES


def test_all_codes_are_two_bytes():
    """All button codes must fit in 2 bytes (0x0000–0xFFFF)."""
    for code in list(BUTTON_CODES.keys()) + [CODE_OFF]:
        assert 0x0000 <= code <= 0xFFFF, f"Code 0x{code:04X} out of 2-byte range"
