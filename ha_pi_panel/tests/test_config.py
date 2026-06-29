import json

import pytest

from app.config import ConfigError, load_config, parse_display_pages, parse_fan_curve


def test_load_config_parses_hex_i2c_address(tmp_path):
    options = tmp_path / "options.json"
    options.write_text(json.dumps({"mock_hardware": True, "display_i2c_address": "0x3D"}), encoding="utf-8")

    config = load_config(options)

    assert config.display_i2c_address == 0x3D
    assert config.mock_hardware is True


def test_display_pages_require_lines_array():
    with pytest.raises(ConfigError):
        parse_display_pages(json.dumps([{"name": "Bad", "lines": "nope"}]))


def test_fan_curve_sorts_and_clamps():
    curve = parse_fan_curve(json.dumps([{"temp_c": 70, "percent": 150}, {"temp_c": 40, "percent": -1}]))

    assert [point.temp_c for point in curve] == [40, 70]
    assert [point.percent for point in curve] == [0, 100]
