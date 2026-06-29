from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import threading
import time
from typing import Protocol

from .config import AppConfig, FanCurvePoint, clamp


LOGGER = logging.getLogger(__name__)


class FanBackend(Protocol):
    backend_state: str

    def set_percent(self, percent: int) -> None:
        ...

    def close(self, shutdown_behavior: str) -> None:
        ...


def fan_percent_for_temp(temp_c: float | None, curve: list[FanCurvePoint]) -> int:
    if temp_c is None or not curve:
        return 0
    if temp_c <= curve[0].temp_c:
        return curve[0].percent
    for lower, upper in zip(curve, curve[1:]):
        if lower.temp_c <= temp_c <= upper.temp_c:
            span = upper.temp_c - lower.temp_c
            if span <= 0:
                return upper.percent
            ratio = (temp_c - lower.temp_c) / span
            return clamp(lower.percent + (upper.percent - lower.percent) * ratio, 0, 100)
    return curve[-1].percent


class OffFanBackend:
    backend_state = "off_backend"

    def set_percent(self, percent: int) -> None:
        self.backend_state = "off"

    def close(self, shutdown_behavior: str) -> None:
        pass


class MockFanBackend:
    def __init__(self) -> None:
        self.backend_state = "mock:0"

    def set_percent(self, percent: int) -> None:
        self.backend_state = f"mock:{clamp(percent, 0, 100)}"
        LOGGER.info("Mock fan output set to %s%%", clamp(percent, 0, 100))

    def close(self, shutdown_behavior: str) -> None:
        LOGGER.info("Mock fan shutdown behavior: %s", shutdown_behavior)


class GpioLine:
    def __init__(self, chip: str, line: int, active_high: bool) -> None:
        from periphery import GPIO

        self.active_high = active_high
        self.gpio = GPIO(chip, line, "out")

    def write_active(self, active: bool) -> None:
        self.gpio.write(active if self.active_high else not active)

    def close(self) -> None:
        self.gpio.close()


class GpioOnOffFanBackend:
    def __init__(self, config: AppConfig) -> None:
        self.line = GpioLine(config.fan_gpiochip, config.fan_gpio_line, config.fan_active_high)
        self.backend_state = "off"

    def set_percent(self, percent: int) -> None:
        active = percent > 0
        self.line.write_active(active)
        self.backend_state = "on" if active else "off"

    def close(self, shutdown_behavior: str) -> None:
        if shutdown_behavior == "on":
            self.line.write_active(True)
        elif shutdown_behavior == "off":
            self.line.write_active(False)
        self.line.close()


class SoftwarePwmFanBackend:
    def __init__(self, config: AppConfig) -> None:
        self.line = GpioLine(config.fan_gpiochip, config.fan_gpio_line, config.fan_active_high)
        self.frequency_hz = min(config.fan_pwm_frequency_hz, 100)
        self.percent = 0
        self.backend_state = "software_pwm:0"
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        if config.fan_pwm_frequency_hz > 100:
            LOGGER.warning("software_pwm is capped at 100 Hz inside the add-on; use external hardware for high-frequency PWM.")

    def _loop(self) -> None:
        period = 1.0 / max(1, self.frequency_hz)
        while not self._stop.is_set():
            percent = clamp(self.percent, 0, 100)
            if percent <= 0:
                self.line.write_active(False)
                self._stop.wait(period)
            elif percent >= 100:
                self.line.write_active(True)
                self._stop.wait(period)
            else:
                on_time = period * (percent / 100)
                off_time = period - on_time
                self.line.write_active(True)
                self._stop.wait(on_time)
                self.line.write_active(False)
                self._stop.wait(off_time)

    def set_percent(self, percent: int) -> None:
        self.percent = clamp(percent, 0, 100)
        self.backend_state = f"software_pwm:{self.percent}"

    def close(self, shutdown_behavior: str) -> None:
        self._stop.set()
        self._thread.join(timeout=1)
        if shutdown_behavior == "on":
            self.line.write_active(True)
        elif shutdown_behavior == "off":
            self.line.write_active(False)
        self.line.close()


class SysfsPwmFanBackend:
    def __init__(self, config: AppConfig, pwm_path: str = "/sys/class/pwm/pwmchip0/pwm0") -> None:
        self.path = Path(pwm_path)
        if not self.path.exists():
            raise FileNotFoundError(f"{self.path} is not available")
        self.period_ns = int(1_000_000_000 / max(1, config.fan_pwm_frequency_hz))
        self.backend_state = "sysfs_pwm:0"
        self._write("period", self.period_ns)
        self._write("enable", 1)

    def _write(self, name: str, value: int) -> None:
        (self.path / name).write_text(str(value), encoding="utf-8")

    def set_percent(self, percent: int) -> None:
        percent = clamp(percent, 0, 100)
        self._write("duty_cycle", int(self.period_ns * percent / 100))
        self.backend_state = f"sysfs_pwm:{percent}"

    def close(self, shutdown_behavior: str) -> None:
        if shutdown_behavior == "on":
            self.set_percent(100)
        elif shutdown_behavior == "off":
            self.set_percent(0)
            self._write("enable", 0)


@dataclass
class FanController:
    config: AppConfig
    backend: FanBackend
    mode: str
    requested_percent: int = 0
    actual_percent: int = 0
    last_nonzero: int = 0

    def calculate_target(self, cpu_temp_c: str | float | None) -> int:
        temp = _parse_temp(cpu_temp_c)
        if temp is not None and temp >= self.config.fan_fail_safe_temp_c:
            return 100
        if self.mode == "off":
            return 0
        if self.mode == "manual":
            return self.requested_percent
        return fan_percent_for_temp(temp, self.config.fan_curve)

    def apply(self, percent: int) -> None:
        percent = clamp(percent, 0, 100)
        if 0 < percent < self.config.fan_min_percent:
            percent = self.config.fan_min_percent
        if self.actual_percent == 0 and percent > 0 and self.config.fan_kickstart_seconds > 0:
            self.backend.set_percent(self.config.fan_kickstart_percent)
            time.sleep(self.config.fan_kickstart_seconds)
        self.backend.set_percent(percent)
        self.requested_percent = percent
        self.actual_percent = 100 if self.config.fan_control_method == "gpio_onoff" and percent > 0 else percent
        if percent > 0:
            self.last_nonzero = percent

    def close(self) -> None:
        self.backend.close(self.config.fan_shutdown_behavior)


def _parse_temp(cpu_temp_c: str | float | None) -> float | None:
    if cpu_temp_c is None or cpu_temp_c == "--":
        return None
    try:
        return float(cpu_temp_c)
    except (TypeError, ValueError):
        return None


def create_fan_controller(config: AppConfig) -> FanController:
    if not config.fan_enabled or config.fan_control_method == "off":
        backend: FanBackend = OffFanBackend()
    elif config.mock_hardware:
        backend = MockFanBackend()
    else:
        try:
            if config.fan_control_method == "gpio_onoff":
                backend = GpioOnOffFanBackend(config)
            elif config.fan_control_method == "software_pwm":
                backend = SoftwarePwmFanBackend(config)
            elif config.fan_control_method == "sysfs_pwm":
                backend = SysfsPwmFanBackend(config)
            else:
                backend = OffFanBackend()
        except Exception as exc:
            LOGGER.error("Fan backend initialization failed: %s", exc)
            LOGGER.error("If /dev/gpiochip0 is missing, map it into the add-on or run without fan control.")
            backend = OffFanBackend()
    LOGGER.info("Fan backend selected: %s", config.fan_control_method)
    return FanController(config=config, backend=backend, mode=config.fan_mode, requested_percent=config.fan_manual_percent)
