from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from tests.helpers import write_fixture_csv

from generate_chart import build_chart


class StaticChartTests(unittest.TestCase):
    def test_builds_a_png_from_valid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_fixture_csv(root / "models.csv")
            output = root / "chart.png"
            args = argparse.Namespace(
                csv=str(source),
                output=str(output),
                title="Model Meridian",
                xlabel="Cost",
                ylabel="Score",
                footnote="Source attribution",
                min_score=None,
                max_cost=None,
                families=None,
                top=None,
                no_effort_labels=False,
                width=8.0,
                height=4.5,
                dpi=80,
                family_fontsize=8.0,
                effort_fontsize=6.0,
            )

            result = build_chart(args)
            content = result.read_bytes()

        self.assertEqual(result, output)
        self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(content), 5_000)


if __name__ == "__main__":
    unittest.main()
