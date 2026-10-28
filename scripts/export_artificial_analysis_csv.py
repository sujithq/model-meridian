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
from dataclasses import dataclass
from pathlib import Path

from export_pipeline import ExportOptions, ExportResult, run_export
from export_source import PlaywrightChartSource, is_retryable_source_error


@dataclass(frozen=True, slots=True)
class ExportConfig:
    options: ExportOptions
    diagnostics_dir: Path | None = None


def parse_args(argv: list[str] | None = None) -> ExportConfig:
    parser = argparse.ArgumentParser(
        description=(
            "Export all plotted Artificial Analysis model points from the "
            "Intelligence Index vs. Cost per Task, by Model Release chart."
        )
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory to write the CSV output to. Defaults to the current working directory.",
    )
    output.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Atomically update this CSV only when IDs or model content change.",
    )
    parser.add_argument(
        "--filter",
        default="",
        help="Optional case-insensitive model-name filter applied after all models are selected.",
    )
    parser.add_argument(
        "--diagnostics-dir",
        type=Path,
        help="Save browser, network and extraction diagnostics here after export.",
    )
    args = parser.parse_args(argv)
    return ExportConfig(
        options=ExportOptions(
            output_dir=args.output_dir, model_filter=args.filter, output_path=args.output
        ),
        diagnostics_dir=args.diagnostics_dir,
    )


def print_summary(result: ExportResult) -> None:
    print(f"Selected model count: {result.selected_count}")
    print(f"Plotted row count: {result.plotted_count}")
    print(f"Exported row count: {len(result.points)}")
    print(f"Output path: {result.path}")
    if result.changes is not None:
        for label, ids in (
            ("Added", result.changes.added_ids),
            ("Removed", result.changes.removed_ids),
            ("Updated", result.changes.updated_ids),
        ):
            print(f"{label} IDs ({len(ids)}): {', '.join(ids) or 'none'}")
        if not result.changes.has_changes:
            print("No meaningful data changes; the existing CSV was left untouched.")
    print("Top 10 rows by Intelligence Index:")
    for point in result.points[:10]:
        print(
            f"- {point.model} | intelligence={point.intelligence_index} | "
            f"cost={point.cost_per_task_usd} | id={point.id}"
        )


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    with PlaywrightChartSource(diagnostics_dir=config.diagnostics_dir) as source:
        result = run_export(source, config.options)
    print_summary(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(75 if is_retryable_source_error(exc) else 1)
