"""Generate a self-contained Model Meridian page from a CSV export.

Usage:
    python scripts/generate_page.py data/data.csv
    python scripts/generate_page.py data/data.csv -o src/index.html --min-score 30

The page mirrors `generate_chart.py`: same CSV columns, same family and
reasoning-effort parsing, same colours and ordering. It adds hover tooltips with
the full record for each data point, plus live filtering by search text, score,
cost, vendor, family and reasoning effort.

The output file embeds its data and has no external dependencies, so it can be
opened directly from disk or published as a static page.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from chart_data import ChartText, DataFilters
from page_builder import PageOptions, PageText, PageTheme, build_page


def parse_args(argv: list[str] | None = None) -> PageOptions:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("csv", help="Path to the CSV file with the model data")
    parser.add_argument("-o", "--output", help="Output HTML path (default: <csv>.html)")
    parser.add_argument("--title", default="Model Meridian")
    parser.add_argument(
        "--subtitle",
        default="Hover a data point for the full record. Use the filters to narrow the view.",
    )
    parser.add_argument("--xlabel", default="Cost per benchmark task (USD)")
    parser.add_argument("--ylabel", default="Intelligence Index Score")
    parser.add_argument(
        "--footnote",
        default="Data source: Artificial Analysis · Scores and task costs from the source dataset.",
    )
    parser.add_argument("--min-score", type=float, help="Only include models at or above this score")
    parser.add_argument("--max-cost", type=float, help="Only include models at or below this cost")
    parser.add_argument(
        "--families", nargs="+", help="Only include families whose name contains one of these substrings"
    )
    parser.add_argument("--top", type=int, help="Only include the N highest scoring families")
    parser.add_argument(
        "--theme",
        choices=tuple(theme.value for theme in PageTheme),
        default=PageTheme.NATIVE.value,
        help="Page theme (default: native)",
    )
    args = parser.parse_args(argv)
    return PageOptions(
        source=Path(args.csv),
        output=Path(args.output) if args.output else None,
        filters=DataFilters(
            min_score=args.min_score,
            max_cost=args.max_cost,
            families=tuple(args.families or ()),
            top=args.top,
        ),
        text=PageText(
            chart=ChartText(
                title=args.title,
                xlabel=args.xlabel,
                ylabel=args.ylabel,
                footnote=args.footnote,
            ),
            subtitle=args.subtitle,
        ),
        theme=PageTheme(args.theme),
    )


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    output = build_page(options)
    print(f"Page written to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
