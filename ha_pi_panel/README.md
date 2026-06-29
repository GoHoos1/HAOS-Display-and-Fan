# HA Pi Panel

HA Pi Panel is a Home Assistant OS add-on for Raspberry Pi 4 that renders status pages on a small I2C OLED display and controls a 5V case fan.

Supported display targets:

- Dorhea 0.96 inch yellow/blue 128x64 I2C OLED, usually SSD1306 at `0x3C`.
- Generic 0.91 inch blue 128x32 I2C OLED, usually SSD1306 at `0x3C`.
- SH1106 128x64 is included as an optional display type.

The add-on is designed for Home Assistant OS. It maps `/dev/i2c-1` and `/dev/gpiochip0` explicitly and does not require host scripts or long-lived Home Assistant tokens.

## Installation

1. Copy this repository into `/addons/ha_pi_panel` on the Home Assistant host, or add the repository as a local add-on repository.
2. In Home Assistant, go to Settings, Add-ons, Add-on Store, reload local add-ons, and install **HA Pi Panel**.
3. Start with `mock_hardware: true` for a smoke test.
4. Enable I2C and connect hardware before switching `mock_hardware` to `false`.

## Wiring Notes

OLED wiring uses the Raspberry Pi I2C pins: VCC, GND, SDA, and SCL. Most SSD1306 modules use address `0x3C`; some use `0x3D`.

Fan wiring is safety-critical: power the fan from 5V and GND, not from a GPIO pin. GPIO may only be used as a control signal into a suitable transistor, MOSFET, driver board, or PWM input circuit.

## Entities

When MQTT is available, Home Assistant discovery creates one device named `HA Pi Panel` with a case fan, system sensors, display switch, fan mode select, and a hardware fault binary sensor.

See `DOCS.md` for setup, configuration examples, PWM limitations, and troubleshooting.
