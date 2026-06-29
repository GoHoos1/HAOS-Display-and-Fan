from app.config import FanCurvePoint, load_config
from app.fan import FanController, MockFanBackend, fan_percent_for_temp


def test_fan_curve_interpolates():
    curve = [FanCurvePoint(50, 0), FanCurvePoint(60, 50), FanCurvePoint(70, 100)]

    assert fan_percent_for_temp(55, curve) == 25
    assert fan_percent_for_temp(65, curve) == 75


def test_fail_safe_forces_full_speed(tmp_path):
    options = tmp_path / "options.json"
    options.write_text('{"mock_hardware": true, "fan_fail_safe_temp_c": 80}', encoding="utf-8")
    config = load_config(options)
    controller = FanController(config=config, backend=MockFanBackend(), mode="off")

    assert controller.calculate_target("81") == 100


def test_minimum_percent_applied(tmp_path):
    options = tmp_path / "options.json"
    options.write_text('{"mock_hardware": true, "fan_min_percent": 25, "fan_kickstart_seconds": 0}', encoding="utf-8")
    config = load_config(options)
    controller = FanController(config=config, backend=MockFanBackend(), mode="manual")

    controller.apply(10)

    assert controller.requested_percent == 25
