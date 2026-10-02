from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.helpers import write_fixture_csv

from chart_data import (
    DEFAULT_COLOR,
    Point,
    build_series,
    cost_ticks,
    filter_points,
    money,
    parse_model_name,
    read_family_colors,
    read_points,
    shade,
)


class ModelNameParsingTests(unittest.TestCase):
    def test_parses_effort_and_fallback(self) -> None:
        self.assertEqual(
            parse_model_name("Claude Opus 5.5 (max with fallback)"),
            ("Claude Opus 5.5", "max", True),
        )

    def test_preserves_model_without_effort(self) -> None:
        self.assertEqual(parse_model_name("Kimi K2.6"), ("Kimi K2.6", "", False))

    def test_entirely_parenthesized_name_is_not_an_empty_family(self) -> None:
        self.assertEqual(parse_model_name("(experimental)"), ("(experimental)", "", False))


class CsvLoadingTests(unittest.TestCase):
    def test_loads_valid_rows_and_skips_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            points = read_points(source)

        self.assertEqual([point.model for point in points], [
            "Alpha 1 (low with fallback)",
            "Alpha 1 (max)",
            "Beta",
        ])
        self.assertTrue(points[0].fallback)

    def test_uses_first_declared_family_color(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            colors = read_family_colors(source)

        self.assertEqual(colors["Alpha 1"], "#1f1f1f")
        self.assertEqual(colors["Beta"], "#ff0000")


class SeriesAndFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.points = [
            Point("Alpha (max)", "Alpha", "max", False, 2.0, 50.0),
            Point("Alpha (low)", "Alpha", "low", False, 1.0, 40.0),
            Point("Beta", "Beta", "", False, 0.5, 45.0),
            Point("Gamma", "Gamma", "", False, 0.2, 30.0),
        ]

    def test_build_series_orders_families_and_efforts(self) -> None:
        series = build_series(
            self.points,
            {"Alpha": "#1f1f1f", "Beta": "#1f1f1f", "Gamma": "#00aa00"},
        )

        self.assertEqual([item.family for item in series], ["Alpha", "Beta", "Gamma"])
        self.assertEqual([point.effort for point in series[0].points], ["low", "max"])
        self.assertNotEqual(series[0].color, series[1].color)

    def test_filter_combines_score_cost_and_family(self) -> None:
        filtered = filter_points(
            self.points,
            min_score=40,
            max_cost=1.5,
            families=["alp", "beta"],
        )

        self.assertEqual([point.model for point in filtered], ["Alpha (low)", "Beta"])
        self.assertEqual(len(self.points), 4)

    def test_formatting_and_tick_fallbacks(self) -> None:
        self.assertEqual(money(2.4), "$2")
        self.assertEqual(money(0.125), "$0.12")
        self.assertEqual(money(0.005), "$0.005")
        self.assertEqual(cost_ticks(0.01, 0.05), [0.01, 0.02, 0.05])
        self.assertEqual(cost_ticks(601, 700), [601, 700])

    def test_invalid_color_uses_default(self) -> None:
        self.assertEqual(shade("not-a-color", 0, 0), DEFAULT_COLOR)


if __name__ == "__main__":
    unittest.main()
