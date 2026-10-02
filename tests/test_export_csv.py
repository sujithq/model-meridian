from __future__ import annotations

import csv
import math
import tempfile
import unittest
from pathlib import Path

from tests.helpers import FIELDNAMES

from export_artificial_analysis_csv import (
    apply_model_filter,
    sort_rows,
    validate_csv,
    write_csv,
)


def export_rows() -> list[dict]:
    return [
        {
            "id": "beta",
            "model": "Beta",
            "cost_per_task_usd": 2.0,
            "intelligence_index": 50.0,
            "model_url": "https://example.test/beta",
            "color": "#222222",
        },
        {
            "id": "alpha-expensive",
            "model": "Alpha Z",
            "cost_per_task_usd": 3.0,
            "intelligence_index": 50.0,
            "model_url": "https://example.test/alpha-z",
            "color": "#111111",
        },
        {
            "id": "alpha-cheap",
            "model": "Alpha A",
            "cost_per_task_usd": 1.0,
            "intelligence_index": 50.0,
            "model_url": "https://example.test/alpha-a",
            "color": "#111111",
        },
        {
            "id": "gamma",
            "model": "Gamma",
            "cost_per_task_usd": 0.5,
            "intelligence_index": 40.0,
            "model_url": "",
            "color": "#333333",
        },
    ]


def write_raw_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


class ExportTransformationTests(unittest.TestCase):
    def test_filters_case_insensitively(self) -> None:
        rows = apply_model_filter(export_rows(), "ALPHA")
        self.assertEqual({row["id"] for row in rows}, {"alpha-expensive", "alpha-cheap"})

    def test_sorts_by_score_cost_then_model(self) -> None:
        rows = sort_rows(export_rows())
        self.assertEqual(
            [row["id"] for row in rows],
            ["alpha-cheap", "beta", "alpha-expensive", "gamma"],
        )


class ExportCsvTests(unittest.TestCase):
    def test_write_csv_adds_bom_provenance_and_valid_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_csv(sort_rows(export_rows()), Path(directory))
            raw = path.read_bytes()
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["source_chart"] for row in rows))
        self.assertTrue(all(row["source_page"] for row in rows))
        self.assertTrue(all(row["extracted_at"].endswith("Z") for row in rows))
        self.assertTrue(all(math.isfinite(float(row["cost_per_task_usd"])) for row in rows))

    def test_validate_csv_rejects_duplicate_ids(self) -> None:
        row = {
            "id": "duplicate",
            "model": "Model",
            "cost_per_task_usd": "1",
            "intelligence_index": "2",
            "model_url": "",
            "color": "#000000",
            "source_chart": "Chart",
            "source_page": "https://example.test",
            "extracted_at": "2026-01-01T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.csv"
            write_raw_csv(path, [row, row])
            with self.assertRaisesRegex(ValueError, "duplicate ids"):
                validate_csv(path, 2)

    def test_validate_csv_rejects_non_finite_values(self) -> None:
        row = {
            "id": "model",
            "model": "Model",
            "cost_per_task_usd": "nan",
            "intelligence_index": "2",
            "model_url": "",
            "color": "#000000",
            "source_chart": "Chart",
            "source_page": "https://example.test",
            "extracted_at": "2026-01-01T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "non-finite.csv"
            write_raw_csv(path, [row])
            with self.assertRaisesRegex(ValueError, "non-finite"):
                validate_csv(path, 1)

    def test_validate_csv_checks_expected_count(self) -> None:
        row = {
            "id": "model",
            "model": "Model",
            "cost_per_task_usd": "1",
            "intelligence_index": "2",
            "model_url": "",
            "color": "#000000",
            "source_chart": "Chart",
            "source_page": "https://example.test",
            "extracted_at": "2026-01-01T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "count.csv"
            write_raw_csv(path, [row])
            with self.assertRaisesRegex(ValueError, "does not match expected"):
                validate_csv(path, 2)


if __name__ == "__main__":
    unittest.main()
