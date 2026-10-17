import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import export_source  # noqa: E402

FIXTURE = """
<div id="{section}">
  <h3>{title}</h3>
  <button role="combobox">{selection}</button>
  <svg class="recharts-surface">
    <circle data-chart-item-id="a"></circle>
    <circle data-chart-item-id="b"></circle>
  </svg>
</div>
<script>
  const payloads = [
    {{id: 'a', x: 5.9, y: 57.6, label: 'Claude Opus 5.5',
      tooltipLabel: 'Claude Opus 5.5 (max with fallback)',
      url: '/models/releases/claude-opus-5-5', color: '#cc785c'}},
    {{id: 'b', x: 1.8, y: 53.5, label: 'Claude Opus 5.5 (high with fallback)',
      url: '/models/releases/claude-opus-5-5', color: '#cc785c'}},
  ];
  document.querySelectorAll('circle').forEach((circle, index) => {{
    circle['__reactFiber$test'] = {{
      memoizedProps: {{}},
      return: {{ memoizedProps: {{ payload: payloads[index] }}, return: null }},
    }};
  }});
</script>
"""


class ExportSourceConfigurationTests(unittest.TestCase):
    def test_targets_homepage_model_release_chart(self):
        self.assertEqual(export_source.SITE_URL, "https://artificialanalysis.ai/")
        self.assertEqual(
            export_source.TARGET_SECTION_ID,
            "intelligence-index-vs-cost-per-task-by-model-release",
        )
        self.assertEqual(
            export_source.TARGET_TITLE,
            "Intelligence Index vs. Cost per Task, by Model Release",
        )


class ExportSourceScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls._playwright = export_source.sync_playwright().start()
            cls._browser = cls._playwright.chromium.launch()
        except Exception as error:  # pragma: no cover - environment dependent
            if getattr(cls, "_playwright", None):
                cls._playwright.stop()
            raise unittest.SkipTest(f"Chromium is unavailable: {error}")

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._playwright.stop()

    def _page(self, selection):
        page = self._browser.new_page()
        self.addCleanup(page.close)
        page.set_content(
            FIXTURE.format(
                section=export_source.TARGET_SECTION_ID,
                title=export_source.TARGET_TITLE,
                selection=selection,
            )
        )
        return page

    def test_selection_complete_accepts_all_releases(self):
        page = self._page("509 of 509 releases")
        self.assertTrue(
            page.evaluate(
                export_source.SELECTION_COMPLETE_SCRIPT, export_source.TARGET_SECTION_ID
            )
        )

    def test_selection_complete_rejects_partial_releases(self):
        page = self._page("10 of 509 releases")
        self.assertFalse(
            page.evaluate(
                export_source.SELECTION_COMPLETE_SCRIPT, export_source.TARGET_SECTION_ID
            )
        )

    def test_extraction_prefers_full_tooltip_variant_name(self):
        page = self._page("509 of 509 releases")
        result = page.evaluate(
            export_source.EXTRACTION_SCRIPT, export_source.TARGET_SECTION_ID
        )

        self.assertEqual(result["candidateCount"], 2)
        self.assertEqual(
            [row["model"] for row in result["rows"]],
            ["Claude Opus 5.5 (max with fallback)", "Claude Opus 5.5 (high with fallback)"],
        )
        self.assertEqual(
            result["rows"][0]["model_url"],
            "https://artificialanalysis.ai/models/releases/claude-opus-5-5",
        )


if __name__ == "__main__":
    unittest.main()
