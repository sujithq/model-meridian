from __future__ import annotations

import csv
import importlib.util
import math
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from tests.helpers import FIELDNAMES, ROOT, SCRIPTS

from export_pipeline import (
    ExportOptions,
    ExportPoint,
    ModelSource,
    SourceMetadata,
    apply_model_filter,
    paris_now,
    run_export,
    sort_points,
    validate_csv,
    write_csv,
)

FAKE_METADATA = SourceMetadata(
    chart="Fake Chart",
    page="https://example.test/models",
    slug="fake-chart-models",
)


def export_points() -> list[ExportPoint]:
    return [
        ExportPoint("beta", "Beta", 2.0, 50.0, "https://example.test/beta", "#222222"),
        ExportPoint(
            "alpha-expensive", "Alpha Z", 3.0, 50.0, "https://example.test/alpha-z", "#111111"
        ),
        ExportPoint(
            "alpha-cheap", "Alpha A", 1.0, 50.0, "https://example.test/alpha-a", "#111111"
        ),
        ExportPoint("gamma", "Gamma", 0.5, 40.0, "", "#333333"),
    ]


class FakeSource:
    """In-memory `ModelSource` used to exercise the pipeline without a browser."""

    def __init__(self, points: list[ExportPoint], selected_count: int | None = None) -> None:
        self._points = points
        self._selected_count = len(points) if selected_count is None else selected_count
        self.calls: list[str] = []

    @property
    def metadata(self) -> SourceMetadata:
        return FAKE_METADATA

    def select_all(self) -> int:
        self.calls.append("select_all")
        return self._selected_count

    def extract_points(self) -> list[ExportPoint]:
        self.calls.append("extract_points")
        return list(self._points)


def write_raw_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


class ExportTransformationTests(unittest.TestCase):
    def test_filters_case_insensitively(self) -> None:
        points = apply_model_filter(export_points(), "ALPHA")
        self.assertEqual({point.id for point in points}, {"alpha-expensive", "alpha-cheap"})

    def test_sorts_by_score_cost_then_model(self) -> None:
        points = sort_points(export_points())
        self.assertEqual(
            [point.id for point in points],
            ["alpha-cheap", "beta", "alpha-expensive", "gamma"],
        )


class ExportCsvTests(unittest.TestCase):
    def test_write_csv_adds_bom_provenance_and_valid_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_csv(sort_points(export_points()), Path(directory), FAKE_METADATA)
            raw = path.read_bytes()
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["source_chart"] == FAKE_METADATA.chart for row in rows))
        self.assertTrue(all(row["source_page"] == FAKE_METADATA.page for row in rows))
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


class RunExportTests(unittest.TestCase):
    def test_drives_the_source_then_writes_a_sorted_deduped_csv(self) -> None:
        duplicated = export_points() + [export_points()[0]]
        source = FakeSource(duplicated, selected_count=171)
        with tempfile.TemporaryDirectory() as directory:
            result = run_export(source, ExportOptions(output_dir=Path(directory)))
            with result.path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(source.calls, ["select_all", "extract_points"])
        self.assertEqual(result.selected_count, 171)
        self.assertEqual(result.plotted_count, 5)
        self.assertEqual(
            [row["id"] for row in rows],
            ["alpha-cheap", "beta", "alpha-expensive", "gamma"],
        )
        self.assertTrue(all(row["source_page"] == FAKE_METADATA.page for row in rows))

    def test_uses_the_source_slug_and_local_date_for_the_filename(self) -> None:
        source = FakeSource(export_points())
        with tempfile.TemporaryDirectory() as directory:
            result = run_export(source, ExportOptions(output_dir=Path(directory)))

        expected = f"{FAKE_METADATA.slug}-{paris_now().strftime('%Y-%m-%d')}.csv"
        self.assertEqual(result.path.name, expected)

    def test_rejects_a_source_that_plots_nothing(self) -> None:
        source = FakeSource([])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "no extractable model payloads"):
                run_export(source, ExportOptions(output_dir=Path(directory)))

    def test_rejects_a_filter_that_matches_nothing(self) -> None:
        source = FakeSource(export_points())
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "matched no plotted models"):
                run_export(
                    source,
                    ExportOptions(output_dir=Path(directory), model_filter="nonexistent"),
                )


class ModelSourceBoundaryTests(unittest.TestCase):
    def test_fake_source_satisfies_the_protocol(self) -> None:
        self.assertIsInstance(FakeSource(export_points()), ModelSource)

    @unittest.skipUnless(
        importlib.util.find_spec("playwright"), "playwright is not installed"
    )
    def test_playwright_source_satisfies_the_protocol(self) -> None:
        from export_source import PlaywrightChartSource

        self.assertIsInstance(PlaywrightChartSource(), ModelSource)

    def test_pipeline_imports_without_a_browser_driver(self) -> None:
        script = textwrap.dedent(
            """
            import sys
            sys.path.insert(0, sys.argv[1])
            import export_pipeline
            assert "playwright" not in sys.modules, "export_pipeline pulled in playwright"
            """
        )
        completed = subprocess.run(
            [sys.executable, "-c", script, str(SCRIPTS)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
