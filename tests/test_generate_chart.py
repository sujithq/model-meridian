from __future__ import annotations

import tempfile
import unittest
from unittest import mock
from pathlib import Path

from tests.helpers import write_fixture_csv

from chart_data import ChartText, DataFilters
from generate_chart import ChartOptions, FigureOptions, build_chart, parse_args


class StaticChartTests(unittest.TestCase):
    def test_builds_a_png_from_valid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_fixture_csv(root / "models.csv")
            output = root / "chart.png"
            options = ChartOptions(
                source=source,
                output=output,
                filters=DataFilters(),
                text=ChartText(
                    title="Model Meridian",
                    xlabel="Cost",
                    ylabel="Score",
                    footnote="Source attribution",
                ),
                figure=FigureOptions(
                    width=8.0,
                    height=4.5,
                    dpi=80,
                    family_fontsize=8.0,
                    effort_fontsize=6.0,
                ),
            )

            original_open = Path.open
            opened_sources: list[Path] = []

            def tracked_open(path: Path, *args, **kwargs):
                if path == source:
                    opened_sources.append(path)
                return original_open(path, *args, **kwargs)

            with mock.patch.object(Path, "open", tracked_open):
                result = build_chart(options)
            content = result.read_bytes()

        self.assertEqual(result, output)
        self.assertEqual(opened_sources, [source])
        self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(content), 5_000)

    def test_parse_args_translates_cli_values_to_typed_options(self) -> None:
        options = parse_args([
            "models.csv",
            "--families",
            "Alpha",
            "Beta",
            "--no-effort-labels",
        ])

        self.assertIsInstance(options, ChartOptions)
        self.assertEqual(options.source, Path("models.csv"))
        self.assertEqual(options.filters.families, ("Alpha", "Beta"))
        self.assertFalse(options.figure.show_effort_labels)


if __name__ == "__main__":
    unittest.main()
