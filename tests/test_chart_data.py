from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.helpers import write_fixture_csv

from chart_data import (
    DataFilters,
    DEFAULT_COLOR,
    ModelRecord,
    build_series,
    cost_ticks,
    filter_records,
    money,
    parse_model_name,
    read_model_records,
    shade,
)


class ModelNameParsingTests(unittest.TestCase):
    def test_parses_effort_and_fallback(self) -> None:
        self.assertEqual(
            parse_model_name("Claude Opus 5.5 (max with fallback)"),
            ("Claude Opus 5.5", "max", True),
        )

    def test_parses_effort_with_trailing_source_marker(self) -> None:
        for effort in ("max", "xhigh", "high", "medium", "low"):
            with self.subTest(effort=effort):
                self.assertEqual(
                    parse_model_name(f"Claude Haiku 5.5 ({effort})*"),
                    ("Claude Haiku 5.5", effort, False),
                )

    def test_preserves_model_without_effort(self) -> None:
        self.assertEqual(parse_model_name("Kimi K2.6"), ("Kimi K2.6", "", False))

    def test_entirely_parenthesized_name_is_not_an_empty_family(self) -> None:
        self.assertEqual(parse_model_name("(experimental)"), ("(experimental)", "", False))


class CsvLoadingTests(unittest.TestCase):
    def test_loads_valid_rows_and_skips_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            records = read_model_records(source)

        self.assertEqual([record.model for record in records], [
            "Alpha 1 (low with fallback)",
            "Alpha 1 (max)",
            "Beta",
        ])
        self.assertTrue(records[0].fallback)
        self.assertEqual(records[0].id, "alpha-low")
        self.assertEqual(records[0].model_url, "https://example.test/alpha-low")

    def test_optional_fields_and_extra_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "minimal.csv"
            source.write_text(
                "model,cost_per_task_usd,intelligence_index,color,ignored\n"
                "Minimal,0.5,10,,extra\n",
                encoding="utf-8",
            )
            records = read_model_records(source)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].id, "")
        self.assertEqual(records[0].model_url, "")
        self.assertEqual(records[0].source_color, DEFAULT_COLOR)


class SeriesAndFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            ModelRecord("Alpha (max)", "Alpha", "max", False, 2.0, 50.0, "#1f1f1f"),
            ModelRecord("Alpha (low)", "Alpha", "low", False, 1.0, 40.0, "#ff00ff"),
            ModelRecord("Beta", "Beta", "", False, 0.5, 45.0, "#1f1f1f"),
            ModelRecord("Gamma", "Gamma", "", False, 0.2, 30.0, "#00aa00"),
        ]

    def test_build_series_orders_families_and_efforts(self) -> None:
        series = build_series(self.records)

        self.assertEqual([item.family for item in series], ["Alpha", "Beta", "Gamma"])
        self.assertEqual([point.effort for point in series[0].points], ["low", "max"])
        self.assertEqual(series[0].base_color, "#1f1f1f")
        self.assertNotEqual(series[0].color, series[1].color)

    def test_filter_combines_score_cost_and_family(self) -> None:
        filtered = filter_records(
            self.records,
            DataFilters(
                min_score=40,
                max_cost=1.5,
                families=("alp", "beta"),
            ),
        )

        self.assertEqual([point.model for point in filtered], ["Alpha (low)", "Beta"])
        self.assertEqual(len(self.records), 4)

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
