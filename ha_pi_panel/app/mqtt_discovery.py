from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

try:
    import paho.mqtt.client as mqtt
except ImportError:  # Allows discovery payload tests without the runtime dependency.
    mqtt = None  # type: ignore[assignment]

from . import __version__
from .config import AppConfig


LOGGER = logging.getLogger(__name__)


class MqttManager:
    def __init__(
        self,
        config: AppConfig,
        on_fan_percent: Callable[[int], None],
        on_display_enabled: Callable[[bool], None],
        on_fan_mode: Callable[[str], None],
    ) -> None:
        self.config = config
        self.base = config.mqtt_base_topic
        self.discovery_prefix = config.mqtt_discovery_prefix
        self.availability_topic = f"{self.base}/availability"
        self.state_topic = f"{self.base}/state"
        self.fan_command_topic = f"{self.base}/fan/percentage/set"
        self.display_command_topic = f"{self.base}/display/enabled/set"
        self.fan_mode_command_topic = f"{self.base}/fan/mode/set"
        self.on_fan_percent = on_fan_percent
        self.on_display_enabled = on_display_enabled
        self.on_fan_mode = on_fan_mode
        self.client: mqtt.Client | None = None

    @property
    def enabled(self) -> bool:
        return self.config.mqtt_enabled and bool(os.environ.get("MQTT_HOST"))

    def connect(self) -> None:
        if not self.enabled:
            LOGGER.warning("MQTT is disabled or no MQTT service was discovered")
            return
        if mqtt is None:
            LOGGER.warning("paho-mqtt is not installed; MQTT is disabled")
            return
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{self.base}_addon")
        username = os.environ.get("MQTT_USERNAME")
        password = os.environ.get("MQTT_PASSWORD")
        if username:
            client.username_pw_set(username, password)
        client.will_set(self.availability_topic, "offline", retain=True)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.connect(os.environ["MQTT_HOST"], int(os.environ.get("MQTT_PORT", "1883")), keepalive=60)
        client.loop_start()
        self.client = client

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any | None = None) -> None:
        LOGGER.info("MQTT connected with result %s", reason_code)
        client.subscribe("homeassistant/status")
        client.subscribe(self.fan_command_topic)
        client.subscribe(self.display_command_topic)
        client.subscribe(self.fan_mode_command_topic)
        self.publish_discovery()
        self.publish_availability(True)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        payload = msg.payload.decode("utf-8", errors="replace").strip()
        if msg.topic == "homeassistant/status" and payload.lower() == "online":
            self.publish_discovery()
            return
        if msg.topic == self.fan_command_topic:
            try:
                self.on_fan_percent(max(0, min(100, int(float(payload)))))
            except ValueError:
                LOGGER.warning("Invalid fan percentage command: %s", payload)
            return
        if msg.topic == self.display_command_topic:
            self.on_display_enabled(payload.upper() in {"ON", "1", "TRUE"})
            return
        if msg.topic == self.fan_mode_command_topic and payload in {"auto", "manual", "off"}:
            self.on_fan_mode(payload)

    def publish_availability(self, online: bool) -> None:
        self.publish(self.availability_topic, "online" if online else "offline", retain=True)

    def publish(self, topic: str, payload: str | dict[str, Any], retain: bool = False) -> None:
        if not self.client:
            return
        if isinstance(payload, dict):
            payload = json.dumps(payload, separators=(",", ":"))
        self.client.publish(topic, payload, retain=retain)

    def device(self) -> dict[str, Any]:
        return {
            "identifiers": ["ha_pi_panel_rpi4"],
            "name": self.config.device_name,
            "manufacturer": "Local",
            "model": "Raspberry Pi 4 HAOS Panel",
            "sw_version": __version__,
        }

    def discovery_payloads(self) -> dict[str, dict[str, Any]]:
        return build_discovery_payloads(self.config, self.base, self.discovery_prefix, self.availability_topic, self.device())

    def publish_discovery(self) -> None:
        for topic, payload in self.discovery_payloads().items():
            self.publish(topic, payload, retain=True)
        LOGGER.info("MQTT discovery payloads published")

    def publish_state(self, state: dict[str, Any]) -> None:
        self.publish(self.state_topic, state, retain=False)

    def close(self) -> None:
        self.publish_availability(False)
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()


def build_discovery_payloads(
    config: AppConfig,
    base: str,
    discovery_prefix: str,
    availability_topic: str,
    device: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    device = device or {
        "identifiers": ["ha_pi_panel_rpi4"],
        "name": config.device_name,
        "manufacturer": "Local",
        "model": "Raspberry Pi 4 HAOS Panel",
        "sw_version": __version__,
    }
    state_topic = f"{base}/state"

    def topic(component: str, object_id: str) -> str:
        return f"{discovery_prefix}/{component}/ha_pi_panel/{object_id}/config"

    def common(name: str, unique_id: str) -> dict[str, Any]:
        return {"name": name, "object_id": f"ha_pi_panel_{unique_id}", "unique_id": f"ha_pi_panel_{unique_id}", "availability_topic": availability_topic, "device": device}

    payloads: dict[str, dict[str, Any]] = {}
    payloads[topic("fan", "case_fan")] = {
        **common("Case Fan", "case_fan"),
        "command_topic": f"{base}/fan/percentage/set",
        "percentage_command_topic": f"{base}/fan/percentage/set",
        "percentage_state_topic": state_topic,
        "percentage_value_template": "{{ value_json.fan_requested_percent }}",
        "state_topic": state_topic,
        "state_value_template": "{{ 'ON' if value_json.fan_requested_percent|int > 0 else 'OFF' }}",
        "payload_on": "100",
        "payload_off": "0",
        "speed_range_min": 0,
        "speed_range_max": 100,
    }

    sensors = {
        "cpu_temperature": ("CPU Temperature", "cpu_temp_c", "temperature", "°C"),
        "cpu_load": ("CPU Load", "cpu_load_1m", None, None),
        "memory_percent": ("Memory", "mem_percent", None, "%"),
        "disk_percent": ("Disk", "disk_percent", None, "%"),
        "uptime": ("Uptime", "uptime", None, None),
        "fan_requested_percent": ("Fan Requested", "fan_requested_percent", None, "%"),
        "fan_actual_state": ("Fan Backend State", "fan_backend_state", None, None),
        "display_status": ("Display Status", "display_status", None, None),
    }
    for object_id, (name, key, device_class, unit) in sensors.items():
        payload: dict[str, Any] = {**common(name, object_id), "state_topic": state_topic, "value_template": f"{{{{ value_json.{key} }}}}"}
        if device_class:
            payload["device_class"] = device_class
        if unit:
            payload["unit_of_measurement"] = unit
        payloads[topic("sensor", object_id)] = payload

    payloads[topic("switch", "oled_display")] = {
        **common("OLED Display", "oled_display"),
        "command_topic": f"{base}/display/enabled/set",
        "state_topic": state_topic,
        "value_template": "{{ value_json.display_enabled_state }}",
        "payload_on": "ON",
        "payload_off": "OFF",
    }
    payloads[topic("select", "fan_mode")] = {
        **common("Fan Mode", "fan_mode"),
        "command_topic": f"{base}/fan/mode/set",
        "state_topic": state_topic,
        "value_template": "{{ value_json.fan_mode }}",
        "options": ["auto", "manual", "off"],
    }
    payloads[topic("binary_sensor", "hardware_fault")] = {
        **common("Hardware Fault", "hardware_fault"),
        "state_topic": state_topic,
        "value_template": "{{ value_json.hardware_fault }}",
        "payload_on": "ON",
        "payload_off": "OFF",
        "device_class": "problem",
    }
    return payloads
