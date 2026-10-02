from __future__ import annotations

import csv
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import FIELDNAMES, write_fixture_csv

import page_builder
from chart_data import ChartText, DataFilters
from generate_page import parse_args
from page_builder import (
    ASSET_DIR,
    SCRIPT_ASSETS,
    THEME_SPECS,
    PageOptions,
    PageText,
    PageTheme,
    ThemeSpec,
    assemble_page,
    build_page,
    read_styles,
)
from page_data import build_payload


def page_options(source: Path, output: Path | None = None) -> PageOptions:
    return PageOptions(
        source=source,
        output=output,
        filters=DataFilters(),
        text=PageText(
            chart=ChartText(
                title="Model <Meridian>",
                xlabel="Cost",
                ylabel="Score",
                footnote="Source attribution",
            ),
            subtitle="Interactive comparison",
        ),
    )


def payload_for(options: PageOptions):
    return build_payload(options.source, options.filters, options.text.chart)


class PagePayloadTests(unittest.TestCase):
    def test_payload_preserves_urls_efforts_and_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            payload = payload_for(page_options(source))

        self.assertEqual(len(payload.records), 3)
        alpha_low = next(
            record for record in payload.records if str(record["model"]).endswith("fallback)")
        )
        self.assertEqual(alpha_low["family"], "Alpha 1")
        self.assertEqual(alpha_low["effort"], "low")
        self.assertTrue(alpha_low["fallback"])
        self.assertEqual(alpha_low["url"], "https://example.test/alpha-low")
        self.assertEqual(payload.config["minScore"], 40.0)
        self.assertEqual(payload.config["maxScore"], 50.0)
        self.assertEqual(payload.config["minCost"], 0.5)
        self.assertEqual(payload.config["maxCost"], 2.0)

    def test_payload_applies_starting_filters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            options = page_options(source)
            payload = build_payload(
                options.source,
                DataFilters(min_score=44, families=("beta",)),
                options.text.chart,
            )

        self.assertEqual([record["model"] for record in payload.records], ["Beta"])

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
            payload = payload_for(page_options(source))

        self.assertEqual(
            {(record["cost"], record["url"]) for record in payload.records},
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
                payload_for(page_options(source))

        self.assertEqual(opened_sources, [source])

    def test_parse_args_translates_cli_values_to_typed_options(self) -> None:
        options = parse_args([
            "models.csv",
            "--families",
            "Alpha",
            "Beta",
            "--min-score",
            "42",
        ])

        self.assertIsInstance(options, PageOptions)
        self.assertEqual(options.source, Path("models.csv"))
        self.assertEqual(options.filters.families, ("Alpha", "Beta"))
        self.assertEqual(options.filters.min_score, 42.0)
        self.assertEqual(options.theme, PageTheme.NATIVE)

    def test_parse_args_rejects_an_unknown_theme(self) -> None:
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                parse_args(["models.csv", "--theme", "unknown"])

    def test_parse_args_selects_framework_theme(self) -> None:
        for theme in (PageTheme.PICO, PageTheme.BULMA, PageTheme.TAILWIND):
            with self.subTest(theme=theme):
                options = parse_args(["models.csv", "--theme", theme.value])

                self.assertEqual(options.theme, theme)


class GeneratedPageTests(unittest.TestCase):
    def test_page_is_self_contained_and_escapes_visible_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_fixture_csv(root / "models.csv")
            output = root / "index.html"
            result = build_page(page_options(source, output))
            html = result.read_text(encoding="utf-8")

        self.assertEqual(result, output)
        self.assertIn("<title>Model &lt;Meridian&gt;</title>", html)
        self.assertIn("const DATA =", html)
        self.assertIn("Alpha 1 (max)", html)
        self.assertNotIn('<script src="', html)
        self.assertNotIn('<link rel="stylesheet"', html)
        self.assertNotIn("https://cdn.", html)
        self.assertIn("* { box-sizing: border-box; }", html)
        self.assertIn("--bg: #ffffff;", html)

    def test_page_replaces_all_placeholders_and_embeds_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            options = page_options(source)
            html = assemble_page(payload_for(options), options.text)

        self.assertNotIn("__STYLES__", html)
        self.assertNotIn("__SCRIPT__", html)
        self.assertNotIn("__DATA__", html)
        self.assertNotIn("__CONFIG__", html)
        self.assertIn(":root {", html)
        self.assertIn("function render()", html)

    def test_native_theme_embeds_base_styles_before_theme_styles(self) -> None:
        styles = read_styles(PageTheme.NATIVE)

        self.assertLess(
            styles.index("* { box-sizing: border-box; }"),
            styles.index("--bg: #ffffff;"),
        )
        self.assertEqual(
            THEME_SPECS[PageTheme.NATIVE],
            ThemeSpec(styles=("base.css", "themes/native.css")),
        )

    def test_pico_theme_embeds_pinned_framework_between_base_and_adapter(self) -> None:
        styles = read_styles(PageTheme.PICO)

        base_position = styles.index("* { box-sizing: border-box; }")
        framework_position = styles.index("Pico CSS")
        adapter_position = styles.index("--pico-font-size: 100%;")
        self.assertLess(base_position, framework_position)
        self.assertLess(framework_position, adapter_position)
        self.assertIn("v2.1.1", styles)

    def test_pico_page_is_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            options = page_options(source)
            html = assemble_page(payload_for(options), options.text, PageTheme.PICO)

        self.assertIn("Pico CSS", html)
        self.assertIn("themes/pico.css", str(THEME_SPECS[PageTheme.PICO].styles))
        self.assertNotIn('<link rel="stylesheet"', html)
        self.assertNotIn("https://cdn.", html)

    def test_bulma_theme_embeds_framework_adapter_and_component_classes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            options = page_options(source)
            html = assemble_page(payload_for(options), options.text, PageTheme.BULMA)

        self.assertIn("bulma.io v1.0.4", html)
        self.assertIn(".panel.box", html)
        self.assertIn('class="panel box"', html)
        self.assertIn('class="input is-small"', html)
        self.assertIn('class="button is-small"', html)

    def test_tailwind_theme_embeds_compiled_framework_and_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            options = page_options(source)
            html = assemble_page(payload_for(options), options.text, PageTheme.TAILWIND)

        self.assertIn("tailwindcss v4.3.3", html)
        self.assertIn(".chart-wrap", html)
        self.assertNotIn('<link rel="stylesheet"', html)

    def test_framework_assets_are_local_and_licensed(self) -> None:
        assets = {
            PageTheme.PICO: "vendor/pico-2.1.1/LICENSE.md",
            PageTheme.BULMA: "vendor/bulma-1.0.4/LICENSE",
            PageTheme.TAILWIND: "vendor/tailwind-4.3.3/LICENSE",
        }
        for theme, license_name in assets.items():
            with self.subTest(theme=theme):
                styles = read_styles(theme)
                self.assertNotIn("@import", styles)
                self.assertNotIn("url(http", styles)
                self.assertTrue((ASSET_DIR / license_name).is_file())

    def test_unsupported_theme_fails_explicitly(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported page theme"):
            read_styles("unknown")  # type: ignore[arg-type]

    def test_missing_theme_asset_fails_explicitly(self) -> None:
        with mock.patch.dict(
            THEME_SPECS,
            {PageTheme.NATIVE: ThemeSpec(styles=("base.css", "themes/missing.css"))},
        ):
            with self.assertRaisesRegex(RuntimeError, "themes.missing.css"):
                read_styles(PageTheme.NATIVE)

    def test_page_embeds_javascript_modules_in_dependency_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            options = page_options(source)
            html = assemble_page(payload_for(options), options.text)

        module_markers = (
            "function money(",
            "function currentFilters(",
            "const svg = document.getElementById",
            "function render(",
            "const els =",
        )
        positions = [html.index(marker) for marker in module_markers]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(
            SCRIPT_ASSETS,
            ("chart_math.js", "filter_state.js", "chart_renderer.js", "app.js"),
        )

    def test_missing_javascript_module_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = write_fixture_csv(Path(directory) / "models.csv")
            options = page_options(source)
            with mock.patch.object(page_builder, "SCRIPT_ASSETS", ("missing.js",)):
                with self.assertRaisesRegex(RuntimeError, "missing.js"):
                    assemble_page(payload_for(options), options.text)

    def test_missing_asset_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_fixture_csv(root / "models.csv")
            options = page_options(source)
            with mock.patch.object(page_builder, "ASSET_DIR", root / "missing"):
                with self.assertRaisesRegex(RuntimeError, "Unable to read page asset"):
                    assemble_page(payload_for(options), options.text)

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
