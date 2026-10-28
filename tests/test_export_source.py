from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import tests.helpers  # noqa: F401  (puts scripts/ on sys.path)

PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None

if PLAYWRIGHT_AVAILABLE:
    import export_artificial_analysis_csv as exporter
    import export_source


def chromium_available() -> bool:
    if not PLAYWRIGHT_AVAILABLE:
        if os.environ.get("REQUIRE_BROWSER_TESTS") == "1":
            raise RuntimeError("Browser tests are required, but Playwright is not installed.")
        return False
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as playwright:
            playwright.chromium.launch(headless=True).close()
    except Exception as exc:
        if os.environ.get("REQUIRE_BROWSER_TESTS") == "1":
            raise RuntimeError("Browser tests are required, but Chromium could not launch.") from exc
        return False
    return True


POINTS = [
    {
        "id": "release-default",
        "x": 1.5,
        "y": 60.0,
        "label": "Alpha 2",
        "tooltipLabel": "Alpha 2 (max)",
        "color": "#111111",
        "url": "/models/releases/alpha-2",
    },
    {
        "id": "release-variant",
        "x": 0.5,
        "y": 55.0,
        "label": "Alpha 2 (low)",
        "tooltipLabel": None,
        "color": "#111111",
        "url": "/models/releases/alpha-2",
    },
    {
        "id": "other-release",
        "x": 0.25,
        "y": 40.0,
        "label": "Beta",
        "tooltipLabel": "Beta",
        "color": "#222222",
        "url": "https://example.test/beta",
    },
]


def fixture_html(section_id: str, title: str) -> str:
    """A release chart whose selector applies immediately and has no Save button.

    A hidden copy of the section with the same ID precedes the visible one, as
    the site has rendered duplicate tab panels before.
    """
    return f"""<!doctype html>
<html><body>
<div id="{section_id}" style="display:none">
  <h2>{title}</h2>
  <button role="combobox">1 of 1 releases</button>
  <svg class="recharts-surface"><circle data-chart-item-id="stale" r="3"></circle></svg>
</div>
<div id="{section_id}">
  <h2>{title}</h2>
  <button role="combobox" id="selector">1 of 2 releases</button>
  <svg class="recharts-surface" id="plot" width="400" height="300"></svg>
</div>
<script>
const points = {json.dumps(POINTS)};
const visible = document.querySelectorAll('[id="{section_id}"]')[1];
const selector = visible.querySelector('#selector');
const plot = visible.querySelector('#plot');
function render(count) {{
  plot.innerHTML = '';
  for (const payload of points.slice(0, count)) {{
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('data-chart-item-id', payload.id);
    circle.setAttribute('r', '3');
    circle['__reactFiber$fixture'] = {{
      memoizedProps: {{}},
      return: {{ memoizedProps: {{ payload }}, return: null }},
    }};
    plot.appendChild(circle);
  }}
}}
render(1);
selector.addEventListener('click', () => {{
  const dialog = document.createElement('div');
  dialog.setAttribute('role', 'dialog');
  for (const name of ['Clear', 'Select all', 'Reset (to default)']) {{
    const button = document.createElement('button');
    button.textContent = name;
    dialog.appendChild(button);
  }}
  dialog.children[1].addEventListener('click', () => {{
    setTimeout(() => {{
      selector.textContent = '2 of 2 releases';
      render(points.length);
    }}, 100);
  }});
  document.addEventListener('keydown', function close(event) {{
    if (event.key === 'Escape') {{
      dialog.remove();
      document.removeEventListener('keydown', close);
    }}
  }});
  document.body.appendChild(dialog);
}});
</script>
</body></html>
"""


@unittest.skipUnless(chromium_available(), "Playwright Chromium is not installed")
class PlaywrightChartSourceFixtureTests(unittest.TestCase):
    def test_saves_diagnostics_after_a_successful_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "index.html"
            diagnostics = Path(directory) / "diagnostics"
            page.write_text(
                fixture_html(export_source.TARGET_SECTION_ID, export_source.TARGET_TITLE),
                encoding="utf-8",
            )
            with mock.patch.object(
                export_source, "SITE_URL", page.as_uri()
            ), mock.patch.object(export_source, "SETTLE_DELAY", 0):
                with export_source.PlaywrightChartSource(
                    timeout=15000, diagnostics_dir=diagnostics
                ) as source:
                    source.select_all()
                    source.extract_points()
            details = json.loads((diagnostics / "diagnostics.json").read_text())
        self.assertIsNone(details["error"])
        self.assertIsNone(details["error_type"])
        self.assertEqual(len(details["extraction"]["rows"]), 3)

    def test_records_dataset_loading_and_browser_errors_before_navigation(self) -> None:
        from playwright.sync_api import sync_playwright

        html = fixture_html(export_source.TARGET_SECTION_ID, export_source.TARGET_TITLE)
        html = html.replace(
            "render(1);",
            """render(1);
fetch('/data/missing.txt?token=not-for-diagnostics');
fetch('/data/broken.txt');
fetch('/data/ok.txt');
console.warn('dataset warning');
setTimeout(() => { throw new Error('dataset initialization failed'); }, 0);""",
        )
        with tempfile.TemporaryDirectory() as directory:
            diagnostics = Path(directory) / "diagnostics"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    with browser.new_context() as context:
                        def serve(route) -> None:
                            path = urlsplit(route.request.url).path
                            if path == "/data/missing.txt":
                                route.fulfill(status=503, body="Unavailable")
                            elif path == "/data/broken.txt":
                                route.abort("connectionreset")
                            elif path == "/data/ok.txt":
                                route.fulfill(status=200, body="{}")
                            else:
                                route.fulfill(
                                    status=200, content_type="text/html", body=html
                                )

                        context.route("https://example.test/**", serve)
                        source = export_source.PlaywrightChartSource(
                            timeout=15000, diagnostics_dir=diagnostics
                        )
                        source._page = context.new_page()
                        with mock.patch.object(
                            export_source, "SITE_URL", "https://example.test/"
                        ), mock.patch.object(export_source, "SETTLE_DELAY", 0):
                            source._start_diagnostics()
                            source._open_chart()
                            source._page.wait_for_function(
                                "() => performance.getEntriesByName("
                                "'https://example.test/data/ok.txt').length > 0"
                            )
                            source.select_all()
                            points = source.extract_points()
                            source._save_diagnostics(RuntimeError("incomplete export"))
                finally:
                    browser.close()

            details = json.loads((diagnostics / "diagnostics.json").read_text())

        events = details["events"]
        self.assertTrue(any(event["event"] == "request" for event in events))
        self.assertTrue(
            any(
                event["event"] == "response"
                and event["url"] == "https://example.test/data/missing.txt"
                and event["status"] == 503
                for event in events
            )
        )
        self.assertTrue(
            any(
                event["event"] == "requestfailed"
                and event["url"] == "https://example.test/data/broken.txt"
                and event["failure"]
                for event in events
            )
        )
        self.assertTrue(
            any(
                event["event"] == "requestfinished"
                and event["url"] == "https://example.test/data/ok.txt"
                for event in events
            )
        )
        self.assertTrue(
            any(
                event["event"] == "pageerror"
                and "dataset initialization failed" in event["message"]
                for event in events
            )
        )
        self.assertTrue(
            any(
                event["event"] == "console" and event["message"] == "dataset warning"
                for event in events
            )
        )
        self.assertTrue(all(event["elapsed_ms"] >= 0 for event in events))
        self.assertTrue(all("?" not in event["url"] for event in events if "url" in event))
        self.assertEqual(details["dropped_event_count"], 0)
        self.assertEqual(
            [row["id"] for row in details["extraction"]["rows"]],
            [point.id for point in points],
        )

    def test_saves_diagnostics_when_export_fails_inside_an_open_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "index.html"
            diagnostics = Path(directory) / "diagnostics"
            page.write_text(
                fixture_html(export_source.TARGET_SECTION_ID, export_source.TARGET_TITLE),
                encoding="utf-8",
            )
            with mock.patch.object(export_source, "SITE_URL", page.as_uri()):
                with self.assertRaisesRegex(RuntimeError, "fixture export failed"):
                    with export_source.PlaywrightChartSource(
                        timeout=15000, diagnostics_dir=diagnostics
                    ):
                        raise RuntimeError("fixture export failed")
            details = json.loads((diagnostics / "diagnostics.json").read_text())
            self.assertEqual(details["error"], "fixture export failed")
            self.assertEqual(
                details["page"]["viewport"],
                {"width": 1600, "height": 1200, "devicePixelRatio": 1},
            )
            self.assertIn(export_source.TARGET_SECTION_ID, details["page"]["sectionIds"])
            self.assertEqual(details["page"]["plotCount"], 2)
            self.assertTrue((diagnostics / "page.png").is_file())
            self.assertIn(export_source.TARGET_TITLE, (diagnostics / "page.html").read_text())

    def test_saves_diagnostics_when_opening_the_chart_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "index.html"
            diagnostics = Path(directory) / "diagnostics"
            page.write_text("<html><body>No chart</body></html>", encoding="utf-8")
            with mock.patch.object(export_source, "SITE_URL", page.as_uri()):
                source = export_source.PlaywrightChartSource(
                    timeout=100, diagnostics_dir=diagnostics
                )
                with self.assertRaises(export_source.PlaywrightTimeoutError):
                    with source:
                        self.fail("A missing chart must not open successfully.")
            self.assertIsNone(source._page)
            details = json.loads((diagnostics / "diagnostics.json").read_text())
            self.assertEqual(details["error_type"], "TimeoutError")
            self.assertEqual(details["page"]["plotCount"], 0)

    def test_selects_all_releases_and_extracts_full_variant_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "index.html"
            page.write_text(
                fixture_html(export_source.TARGET_SECTION_ID, export_source.TARGET_TITLE),
                encoding="utf-8",
            )
            with mock.patch.object(export_source, "SITE_URL", page.as_uri()), mock.patch.object(
                export_source, "SETTLE_DELAY", 0
            ):
                with export_source.PlaywrightChartSource(timeout=15000) as source:
                    selected = source.select_all()
                    points = source.extract_points()

        self.assertEqual(selected, 2)
        self.assertEqual(
            [(point.id, point.model) for point in points],
            [
                ("release-default", "Alpha 2 (max)"),
                ("release-variant", "Alpha 2 (low)"),
                ("other-release", "Beta"),
            ],
        )
        self.assertEqual(
            points[0].model_url, "https://artificialanalysis.ai/models/releases/alpha-2"
        )
        self.assertEqual(points[2].model_url, "https://example.test/beta")
        self.assertEqual(points[0].cost_per_task_usd, 1.5)
        self.assertEqual(points[0].intelligence_index, 60.0)
        self.assertEqual(points[0].color, "#111111")

    def test_reloads_selected_release_url_before_extracting_stale_plot(self) -> None:
        html = fixture_html(export_source.TARGET_SECTION_ID, export_source.TARGET_TITLE)
        html = html.replace(
            "render(1);",
            """const allSelected = new URLSearchParams(location.search).has('releases');
if (allSelected) selector.textContent = '2 of 2 releases';
render(allSelected ? points.length : 1);""",
        ).replace(
            "render(points.length);",
            "history.replaceState(null, '', '?releases=alpha-2,beta' + location.hash);",
        )
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                for reloaded_count in (2, 3):
                    with self.subTest(reloaded_count=reloaded_count):
                        visited = []
                        with browser.new_context() as context:
                            def serve(route) -> None:
                                visited.append(route.request.url)
                                body = html.replace(
                                    "if (allSelected) selector.textContent = '2 of 2 releases';",
                                    "if (allSelected) selector.textContent = "
                                    f"'{reloaded_count} of {reloaded_count} releases';",
                                )
                                route.fulfill(
                                    status=200, content_type="text/html", body=body
                                )

                            context.route("https://example.test/**", serve)
                            source = export_source.PlaywrightChartSource(timeout=15000)
                            source._page = context.new_page()
                            with mock.patch.object(
                                export_source, "SITE_URL", "https://example.test/"
                            ), mock.patch.object(export_source, "SETTLE_DELAY", 0):
                                source._open_chart()
                                if reloaded_count == 3:
                                    with self.assertRaisesRegex(
                                        RuntimeError, "Release selection changed"
                                    ):
                                        source.select_all()
                                else:
                                    selected = source.select_all()
                                    points = source.extract_points()
                                    self.assertEqual(selected, 2)
                                    self.assertEqual(
                                        [point.id for point in points],
                                        [point["id"] for point in POINTS],
                                    )
                            self.assertEqual(len(visited), 2)
                            self.assertEqual(
                                parse_qs(urlsplit(visited[1]).query)["releases"],
                                ["alpha-2,beta"],
                            )
            finally:
                browser.close()

    def test_finds_chart_by_title_when_section_id_changes(self) -> None:
        changed_section_id = "updated-chart-section"
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "index.html"
            page.write_text(
                fixture_html(changed_section_id, export_source.TARGET_TITLE),
                encoding="utf-8",
            )
            with mock.patch.object(export_source, "SITE_URL", page.as_uri()), mock.patch.object(
                export_source, "SETTLE_DELAY", 0
            ):
                with export_source.PlaywrightChartSource(timeout=15000) as source:
                    selected = source.select_all()
                    points = source.extract_points()

        self.assertEqual(selected, 2)
        self.assertEqual(len(points), 3)

    def test_finds_chart_by_legacy_section_id(self) -> None:
        legacy_id = export_source.LEGACY_SECTION_IDS[0]
        self.assertNotEqual(legacy_id, export_source.TARGET_SECTION_ID)
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "index.html"
            page.write_text(
                fixture_html(legacy_id, export_source.TARGET_TITLE),
                encoding="utf-8",
            )
            with mock.patch.object(export_source, "SITE_URL", page.as_uri()), mock.patch.object(
                export_source, "SETTLE_DELAY", 0
            ):
                with export_source.PlaywrightChartSource(timeout=15000) as source:
                    selected = source.select_all()
                    points = source.extract_points()

        self.assertEqual(selected, 2)
        self.assertEqual(len(points), 3)

    def test_title_fallback_skips_containers_without_a_plot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "index.html"
            html = fixture_html("updated-chart-section", export_source.TARGET_TITLE)
            decoy = (
                f"<div><h3>{export_source.TARGET_TITLE}</h3>"
                "<button role=\"combobox\">Sort</button></div>\n"
            )
            html = html.replace("<html><body>\n", "<html><body>\n" + decoy, 1)
            page.write_text(html, encoding="utf-8")
            with mock.patch.object(export_source, "SITE_URL", page.as_uri()), mock.patch.object(
                export_source, "SETTLE_DELAY", 0
            ):
                with export_source.PlaywrightChartSource(timeout=15000) as source:
                    selected = source.select_all()
                    points = source.extract_points()

        self.assertEqual(selected, 2)
        self.assertEqual(len(points), 3)

    def test_extracts_payloads_when_chart_points_have_no_data_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "index.html"
            html = fixture_html(export_source.TARGET_SECTION_ID, export_source.TARGET_TITLE)
            html = html.replace(
                "circle.setAttribute('data-chart-item-id', payload.id);",
                "",
            )
            page.write_text(html, encoding="utf-8")
            with mock.patch.object(export_source, "SITE_URL", page.as_uri()), mock.patch.object(
                export_source, "SETTLE_DELAY", 0
            ):
                with export_source.PlaywrightChartSource(timeout=15000) as source:
                    selected = source.select_all()
                    points = source.extract_points()

        self.assertEqual(selected, 2)
        self.assertEqual(
            [(point.id, point.model) for point in points],
            [
                ("release-default", "Alpha 2 (max)"),
                ("release-variant", "Alpha 2 (low)"),
                ("other-release", "Beta"),
            ],
        )


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "Playwright is not installed")
class ExportCliTests(unittest.TestCase):
    def test_diagnostics_are_opt_in_and_bounded(self) -> None:
        source = export_source.PlaywrightChartSource()
        source._page = mock.Mock()
        source._start_diagnostics()
        source._page.on.assert_not_called()
        with mock.patch.object(export_source, "MAX_DIAGNOSTIC_EVENTS", 2):
            for _ in range(3):
                source._record_diagnostic_event({"event": "test"})
        self.assertEqual(len(source._diagnostic_events), 2)
        self.assertEqual(source._dropped_diagnostic_events, 1)

    def test_parses_fixed_output_and_diagnostics_into_configuration(self) -> None:
        config = exporter.parse_args(
            ["--output", "data.csv", "--diagnostics-dir", "diagnostics"]
        )
        self.assertEqual(config.options.output_path, Path("data.csv"))
        self.assertEqual(config.diagnostics_dir, Path("diagnostics"))

    def test_retains_dated_snapshot_output(self) -> None:
        config = exporter.parse_args(["--output-dir", "snapshots", "--filter", "Alpha"])
        self.assertEqual(config.options.output_dir, Path("snapshots"))
        self.assertEqual(config.options.model_filter, "Alpha")
        self.assertIsNone(config.options.output_path)

    def test_only_browser_timeouts_and_network_errors_are_retryable(self) -> None:
        self.assertTrue(
            export_source.is_retryable_source_error(export_source.PlaywrightTimeoutError("timeout"))
        )
        self.assertTrue(
            export_source.is_retryable_source_error(
                export_source.PlaywrightError("Page.goto: net::ERR_CONNECTION_RESET")
            )
        )
        self.assertFalse(
            export_source.is_retryable_source_error(RuntimeError("no extractable model payloads"))
        )
        self.assertFalse(
            export_source.is_retryable_source_error(export_source.PlaywrightError("invalid selector"))
        )


if __name__ == "__main__":
    unittest.main()
