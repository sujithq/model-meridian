"""Generate an "Intelligence Index vs. Cost per task" chart from a CSV export.

Usage:
    python scripts/generate_chart.py data/data.csv
    python scripts/generate_chart.py data/data.csv -o my-chart.png --min-score 30

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
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullFormatter

from chart_data import (
    build_series,
    cost_ticks,
    filter_points,
    money,
    read_family_colors,
    read_points,
)


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

    colors = read_family_colors(source)

    points = filter_points(points, args.min_score, args.max_cost, args.families)
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
