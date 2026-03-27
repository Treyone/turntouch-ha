# Turn Touch for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Home Assistant integration for the [Turn Touch](https://shop.turntouch.com/) Bluetooth remote. Supports all 4 buttons (North, East, West, South) with press, double-tap, and hold actions.

## Features

- Auto-discovery of nearby Turn Touch devices
- 4 button event entities (North, East, West, South)
- 3 action types per button: `press`, `double_tap`, `hold` → 12 total triggers for automations
- Battery level sensor
- Active BLE connection with automatic reconnection

## Installation via HACS

1. Open HACS in your Home Assistant instance
2. Go to **Integrations**
3. Click the three-dot menu → **Custom repositories**
4. Add `https://github.com/Treyone/turntouch-ha` with category **Integration**
5. Click **Install**
6. Restart Home Assistant

## Manual Installation

1. Copy `custom_components/turntouch/` into your HA `config/custom_components/` folder
2. Restart Home Assistant

## Setup

1. Make sure your Turn Touch remote is nearby and has Bluetooth enabled on your HA host
2. Go to **Settings → Devices & Services → Add Integration**
3. Search for **Turn Touch** — if the device was already detected, a notification will appear automatically
4. Follow the setup steps

## Usage in Automations

In the automation editor, select **Device** as trigger type, pick your Turn Touch remote, and choose from the 12 available triggers (North / East / West / South × press / double_tap / hold).

Example automation YAML:

```yaml
automation:
  - alias: 'Turn Touch North Press → Toggle Light'
    trigger:
      - platform: device
        domain: turntouch
        device_id: !secret turn_touch_device_id
        type: north_press
    action:
      - service: light.toggle
        target:
          entity_id: light.living_room
```

Replace `north_press` with any of the 12 trigger types: `north_press`, `north_double_tap`, `north_hold`, `east_press`, `east_double_tap`, `east_hold`, `west_press`, `west_double_tap`, `west_hold`, `south_press`, `south_double_tap`, `south_hold`.

## Button Map

| Direction      | Single Press | Double-Tap   | Hold   |
| -------------- | ------------ | ------------ | ------ |
| North (top)    | `press`      | `double_tap` | `hold` |
| East (right)   | `press`      | `double_tap` | `hold` |
| West (left)    | `press`      | `double_tap` | `hold` |
| South (bottom) | `press`      | `double_tap` | `hold` |

## Requirements

- Home Assistant 2023.8 or newer
- Bluetooth adapter on the HA host (or an [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html))

## License

MIT
