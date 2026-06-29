from app.config import AppConfig
from app.mqtt_discovery import build_discovery_payloads


def test_discovery_payloads_include_device_and_fan():
    config = AppConfig(mock_hardware=True)

    payloads = build_discovery_payloads(config, "ha_pi_panel", "homeassistant", "ha_pi_panel/availability")

    fan_topic = "homeassistant/fan/ha_pi_panel/case_fan/config"
    assert fan_topic in payloads
    assert payloads[fan_topic]["device"]["model"] == "Raspberry Pi 4 HAOS Panel"
    assert payloads[fan_topic]["percentage_command_topic"] == "ha_pi_panel/fan/percentage/set"


def test_discovery_payloads_include_problem_binary_sensor():
    payloads = build_discovery_payloads(AppConfig(), "base", "homeassistant", "base/availability")

    assert "homeassistant/binary_sensor/ha_pi_panel/hardware_fault/config" in payloads
