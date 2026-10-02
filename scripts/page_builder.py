"""Assemble the interactive page from local build-time assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from page_data import build_payload

ASSET_DIR = Path(__file__).resolve().parent / "page_assets"


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


def assemble_page(args: argparse.Namespace) -> str:
    records, config = build_payload(args)
    replacements = {
        "__STYLES__": read_asset("styles.css"),
        "__SCRIPT__": read_asset("app.js"),
        "__DATA__": json.dumps(records, separators=(",", ":")),
        "__CONFIG__": json.dumps(config, separators=(",", ":")),
        "__TITLE__": escape_html(args.title),
        "__SUBTITLE__": escape_html(args.subtitle),
        "__FOOTNOTE__": escape_html(args.footnote),
    }

    html = read_asset("template.html")
    missing = [placeholder for placeholder in replacements if placeholder not in html]
    if missing:
        raise RuntimeError(f"Missing page template placeholders: {', '.join(missing)}")

    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html + "\n"


def build_page(args: argparse.Namespace) -> Path:
    html = assemble_page(args)
    source = Path(args.csv)
    output = Path(args.output) if args.output else source.with_suffix(".html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output
