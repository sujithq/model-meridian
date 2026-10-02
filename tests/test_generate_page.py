from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import FIELDNAMES, write_fixture_csv

import page_builder
from page_builder import assemble_page, build_page
from page_data import build_payload


def page_args(source: Path, output: Path | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        csv=str(source),
        output=str(output) if output else None,
        title="Model <Meridian>",
        subtitle="Interactive comparison",
        xlabel="Cost",
        ylabel="Score",
        footnote="Source attribution",
        min_score=None,
        max_cost=None,
        families=None,
        top=None,
    )


class PagePayloadTests(unittest.TestCase):
    def test_payload_preserves_urls_efforts_and_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            records, config = build_payload(page_args(source))

        self.assertEqual(len(records), 3)
        alpha_low = next(record for record in records if record["model"].endswith("fallback)"))
        self.assertEqual(alpha_low["family"], "Alpha 1")
        self.assertEqual(alpha_low["effort"], "low")
        self.assertTrue(alpha_low["fallback"])
        self.assertEqual(alpha_low["url"], "https://example.test/alpha-low")
        self.assertEqual(config["minScore"], 40.0)
        self.assertEqual(config["maxScore"], 50.0)
        self.assertEqual(config["minCost"], 0.5)
        self.assertEqual(config["maxCost"], 2.0)

    def test_payload_applies_starting_filters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            args = page_args(source)
            args.min_score = 44
            args.families = ["beta"]
            records, _ = build_payload(args)

        self.assertEqual([record["model"] for record in records], ["Beta"])

    def test_duplicate_labels_keep_row_specific_urls(self) -> None:
        rows = [
            {
                "id": "duplicate-a",
                "model": "Duplicate",
                "cost_per_task_usd": "1",
                "intelligence_index": "20",
                "model_url": "https://example.test/a",
                "color": "#123456",
            },
            {
                "id": "duplicate-b",
                "model": "Duplicate",
                "cost_per_task_usd": "2",
                "intelligence_index": "30",
                "model_url": "https://example.test/b",
                "color": "#123456",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "duplicates.csv"
            with source.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerows(rows)
            records, _ = build_payload(page_args(source))

        self.assertEqual(
            {(record["cost"], record["url"]) for record in records},
            {(1.0, "https://example.test/a"), (2.0, "https://example.test/b")},
        )

    def test_payload_opens_input_csv_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            original_open = Path.open
            opened_sources: list[Path] = []

            def tracked_open(path: Path, *args, **kwargs):
                if path == source:
                    opened_sources.append(path)
                return original_open(path, *args, **kwargs)

            with mock.patch.object(Path, "open", tracked_open):
                build_payload(page_args(source))

        self.assertEqual(opened_sources, [source])


class GeneratedPageTests(unittest.TestCase):
    def test_page_is_self_contained_and_escapes_visible_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_fixture_csv(root / "models.csv")
            output = root / "index.html"
            result = build_page(page_args(source, output))
            html = result.read_text(encoding="utf-8")

        self.assertEqual(result, output)
        self.assertIn("<title>Model &lt;Meridian&gt;</title>", html)
        self.assertIn("const DATA =", html)
        self.assertIn("Alpha 1 (max)", html)
        self.assertNotIn('<script src="', html)
        self.assertNotIn('<link rel="stylesheet"', html)
        self.assertNotIn("https://cdn.", html)

    def test_page_replaces_all_placeholders_and_embeds_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            html = assemble_page(page_args(source))

        self.assertNotIn("__STYLES__", html)
        self.assertNotIn("__SCRIPT__", html)
        self.assertNotIn("__DATA__", html)
        self.assertNotIn("__CONFIG__", html)
        self.assertIn(":root {", html)
        self.assertIn("function render()", html)

    def test_missing_asset_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_fixture_csv(root / "models.csv")
            with mock.patch.object(page_builder, "ASSET_DIR", root / "missing"):
                with self.assertRaisesRegex(RuntimeError, "Unable to read page asset"):
                    assemble_page(page_args(source))

    def test_cli_resolves_assets_outside_repository_working_directory(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        script = repository / "scripts" / "generate_page.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_fixture_csv(root / "models.csv")
            output = root / "index.html"
            result = subprocess.run(
                [sys.executable, str(script), str(source), "-o", str(output)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.is_file())
            self.assertIn("const DATA =", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
