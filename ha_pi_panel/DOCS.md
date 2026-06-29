# HA Pi Panel Documentation

## What It Does

HA Pi Panel runs as a Home Assistant OS add-on on Raspberry Pi 4. It can show rotating OLED status pages, control a 5V fan, publish system state over MQTT discovery, and fetch selected Home Assistant entity states through the Supervisor-proxied Core API.

No long-lived access token is required. The add-on uses SUPERVISOR_TOKEN and http://supervisor/core/api/ from inside the add-on.

## Supported Hardware

Displays:

- Dorhea 0.96 inch yellow/blue I2C OLED, 128x64, usually SSD1306-compatible.
- Generic 0.91 inch blue I2C OLED, 128x32, usually SSD1306-compatible.
- SH1106 128x64 modules may work by selecting sh1106_128x64.

Fan:

- GeeekPi 4010 DC 5V fan or a similar 5V fan controlled by a suitable external switching or PWM circuit.

## Wiring

### OLED

Connect the OLED module to the Raspberry Pi I2C bus:

- VCC to 3.3V or 5V, according to the display module rating.
- GND to GND.
- SDA to Raspberry Pi SDA.
- SCL to Raspberry Pi SCL.

Most modules use I2C address 0x3C. If the display stays blank, scan the bus or try 0x3D.

### Fan

Do not power the fan from a GPIO pin. A GPIO pin is only a control or signal pin. Power the fan from 5V and GND, and use a transistor, MOSFET, fan HAT, or proper driver circuit if switching the fan from GPIO.

Use BCM GPIO numbering in the add-on configuration. The default fan_gpio_line: 18 means BCM GPIO18, not physical pin 18.

## Enable I2C on Home Assistant OS

Home Assistant OS does not use the same workflow as Raspberry Pi OS. Enable I2C using the Home Assistant OS hardware configuration method for Raspberry Pi, then fully reboot the host. After reboot, /dev/i2c-1 should exist and the add-on can map it.

The add-on intentionally does not edit the HAOS boot partition automatically. If /dev/i2c-1 is missing, it logs a clear warning and continues in degraded mode.

## Install as a Local Add-on

1. Place this repository where Home Assistant can see local add-ons, for example /addons/ha_pi_panel.
2. Open Settings, Add-ons, Add-on Store.
3. Reload local add-ons.
4. Install HA Pi Panel.
5. Start with mock_hardware: true to verify the add-on starts before attaching hardware.

## Display Configuration

Use display_type to match the module:

- ssd1306_128x64 for the Dorhea 0.96 inch module.
- ssd1306_128x32 for common 0.91 inch modules.
- sh1106_128x64 for compatible SH1106 modules.

Set display_width and display_height to the actual panel size. The renderer automatically limits lines on 128x32 panels.

Example page JSON:

    [
      {
        "name": "System",
        "lines": ["HA Pi Panel", "IP: {ip}", "CPU: {cpu_temp_c}C", "RAM: {mem_percent}%"]
      },
      {
        "name": "Home",
        "lines": ["Outside {ha:sensor.outdoor_temperature}", "Weather {ha:weather.home}", "DNS {ha:sensor.pihole_ads_blocked_today}", "{time}"]
      }
    ]

Supported tokens include {hostname}, {ip}, {time}, {date}, {uptime}, {cpu_temp_c}, {cpu_load_1m}, {mem_percent}, {disk_percent}, {fan_percent}, {fan_mode}, {display_status}, and {ha:entity_id}.

Unavailable Home Assistant entities render as --.

## Fan Configuration

Backends:

- off: no GPIO access.
- gpio_onoff: reliable on/off control through /dev/gpiochip0 using python-periphery.
- software_pwm: experimental low-frequency PWM by toggling a GPIO line. It is capped at 100 Hz to avoid busy-looping and is not a reliable 25 kHz PC fan PWM source.
- sysfs_pwm: optional backend if /sys/class/pwm/pwmchip0/pwm0 is available and mapped. It fails gracefully when unavailable.

Example fan curve:

    [
      {"temp_c": 45, "percent": 0},
      {"temp_c": 55, "percent": 35},
      {"temp_c": 65, "percent": 70},
      {"temp_c": 75, "percent": 100}
    ]

Auto mode interpolates between points. Manual mode uses the MQTT fan command or fan_manual_percent. Off mode keeps the fan off unless CPU temperature reaches fan_fail_safe_temp_c, which forces 100 percent.

The default shutdown behavior is on for thermal safety.

## MQTT Discovery

When the Mosquitto add-on service is available, run.sh exports MQTT connection variables through bashio. Discovery payloads are retained. State is published under the configured base topic, default ha_pi_panel.

Home Assistant should discover:

- fan.ha_pi_panel_case_fan
- CPU temperature sensor
- CPU load sensor
- Memory percent sensor
- Disk percent sensor
- Uptime sensor
- Fan requested percent sensor
- Fan backend state sensor
- Display status sensor
- OLED display switch
- Fan mode select
- Hardware fault binary sensor

The add-on subscribes to homeassistant/status and republishes discovery when Home Assistant announces it is online.

## Startup Validation

At startup the add-on logs the version, architecture, mock mode, I2C device presence, GPIO chip presence, OLED initialization status, fan backend, MQTT status, and Home Assistant API status.

## Known Limitations

Container metrics are read from Linux paths visible inside the add-on. On HAOS these are generally useful, but disk and memory may not be identical to every host-level view.

High-frequency fan PWM from inside a HAOS add-on is not guaranteed without additional host device mapping and privileges. The reliable default is GPIO on/off control through /dev/gpiochip0.

## Troubleshooting

/dev/i2c-1 missing: Enable I2C for Home Assistant OS on Raspberry Pi and reboot the host. Confirm the add-on has /dev/i2c-1 mapped.

OLED blank: Check VCC, GND, SDA, SCL, display type, width, height, and address. Try 0x3D if 0x3C fails.

Wrong I2C address: Use an I2C scan from an appropriate HAOS shell or hardware tool. Update display_i2c_address.

GPIO chip missing: Confirm /dev/gpiochip0 exists on the host and is listed in the add-on devices.

Fan always on: Check fan_active_high, wiring, transistor orientation, and whether fan_shutdown_behavior left the control line active after a stop.

Fan never turns on: Check that the fan has 5V/GND power, the GPIO is only used as control, the selected BCM line is correct, and the fan mode or curve asks for a nonzero percentage.

MQTT entities not appearing: Confirm the MQTT add-on is installed and running, MQTT service discovery is available to this add-on, mqtt_enabled is true, and Home Assistant MQTT integration has discovery enabled.
