from __future__ import annotations

import logging
from typing import Protocol

from PIL import Image

from .config import AppConfig


LOGGER = logging.getLogger(__name__)


class DisplayDriver(Protocol):
    status: str

    def show(self, image: Image.Image, text_lines: list[str]) -> None:
        ...

    def blank(self) -> None:
        ...

    def close(self) -> None:
        ...


class MockDisplay:
    status = "mock"

    def show(self, image: Image.Image, text_lines: list[str]) -> None:
        LOGGER.info("Mock OLED page:\n%s", "\n".join(text_lines))

    def blank(self) -> None:
        LOGGER.info("Mock OLED blanked")

    def close(self) -> None:
        pass


class NoopDisplay:
    def __init__(self, status: str = "disabled") -> None:
        self.status = status

    def show(self, image: Image.Image, text_lines: list[str]) -> None:
        pass

    def blank(self) -> None:
        pass

    def close(self) -> None:
        pass


class LumaDisplay:
    def __init__(self, config: AppConfig) -> None:
        from luma.core.interface.serial import i2c
        from luma.oled.device import sh1106, ssd1306

        port = 1
        if config.display_i2c_device.startswith("/dev/i2c-"):
            port = int(config.display_i2c_device.rsplit("-", 1)[1])
        serial = i2c(port=port, address=config.display_i2c_address)
        device_cls = sh1106 if config.display_type == "sh1106_128x64" else ssd1306
        self.device = device_cls(serial, width=config.display_width, height=config.display_height, rotate=0)
        self.device.contrast(config.display_contrast)
        if config.display_invert:
            self.device.command(0xA7)
        self.status = "online"

    def show(self, image: Image.Image, text_lines: list[str]) -> None:
        self.device.display(image)

    def blank(self) -> None:
        self.device.clear()

    def close(self) -> None:
        try:
            self.device.clear()
        except Exception:
            LOGGER.debug("OLED cleanup failed", exc_info=True)


def create_display(config: AppConfig) -> DisplayDriver:
    if not config.display_enabled:
        return NoopDisplay("disabled")
    if config.mock_hardware:
        return MockDisplay()
    try:
        display = LumaDisplay(config)
        LOGGER.info("OLED initialized")
        return display
    except Exception as exc:
        LOGGER.error("OLED initialization failed: %s", exc)
        LOGGER.error("If /dev/i2c-1 is missing, enable I2C on Home Assistant OS and restart the host.")
        return NoopDisplay("fault")
