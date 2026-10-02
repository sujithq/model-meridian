"""Build the serialized data consumed by the interactive page."""

from __future__ import annotations

import argparse
from pathlib import Path

from chart_data import (
    EFFORT_ORDER,
    build_series,
    filter_records,
    read_model_records,
)

DASH_PATTERNS = ["", "7 4", "9 3 2 3", "3 2 1 2"]


def dash_for(linestyle: object, index: int) -> str:
    """Translate a matplotlib-style line style into an SVG dash array."""
    if linestyle == "-":
        return ""
    if linestyle == "--":
        return DASH_PATTERNS[1]
    if linestyle == "-.":
        return DASH_PATTERNS[2]
    return DASH_PATTERNS[index % len(DASH_PATTERNS)]


def build_payload(args: argparse.Namespace) -> tuple[list[dict], dict]:
    source = Path(args.csv)
    model_records = read_model_records(source)
    if not model_records:
        raise SystemExit(f"No usable rows found in {source}")

    model_records = filter_records(
        model_records,
        args.min_score,
        args.max_cost,
        args.families,
    )
    if not model_records:
        raise SystemExit("All rows were filtered out; relax --min-score/--max-cost/--families")

    series_list = build_series(model_records)
    if args.top:
        series_list = series_list[: args.top]

    records: list[dict] = []
    family_meta: list[dict] = []
    for index, series in enumerate(series_list):
        dash = dash_for(series.linestyle, index)
        family_meta.append({"name": series.family, "color": series.color})
        for point in series.points:
            records.append(
                {
                    "model": point.model,
                    "family": point.family,
                    "effort": point.effort,
                    "fallback": point.fallback,
                    "cost": round(point.cost, 6),
                    "score": round(point.score, 4),
                    "color": series.color,
                    "dash": dash,
                    "url": point.model_url,
                }
            )

    if not records:
        raise SystemExit("No models remain after filtering")

    efforts = sorted(
        {record["effort"] or "(none)" for record in records},
        key=lambda effort: (EFFORT_ORDER.get(effort.lower(), 99), effort),
    )
    config = {
        "xlabel": args.xlabel,
        "ylabel": args.ylabel,
        "efforts": efforts,
        "families": sorted(family_meta, key=lambda family: family["name"].lower()),
        "minScore": min(record["score"] for record in records),
        "maxScore": max(record["score"] for record in records),
        "minCost": min(record["cost"] for record in records),
        "maxCost": max(record["cost"] for record in records),
    }
    return records, config
