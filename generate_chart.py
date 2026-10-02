"""Generate an "Intelligence Index vs. Cost per task" chart from a CSV export.

Usage:
    python generate_chart.py data/data.csv
    python generate_chart.py data/data.csv -o my-chart.png --min-score 30

The CSV is expected to have (at least) the columns:
    model, cost_per_task_usd, intelligence_index, color

Model names may encode a family, a version and a reasoning effort, e.g.
    "GPT-6 Astra (xhigh)"            -> family "GPT-6 Astra", effort "xhigh"
    "Claude Opus 5.5 (max with fallback)" -> family "Claude Opus 5.5", effort "max", fallback
    "Kimi K2.6"                      -> family "Kimi K2.6", no effort
Models that share a family are connected by a line ordered by cost; families with
a single data point are drawn as a labelled diamond marker.
"""

from __future__ import annotations

import argparse
import colorsys
import csv
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullFormatter

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
        return "#444444"
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
            series = Series(point.family, colors.get(point.family, "#444444"))
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


def overlaps(a, b, pad: float = 1.0) -> bool:
    return not (
        a.x1 + pad < b.x0
        or b.x1 + pad < a.x0
        or a.y1 + pad < b.y0
        or b.y1 + pad < a.y0
    )


def place_labels(fig, ax, labels, obstacles=None) -> None:
    """Greedy, collision-aware placement of annotations.

    `labels` is a list of (artist, required) tuples ordered by priority.
    Optional labels that cannot be placed without overlapping are hidden.
    """
    renderer = fig.canvas.get_renderer()
    candidates = []
    for radius in (8, 16, 26, 38, 52, 70):
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            dx = radius * math.cos(rad)
            dy = radius * math.sin(rad)
            ha = "left" if dx > 2 else "right" if dx < -2 else "center"
            va = "bottom" if dy > 2 else "top" if dy < -2 else "center"
            candidates.append((dx, dy, ha, va))
    occupied: list = []
    if obstacles:
        occupied.extend(obstacles)

    for artist, required in labels:
        best = None
        best_overlap = None
        for dx, dy, ha, va in candidates:
            artist.set_position((dx, dy))
            artist.set_ha(ha)
            artist.set_va(va)
            bbox = artist.get_window_extent(renderer=renderer)
            if bbox.x0 < ax.bbox.x0 or bbox.x1 > ax.bbox.x1:
                continue
            if bbox.y0 < ax.bbox.y0 or bbox.y1 > ax.bbox.y1:
                continue
            clashes = sum(1 for other in occupied if overlaps(bbox, other))
            if clashes == 0:
                best = (dx, dy, ha, va, bbox)
                break
            if best_overlap is None or clashes < best_overlap:
                best_overlap = clashes
                best = (dx, dy, ha, va, bbox)

        if best is None:
            artist.set_visible(False)
            continue

        dx, dy, ha, va, bbox = best
        placed_clean = not any(overlaps(bbox, other) for other in occupied)
        if not placed_clean and not required:
            artist.set_visible(False)
            continue
        artist.set_position((dx, dy))
        artist.set_ha(ha)
        artist.set_va(va)
        if artist.arrow_patch is not None:
            artist.arrow_patch.set_visible(math.hypot(dx, dy) > 18)
        occupied.append(bbox)


def build_chart(args: argparse.Namespace) -> Path:
    source = Path(args.csv)
    points = read_points(source)
    if not points:
        raise SystemExit(f"No usable rows found in {source}")

    colors: dict[str, str] = {}
    with source.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("model") or "").strip()
            if not name:
                continue
            family, _, _ = parse_model_name(name)
            colors.setdefault(family, (row.get("color") or "#444444").strip() or "#444444")

    if args.min_score is not None:
        points = [p for p in points if p.score >= args.min_score]
    if args.max_cost is not None:
        points = [p for p in points if p.cost <= args.max_cost]
    if args.families:
        wanted = [f.lower() for f in args.families]
        points = [
            p for p in points if any(w in p.family.lower() for w in wanted)
        ]
    if not points:
        raise SystemExit("All rows were filtered out; relax --min-score/--max-cost/--families")

    series_list = build_series(points, colors)
    if args.top:
        series_list = series_list[: args.top]
        points = [p for s in series_list for p in s.points]

    fig, ax = plt.subplots(figsize=(args.width, args.height), dpi=args.dpi)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    labels: list[tuple[object, bool]] = []

    for series in series_list:
        xs = [p.cost for p in series.points]
        ys = [p.score for p in series.points]
        if len(series.points) > 1:
            order = sorted(range(len(xs)), key=lambda i: xs[i])
            ax.plot(
                [xs[i] for i in order],
                [ys[i] for i in order],
                linestyle=series.linestyle,
                color=series.color,
                linewidth=1.8,
                marker="o",
                markersize=4.5,
                markeredgecolor=series.color,
                zorder=3,
            )
        else:
            ax.plot(
                xs,
                ys,
                linestyle="none",
                color=series.color,
                marker="D",
                markersize=6,
                zorder=3,
            )

        anchor = max(series.points, key=lambda p: (p.score, -p.cost))
        family_label = ax.annotate(
            series.family,
            xy=(anchor.cost, anchor.score),
            xytext=(8, 8),
            textcoords="offset points",
            color=series.color,
            fontsize=args.family_fontsize,
            fontweight="bold",
            zorder=5,
            arrowprops=dict(arrowstyle="-", color=series.color, linewidth=0.7,
                            shrinkA=1, shrinkB=3, alpha=0.7),
        )
        labels.append((family_label, True))

        if not args.no_effort_labels:
            for point in series.points:
                text = point.effort
                if point.fallback:
                    text = f"{text} · fallback" if text else "fallback"
                if not text:
                    continue
                effort_label = ax.annotate(
                    text,
                    xy=(point.cost, point.score),
                    xytext=(5, -9),
                    textcoords="offset points",
                    color="#4a4a4a",
                    fontsize=args.effort_fontsize,
                    zorder=4,
                    arrowprops=dict(arrowstyle="-", color="#9a9a9a", linewidth=0.5,
                                    shrinkA=1, shrinkB=3),
                )
                labels.append((effort_label, False))

    costs = [p.cost for p in points]
    scores = [p.score for p in points]
    ax.set_xscale("log")
    ax.set_xlim(min(costs) / 2.2, max(costs) * 2.6)
    score_pad = max(2.0, (max(scores) - min(scores)) * 0.08)
    ax.set_ylim(min(scores) - score_pad, max(scores) + score_pad * 1.3)

    ticks = cost_ticks(*ax.get_xlim())
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.set_xticklabels([money(t) for t in ticks])
    ax.xaxis.set_minor_formatter(NullFormatter())

    ax.set_xlabel(args.xlabel, fontsize=12, fontweight="bold", labelpad=10)
    ax.set_ylabel(args.ylabel, fontsize=12, fontweight="bold", labelpad=10)
    ax.tick_params(axis="both", labelsize=10, length=0)
    ax.grid(axis="y", color="#e2e2e2", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#bdbdbd")

    if args.title:
        ax.set_title(args.title, fontsize=11, color="#333333", loc="left", pad=28)
    ax.text(
        0.0, 1.015, "HIGHER SCORES ARE BETTER",
        transform=ax.transAxes, fontsize=8, color="#555555", fontweight="bold",
    )
    ax.text(
        1.0, 1.015, "LOGARITHMIC COST SCALE",
        transform=ax.transAxes, fontsize=8, color="#555555", fontweight="bold",
        ha="right",
    )
    if args.footnote:
        ax.text(
            0.0, -0.13, args.footnote,
            transform=ax.transAxes, fontsize=9.5, color="#555555",
        )

    fig.tight_layout(rect=(0.01, 0.05, 0.99, 0.97))
    fig.canvas.draw()
    marker_boxes = []
    for point in points:
        x, y = ax.transData.transform((point.cost, point.score))
        marker_boxes.append(matplotlib.transforms.Bbox.from_bounds(x - 4, y - 4, 8, 8))
    place_labels(fig, ax, labels, marker_boxes)

    output = Path(args.output) if args.output else source.with_suffix(".png")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=args.dpi, facecolor=fig.get_facecolor())
    plt.close(fig)
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", help="Path to the CSV file with the model data")
    parser.add_argument("-o", "--output", help="Output image path (default: <csv>.png)")
    parser.add_argument("--title", default="Artificial Analysis Intelligence Index")
    parser.add_argument("--xlabel", default="Cost per benchmark task (USD)")
    parser.add_argument("--ylabel", default="Artificial Analysis Intelligence Score")
    parser.add_argument("--footnote", default="Courtesy of Artificial Analysis · Scores and task costs from the source dataset.")
    parser.add_argument("--min-score", type=float, help="Only plot models at or above this intelligence index")
    parser.add_argument("--max-cost", type=float, help="Only plot models at or below this cost per task")
    parser.add_argument("--families", nargs="+", help="Only plot families whose name contains one of these substrings")
    parser.add_argument("--top", type=int, help="Only plot the N highest scoring families")
    parser.add_argument("--no-effort-labels", action="store_true", help="Hide the per-point reasoning effort labels")
    parser.add_argument("--width", type=float, default=16.0, help="Figure width in inches (default 16)")
    parser.add_argument("--height", type=float, default=9.0, help="Figure height in inches (default 9)")
    parser.add_argument("--dpi", type=int, default=140)
    parser.add_argument("--family-fontsize", type=float, default=9.5)
    parser.add_argument("--effort-fontsize", type=float, default=7.5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = build_chart(args)
    print(f"Chart written to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
