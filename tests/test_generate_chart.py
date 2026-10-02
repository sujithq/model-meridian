from __future__ import annotations

import argparse
import tempfile
import unittest
from unittest import mock
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

            original_open = Path.open
            opened_sources: list[Path] = []

            def tracked_open(path: Path, *args, **kwargs):
                if path == source:
                    opened_sources.append(path)
                return original_open(path, *args, **kwargs)

            with mock.patch.object(Path, "open", tracked_open):
                result = build_chart(args)
            content = result.read_bytes()

        self.assertEqual(result, output)
        self.assertEqual(opened_sources, [source])
        self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(content), 5_000)


if __name__ == "__main__":
    unittest.main()
