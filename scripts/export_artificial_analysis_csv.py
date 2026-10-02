#!/usr/bin/env python3
"""Export all plotted Artificial Analysis model points to a CSV.

This is the deterministic data-refresh entry point used by automation. It wires
the live chart source (`export_source.py`) to the source-agnostic export
pipeline (`export_pipeline.py`) and prints a short summary.

Usage:
    python scripts/export_artificial_analysis_csv.py --output-dir data
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from export_pipeline import ExportOptions, ExportResult, run_export
from export_source import PlaywrightChartSource


def parse_args(argv: list[str] | None = None) -> ExportOptions:
    parser = argparse.ArgumentParser(
        description=(
            "Export all plotted Artificial Analysis model points from the "
            "Intelligence Index vs. Cost per Intelligence Index Task chart."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory to write the CSV output to. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--filter",
        default="",
        help="Optional case-insensitive model-name filter applied after all models are selected.",
    )
    args = parser.parse_args(argv)
    return ExportOptions(output_dir=args.output_dir, model_filter=args.filter)


def print_summary(result: ExportResult) -> None:
    print(f"Selected model count: {result.selected_count}")
    print(f"Plotted row count: {result.plotted_count}")
    print(f"Exported row count: {len(result.points)}")
    print(f"Output path: {result.path}")
    print("Top 10 rows by Intelligence Index:")
    for point in result.points[:10]:
        print(
            f"- {point.model} | intelligence={point.intelligence_index} | "
            f"cost={point.cost_per_task_usd} | id={point.id}"
        )


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    with PlaywrightChartSource() as source:
        result = run_export(source, options)
    print_summary(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
