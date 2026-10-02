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
    PICO = "pico"
    BULMA = "bulma"
    TAILWIND = "tailwind"


@dataclass(frozen=True, slots=True)
class ThemeSpec:
    styles: tuple[str, ...]
    classes: tuple[tuple[str, str], ...] = ()

    def class_for(self, role: str) -> str:
        return dict(self.classes).get(role, "")


THEME_SPECS = {
    PageTheme.NATIVE: ThemeSpec(styles=("base.css", "themes/native.css")),
    PageTheme.PICO: ThemeSpec(
        styles=(
            "base.css",
            "vendor/pico-2.1.1/pico.min.css",
            "themes/pico.css",
        )
    ),
    PageTheme.BULMA: ThemeSpec(
        styles=(
            "base.css",
            "vendor/bulma-1.0.4/bulma.min.css",
            "themes/bulma.css",
        ),
        classes=(
            ("panel", "box"),
            ("search", "input is-small"),
            ("actions", "buttons"),
            ("button", "button is-small"),
            ("chart", "box"),
        ),
    ),
    PageTheme.TAILWIND: ThemeSpec(
        styles=(
            "base.css",
            "vendor/tailwind-4.3.3/tailwind.min.css",
        )
    ),
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
    return "\n\n".join(read_asset(name) for name in theme_spec(theme).styles)


def theme_spec(theme: PageTheme) -> ThemeSpec:
    try:
        return THEME_SPECS[theme]
    except KeyError as error:
        raise ValueError(f"Unsupported page theme: {theme}") from error


def assemble_page(
    payload: PagePayload,
    text: PageText,
    theme: PageTheme = PageTheme.NATIVE,
) -> str:
    spec = theme_spec(theme)
    replacements = {
        "__STYLES__": read_styles(theme),
        "__SCRIPT__": read_script(),
        "__DATA__": json.dumps(payload.records, separators=(",", ":")),
        "__CONFIG__": json.dumps(payload.config, separators=(",", ":")),
        "__TITLE__": escape_html(text.chart.title),
        "__SUBTITLE__": escape_html(text.subtitle),
        "__FOOTNOTE__": escape_html(text.chart.footnote),
        "__PANEL_CLASSES__": spec.class_for("panel"),
        "__SEARCH_CLASSES__": spec.class_for("search"),
        "__ACTION_CLASSES__": spec.class_for("actions"),
        "__BUTTON_CLASSES__": spec.class_for("button"),
        "__CHART_CLASSES__": spec.class_for("chart"),
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
