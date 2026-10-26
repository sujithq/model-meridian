from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests.helpers  # noqa: F401  (puts scripts/ on sys.path)

PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None

if PLAYWRIGHT_AVAILABLE:
    import export_source


def chromium_available() -> bool:
    if not PLAYWRIGHT_AVAILABLE:
        return False
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as playwright:
            playwright.chromium.launch(headless=True).close()
    except Exception:
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


if __name__ == "__main__":
    unittest.main()
