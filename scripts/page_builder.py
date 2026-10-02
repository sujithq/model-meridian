"""Assemble the interactive page from local build-time assets."""

from __future__ import annotations

import json
from dataclasses import dataclass
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


def assemble_page(payload: PagePayload, text: PageText) -> str:
    replacements = {
        "__STYLES__": read_asset("styles.css"),
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
    html = assemble_page(payload, options.text)
    output = options.output or options.source.with_suffix(".html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output
