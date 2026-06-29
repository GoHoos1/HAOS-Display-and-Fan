from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from .config import DisplayPage


HA_TOKEN_RE = re.compile(r"\{ha:([^}]+)\}")
TOKEN_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


@dataclass(frozen=True)
class RenderResult:
    image: Image.Image
    text_lines: list[str]


def extract_ha_entities(pages: list[DisplayPage]) -> set[str]:
    entities: set[str] = set()
    for page in pages:
        for line in page.lines:
            entities.update(match.group(1) for match in HA_TOKEN_RE.finditer(line))
    return entities


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/ttf-dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def fit_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if _text_width(draw, text, font) <= max_width:
        return text
    ellipsis = "..."
    while text and _text_width(draw, text + ellipsis, font) > max_width:
        text = text[:-1]
    return (text + ellipsis) if text else ellipsis


def render_template(line: str, tokens: dict[str, str], ha_state: Callable[[str], str] | None = None) -> str:
    def replace_ha(match: re.Match[str]) -> str:
        return ha_state(match.group(1)) if ha_state else "--"

    rendered = HA_TOKEN_RE.sub(replace_ha, line)

    def replace_token(match: re.Match[str]) -> str:
        return tokens.get(match.group(1), "--")

    return TOKEN_RE.sub(replace_token, rendered)


def render_page(
    page: DisplayPage,
    width: int,
    height: int,
    rotate: int,
    tokens: dict[str, str],
    ha_state: Callable[[str], str] | None = None,
) -> RenderResult:
    image = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(image)
    line_height = 10 if height <= 32 else 12
    font_size = 9 if height <= 32 else 10
    font = _load_font(font_size)
    max_lines = max(1, height // line_height)
    rendered_lines = [fit_text(draw, render_template(line, tokens, ha_state), font, width - 2) for line in page.lines[:max_lines]]
    for index, text in enumerate(rendered_lines):
        draw.text((0, index * line_height), text, font=font, fill=255)
    if rotate:
        image = image.rotate(rotate, expand=True)
    return RenderResult(image=image, text_lines=rendered_lines)
