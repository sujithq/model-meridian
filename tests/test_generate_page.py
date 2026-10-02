from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from tests.helpers import write_fixture_csv

from generate_page import build_page, build_payload


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


if __name__ == "__main__":
    unittest.main()
