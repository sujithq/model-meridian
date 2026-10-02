"""Shared CSV loading, model-name parsing and series building.

Used by both the static image generator (`generate_chart.py`) and the
interactive page generator (`generate_page.py`) so that both renderers group,
order and colour models identically.
"""

from __future__ import annotations

import colorsys
import csv
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

NAME_RE = re.compile(r"^(?P<family>.*?)\s*\((?P<effort>[^)]*)\)\s*$")
FALLBACK_RE = re.compile(r"\s*with\s+fallback\s*", re.IGNORECASE)

EFFORT_ORDER = {
    "non-reasoning": 0,
    "reasoning": 1,
    "minimal": 2,
    "low": 3,
    "medium": 4,
    "high": 5,
    "xhigh": 6,
    "max": 7,
}

LINE_STYLES = ["-", "--", "-.", (0, (3, 1, 1, 1))]

DEFAULT_COLOR = "#444444"


@dataclass
class Point:
    model: str
    family: str
    effort: str
    fallback: bool
    cost: float
    score: float


@dataclass
class Series:
    family: str
    base_color: str
    points: list[Point] = field(default_factory=list)
    color: str = "#333333"
    linestyle: object = "-"


def parse_model_name(name: str) -> tuple[str, str, bool]:
    """Split a model name into (family, reasoning effort, fallback flag)."""
    match = NAME_RE.match(name.strip())
    if not match:
        return name.strip(), "", False
    family = match.group("family").strip()
    effort = match.group("effort").strip()
    fallback = bool(FALLBACK_RE.search(effort))
    if fallback:
        effort = FALLBACK_RE.sub(" ", effort).strip()
    if not family:  # e.g. a name that is entirely parenthesised
        return name.strip(), "", fallback
    return family, effort, fallback


def effort_sort_key(point: Point) -> tuple[int, float]:
    return (EFFORT_ORDER.get(point.effort.lower(), 99), point.cost)


def read_points(path: Path) -> list[Point]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    points: list[Point] = []
    for row in rows:
        name = (row.get("model") or "").strip()
        if not name:
            continue
        try:
            cost = float(row["cost_per_task_usd"])
            score = float(row["intelligence_index"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(cost) or not math.isfinite(score) or cost <= 0:
            continue
        family, effort, fallback = parse_model_name(name)
        points.append(Point(name, family, effort, fallback, cost, score))
    return points


def read_family_colors(path: Path) -> dict[str, str]:
    """Map each model family to the first colour its rows declare."""
    colors: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("model") or "").strip()
            if not name:
                continue
            family, _, _ = parse_model_name(name)
            colors.setdefault(
                family, (row.get("color") or DEFAULT_COLOR).strip() or DEFAULT_COLOR
            )
    return colors


def shade(hex_color: str, lightness_delta: float, hue_delta: float, variant: int = 0) -> str:
    """Derive a readable variant of a vendor colour.

    Families sharing a vendor colour need to stay distinguishable; near-grey
    vendor colours (e.g. OpenAI black) get their own hue palette instead.
    """
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(ch * 2 for ch in hex_color)
    try:
        r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return DEFAULT_COLOR
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if s < 0.12:
        if variant == 0:
            return "#" + hex_color
        grey_hues = [0.60, 0.78, 0.33, 0.08, 0.50, 0.92, 0.16, 0.70, 0.42]
        h = grey_hues[(variant - 1) % len(grey_hues)]
        s = 0.62
        l = 0.30 + 0.05 * (((variant - 1) // len(grey_hues)) % 3)
    else:
        h = (h + hue_delta) % 1.0
        l = min(0.72, max(0.18, l + lightness_delta))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


def build_series(points: list[Point], colors: dict[str, str]) -> list[Series]:
    grouped: dict[str, Series] = {}
    for point in points:
        series = grouped.get(point.family)
        if series is None:
            series = Series(point.family, colors.get(point.family, DEFAULT_COLOR))
            grouped[point.family] = series
        series.points.append(point)

    for series in grouped.values():
        series.points.sort(key=effort_sort_key)

    # Families sharing a vendor colour get distinct shades + line styles.
    by_color: dict[str, list[Series]] = {}
    for series in grouped.values():
        by_color.setdefault(series.base_color.lower(), []).append(series)

    spread = [0.0, -0.14, 0.14, -0.26, 0.26, -0.07, 0.07, -0.34, 0.34]
    hues = [0.0, 0.035, -0.035, 0.07, -0.07, 0.105, -0.105, 0.14, -0.14]
    for variants in by_color.values():
        variants.sort(key=lambda s: -max(p.score for p in s.points))
        for index, series in enumerate(variants):
            series.color = shade(
                series.base_color,
                spread[index % len(spread)],
                hues[index % len(hues)],
                index,
            )
            series.linestyle = LINE_STYLES[index % len(LINE_STYLES)]

    return sorted(grouped.values(), key=lambda s: -max(p.score for p in s.points))


def filter_points(
    points: list[Point],
    min_score: float | None = None,
    max_cost: float | None = None,
    families: list[str] | None = None,
) -> list[Point]:
    if min_score is not None:
        points = [p for p in points if p.score >= min_score]
    if max_cost is not None:
        points = [p for p in points if p.cost <= max_cost]
    if families:
        wanted = [f.lower() for f in families]
        points = [p for p in points if any(w in p.family.lower() for w in wanted)]
    return points


def cost_ticks(lo: float, hi: float) -> list[float]:
    candidates = [
        0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
        1, 2, 5, 10, 20, 50, 100, 200, 500,
    ]
    ticks = [t for t in candidates if lo <= t <= hi]
    return ticks or [lo, hi]


def money(value: float) -> str:
    if value >= 1:
        return f"${value:,.0f}"
    if value >= 0.01:
        return f"${value:.2f}"
    return f"${value:.3f}"
