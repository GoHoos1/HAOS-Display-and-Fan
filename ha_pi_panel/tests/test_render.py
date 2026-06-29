from app.config import DisplayPage
from app.render import extract_ha_entities, render_page, render_template


def test_template_renders_tokens_and_missing_ha_state():
    line = "CPU {cpu_temp_c} Outside {ha:sensor.outdoor_temperature}"

    assert render_template(line, {"cpu_temp_c": "42.0"}) == "CPU 42.0 Outside --"


def test_template_renders_ha_state():
    line = "Outside {ha:sensor.outdoor_temperature}"

    assert render_template(line, {}, lambda entity_id: "72") == "Outside 72"


def test_extract_ha_entities():
    pages = [DisplayPage("Home", ["A {ha:sensor.one}", "B {ha:weather.home}"])]

    assert extract_ha_entities(pages) == {"sensor.one", "weather.home"}


def test_render_128x32_limits_lines():
    page = DisplayPage("Small", ["1", "2", "3", "4", "5"])

    result = render_page(page, 128, 32, 0, {}, None)

    assert result.image.size == (128, 32)
    assert len(result.text_lines) <= 3
