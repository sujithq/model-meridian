from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers import SCRIPTS


@unittest.skipUnless(
    importlib.util.find_spec("playwright"), "playwright is not installed"
)
class ChartDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from playwright.sync_api import sync_playwright

        cls.playwright = sync_playwright().start()
        if not Path(cls.playwright.chromium.executable_path).exists():
            cls.playwright.stop()
            raise unittest.SkipTest("Playwright Chromium is not installed")
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self) -> None:
        from export_source import PlaywrightChartSource

        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.source = PlaywrightChartSource(timeout=1000)
        self.source._page = self.page

    def load_chart(self, section_id: str) -> None:
        from export_source import SITE_URL, TARGET_TITLE

        html = f"""
            <section id="intelligence-index-vs-cost-per-intelligence-index-task">
              <h2>Another chart</h2>
              <button role="combobox">1 of 9 models</button>
              <svg class="recharts-surface"><circle data-chart-item-id="other"/></svg>
            </section>
            <section {section_id}>
              <header><h2>{TARGET_TITLE}<svg></svg></h2></header>
              <button role="combobox" onclick="document.querySelector('dialog').showModal()">
                1 of 2 models
              </button>
              <svg class="recharts-surface" width="100" height="100">
                <circle data-chart-item-id="target" cx="20" cy="20" r="5"/>
              </svg>
            </section>
            <dialog>
              <button onclick="window.allSelected = true">Select all</button>
              <button onclick="
                if (window.allSelected) {{
                  setTimeout(() => {{
                    document.querySelectorAll('button[role=combobox]')[1].textContent =
                      '2 of 2 models';
                  }}, 20);
                }}
                document.querySelector('dialog').close();
              ">Save</button>
            </dialog>
            <script>
              for (const circle of document.querySelectorAll('circle')) {{
                const id = circle.getAttribute('data-chart-item-id');
                circle.__reactFiber$fixture = {{
                  memoizedProps: {{
                    payload: {{id, label: id, x: 1.25, y: 50,
                               url: '/models/' + id, color: '#123456'}}
                  }}
                }};
              }}
            </script>
        """
        self.page.route(
            SITE_URL,
            lambda route: route.fulfill(body=html, content_type="text/html"),
        )
        self.source._open_chart()
        self.assertEqual(
            self.page.url, "https://artificialanalysis.ai/models/releases"
        )

    def test_changed_or_missing_id_keeps_selection_and_extraction_scoped(self) -> None:
        from export_source import SITE_URL, TARGET_TITLE

        for section_id in ('id="renamed-chart"', ""):
            with self.subTest(section_id=section_id):
                self.load_chart(section_id)
                self.assertEqual(self.source.select_all(), 2)
                with patch("export_source.SETTLE_DELAY", 0):
                    points = self.source.extract_points()
                self.assertEqual([point.id for point in points], ["target"])
                self.assertEqual(points[0].cost_per_task_usd, 1.25)
                self.assertEqual(points[0].intelligence_index, 50)
                self.assertEqual(
                    points[0].model_url,
                    "https://artificialanalysis.ai/models/target",
                )
                self.assertEqual(points[0].color, "#123456")
                self.assertEqual(self.source.metadata.page, SITE_URL)
                self.assertEqual(self.source.metadata.chart, TARGET_TITLE)
                self.assertEqual(
                    self.page.locator('button[role="combobox"]').first.inner_text(),
                    "1 of 9 models",
                )
                self.page.unroute_all()

    def test_missing_title_does_not_use_the_old_section_id(self) -> None:
        from playwright.sync_api import TimeoutError

        from export_source import SITE_URL

        self.page.route(
            SITE_URL,
            lambda route: route.fulfill(
                body='<section id="intelligence-index-vs-cost-per-intelligence-index-task">'
                '<svg class="recharts-surface"></svg></section>',
                content_type="text/html",
            ),
        )
        with self.assertRaises(TimeoutError):
            self.source._open_chart()


if __name__ == "__main__":
    unittest.main()
