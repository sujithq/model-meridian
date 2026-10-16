from __future__ import annotations

import tempfile
import unittest
from unittest import mock
from pathlib import Path

import matplotlib.pyplot as plt

from tests.helpers import write_fixture_csv

from chart_data import ChartText, CostScale, DataFilters
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
                cost_scale=CostScale.LINEAR,
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

            with (
                mock.patch.object(Path, "open", tracked_open),
                mock.patch("generate_chart.plt.close", wraps=plt.close) as close,
            ):
                result = build_chart(options)
            figure = close.call_args.args[0]
            axis = figure.axes[0]
            self.assertEqual(axis.get_xscale(), "linear")
            self.assertEqual(axis.get_xlim(), (0, 2.2))
            self.assertEqual(list(axis.get_xticks()), [0, 0.5, 1, 1.5, 2])
            positions = [axis.transData.transform((cost, 45))[0] for cost in (0, 1, 2)]
            self.assertAlmostEqual(positions[1] - positions[0], positions[2] - positions[1])
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
        self.assertEqual(options.cost_scale, CostScale.LOGARITHMIC)
        self.assertEqual(options.filters.families, ("Alpha", "Beta"))
        self.assertFalse(options.figure.show_effort_labels)

    def test_parse_args_selects_linear_cost_scale(self) -> None:
        options = parse_args(["models.csv", "--x-scale", "linear"])

        self.assertEqual(options.cost_scale, CostScale.LINEAR)

    def test_default_chart_uses_logarithmic_cost_scale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            options = ChartOptions(
                source=source,
                output=Path(directory) / "chart.png",
                cost_scale=CostScale.LOGARITHMIC,
                filters=DataFilters(),
                text=ChartText("Title", "Cost", "Score", ""),
                figure=FigureOptions(width=8, height=4.5, dpi=80),
            )
            with mock.patch("generate_chart.plt.close", wraps=plt.close) as close:
                build_chart(options)

        axis = close.call_args.args[0].axes[0]
        self.assertEqual(axis.get_xscale(), "log")
        self.assertEqual(axis.get_xlim(), (0.5 / 2.2, 2.0 * 2.2))
        positions = [axis.transData.transform((cost, 45))[0] for cost in (0.5, 1, 2)]
        self.assertAlmostEqual(positions[1] - positions[0], positions[2] - positions[1])


if __name__ == "__main__":
    unittest.main()
