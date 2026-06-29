from __future__ import annotations

import logging
from pathlib import Path


LOGGER = logging.getLogger(__name__)


def device_exists(path: str) -> bool:
    return Path(path).exists()


def log_hardware_probe(i2c_device: str, gpiochip: str) -> None:
    LOGGER.info("Detected I2C device path %s: %s", i2c_device, "present" if device_exists(i2c_device) else "missing")
    LOGGER.info("Detected GPIO chip %s: %s", gpiochip, "present" if device_exists(gpiochip) else "missing")
