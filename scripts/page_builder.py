"""Assemble the interactive page from local build-time assets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from chart_data import ChartText, DataFilters
from page_data import PagePayload, build_payload

ASSET_DIR = Path(__file__).resolve().parent / "page_assets"
SCRIPT_ASSETS = (
    "chart_math.js",
    "filter_state.js",
    "chart_renderer.js",
    "app.js",
)


class PageTheme(str, Enum):
    NATIVE = "native"


@dataclass(frozen=True, slots=True)
class ThemeSpec:
    styles: tuple[str, ...]


THEME_SPECS = {
    PageTheme.NATIVE: ThemeSpec(styles=("base.css", "themes/native.css")),
}


@dataclass(frozen=True, slots=True)
class PageText:
    chart: ChartText
    subtitle: str


@dataclass(frozen=True, slots=True)
class PageOptions:
    source: Path
    output: Path | None
    filters: DataFilters
    text: PageText
    theme: PageTheme = PageTheme.NATIVE


def escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def read_asset(name: str) -> str:
    path = ASSET_DIR / name
    try:
        return path.read_text(encoding="utf-8").rstrip("\n")
    except OSError as error:
        raise RuntimeError(f"Unable to read page asset {path}: {error}") from error


def read_script() -> str:
    return "\n\n".join(read_asset(name) for name in SCRIPT_ASSETS)


def read_styles(theme: PageTheme) -> str:
    try:
        spec = THEME_SPECS[theme]
    except KeyError as error:
        raise ValueError(f"Unsupported page theme: {theme}") from error
    return "\n\n".join(read_asset(name) for name in spec.styles)


def assemble_page(
    payload: PagePayload,
    text: PageText,
    theme: PageTheme = PageTheme.NATIVE,
) -> str:
    replacements = {
        "__STYLES__": read_styles(theme),
        "__SCRIPT__": read_script(),
        "__DATA__": json.dumps(payload.records, separators=(",", ":")),
        "__CONFIG__": json.dumps(payload.config, separators=(",", ":")),
        "__TITLE__": escape_html(text.chart.title),
        "__SUBTITLE__": escape_html(text.subtitle),
        "__FOOTNOTE__": escape_html(text.chart.footnote),
    }

    html = read_asset("template.html")
    missing = [placeholder for placeholder in replacements if placeholder not in html]
    if missing:
        raise RuntimeError(f"Missing page template placeholders: {', '.join(missing)}")

    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html + "\n"


def build_page(options: PageOptions) -> Path:
    payload = build_payload(options.source, options.filters, options.text.chart)
    html = assemble_page(payload, options.text, options.theme)
    output = options.output or options.source.with_suffix(".html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output
