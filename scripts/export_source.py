"""Playwright-backed Artificial Analysis chart source.

This module is the unstable, source-specific boundary of the export: it owns the
site URL, the chart selectors and the in-page extraction script, and it is the
only export module that imports a browser driver. Everything downstream works
against the `ModelSource` protocol in `export_pipeline.py`.
"""

from __future__ import annotations

from types import TracebackType

from playwright.sync_api import sync_playwright

from export_pipeline import ExportPoint, SourceMetadata

SITE_URL = "https://artificialanalysis.ai/"
TARGET_TAB_ID = "intelligence-efficiency-tabs"
TARGET_SECTION_ID = "intelligence-index-vs-cost-per-task-by-model-release"
TARGET_TITLE = "Intelligence Index vs. Cost per Task, by Model Release"
OUTPUT_SLUG = "artificial-analysis-intelligence-index-vs-cost-all-plotted-models"

PAGE_TIMEOUT = 600000
DIALOG_TIMEOUT = 60000
SETTLE_DELAY = 6000
VIEWPORT = {"width": 1600, "height": 1200}

# The site has rendered the same section ID in several tab panels; only the
# visible copy is the one the user (and the selector dialog) interacts with.
_FIND_VISIBLE_CHART = """
  let chart = [...document.querySelectorAll('#' + CSS.escape(sectionId))]
    .find((node) => node.getClientRects().length > 0) || null;
  if (!chart) {
    const targetTitle = """ + repr(TARGET_TITLE) + """;
    const title = [...document.querySelectorAll('body *')]
      .find((node) =>
        node.getClientRects().length > 0 &&
        node.textContent.trim() === targetTitle
      );
    for (let ancestor = title?.parentElement; ancestor && ancestor !== document.body;
      ancestor = ancestor.parentElement) {
      if (ancestor.querySelector('button[role="combobox"]')) {
        chart = ancestor;
        break;
      }
    }
  }
"""

SELECTION_COMPLETE_SCRIPT = """
(sectionId) => {""" + _FIND_VISIBLE_CHART + """
  const selector = chart?.querySelector('button[role="combobox"]');
  if (!selector) return false;
  const text = (selector.textContent || '').trim();
  const match = text.match(/^(\\d+) of (\\d+) (?:releases|models)$/);
  return !!match && match[1] === match[2];
}
"""

EXTRACTION_SCRIPT = """
(sectionId) => {""" + _FIND_VISIBLE_CHART + """
  if (!chart) {
    return { candidateCount: 0, resolvedCandidateCount: 0, rows: [] };
  }
  const candidates = [...chart.querySelectorAll('svg.recharts-surface *')];
  const markedCandidates = candidates.filter((node) =>
    node.hasAttribute('data-chart-item-id')
  );
  const rows = [];
  const seen = new Set();
  const resolvedMarkedCandidates = new Set();

  const findFiber = (node) => {
    if (!node) return null;
    for (const key of Object.keys(node)) {
      if (key.startsWith('__reactFiber$')) return node[key];
    }
    return null;
  };

  const walkPayload = (node) => {
    let current = node;
    while (current) {
      const props = current.memoizedProps || current.pendingProps || null;
      const payload = props && props.payload;
      if (
        payload &&
        payload.id &&
        Number.isFinite(payload.x) &&
        Number.isFinite(payload.y)
      ) {
        return payload;
      }
      current = current.return;
    }
    return null;
  };

  for (const candidate of candidates) {
    const fiber = findFiber(candidate);
    const payload = walkPayload(fiber);
    if (!payload) continue;

    if (candidate.hasAttribute('data-chart-item-id')) {
      resolvedMarkedCandidates.add(candidate);
    }
    const id = String(payload.id).trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);

    // A release's labelled point carries only the release name in `label`;
    // `tooltipLabel` keeps the full variant name with its effort suffix.
    const label = payload.tooltipLabel || payload.label || payload.model || '';
    const url = payload.url || '';
    const href = url
      ? (url.startsWith('http://') || url.startsWith('https://')
          ? url
          : `https://artificialanalysis.ai${url.startsWith('/') ? url : '/' + url}`)
      : '';

    rows.push({
      id,
      model: String(label),
      cost_per_task_usd: Number(payload.x),
      intelligence_index: Number(payload.y),
      model_url: href,
      color: payload.color || '',
    });
  }
  return {
    candidateCount: markedCandidates.length,
    resolvedCandidateCount: resolvedMarkedCandidates.size,
    rows,
  };
}
"""


class PlaywrightChartSource:
    """Read plotted models from the live Artificial Analysis chart.

    Used as a context manager so one browser stays open across `select_all()`
    and `extract_points()`.
    """

    def __init__(self, *, headless: bool = True, timeout: int = PAGE_TIMEOUT) -> None:
        self._headless = headless
        self._timeout = timeout
        self._playwright = None
        self._browser = None
        self._page = None

    @property
    def metadata(self) -> SourceMetadata:
        return SourceMetadata(chart=TARGET_TITLE, page=SITE_URL, slug=OUTPUT_SLUG)

    def __enter__(self) -> PlaywrightChartSource:
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(headless=self._headless)
            self._page = self._browser.new_page(viewport=VIEWPORT)
            self._open_chart()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self._page = None

    @property
    def _active_page(self):
        if self._page is None:
            raise RuntimeError(
                "The chart source is not open; use PlaywrightChartSource as a context manager."
            )
        return self._page

    def _chart(self):
        page = self._active_page
        chart = page.locator(f"#{TARGET_SECTION_ID}").filter(visible=True)
        if chart.count():
            return chart

        title = page.get_by_text(TARGET_TITLE, exact=True).filter(visible=True)
        return title.locator(
            "xpath=ancestor::*[.//button[@role='combobox']][1]"
        )

    def _open_chart(self) -> None:
        page = self._active_page
        page.goto(
            f"{SITE_URL}#{TARGET_TAB_ID}",
            wait_until="domcontentloaded",
            timeout=self._timeout,
        )
        chart = self._chart()
        chart.wait_for(state="visible", timeout=self._timeout)
        chart.get_by_text(TARGET_TITLE, exact=True).wait_for(timeout=self._timeout)

    def select_all(self) -> int:
        page = self._active_page
        selector = self._chart().locator('button[role="combobox"]').filter(has_text="of")
        if selector.count() != 1:
            raise RuntimeError(
                f"Expected one model selector in the target chart, found {selector.count()}."
            )
        selector.wait_for(state="visible", timeout=self._timeout)
        selector.click()

        dialog = page.get_by_role("dialog")
        dialog.wait_for(state="visible", timeout=DIALOG_TIMEOUT)
        select_all = dialog.get_by_role("button", name="Select all")
        if select_all.count() != 1:
            raise RuntimeError(
                f"Expected one Select all control, found {select_all.count()}."
            )
        select_all.click()

        # The release selector applies changes immediately and has no Save control.
        save = dialog.get_by_role("button", name="Save")
        if save.count() > 1:
            raise RuntimeError(f"Expected at most one Save control, found {save.count()}.")
        if save.count() == 1:
            save.click()

        page.wait_for_function(
            SELECTION_COMPLETE_SCRIPT,
            arg=TARGET_SECTION_ID,
            timeout=self._timeout,
        )
        if dialog.is_visible():
            page.keyboard.press("Escape")
            dialog.wait_for(state="hidden", timeout=DIALOG_TIMEOUT)
        return int(selector.inner_text().strip().split()[0])

    def extract_points(self) -> list[ExportPoint]:
        page = self._active_page
        page.wait_for_timeout(SETTLE_DELAY)
        extraction = page.evaluate(EXTRACTION_SCRIPT, TARGET_SECTION_ID)

        candidate_count = int(extraction["candidateCount"])
        resolved_candidate_count = int(extraction["resolvedCandidateCount"])
        rows = extraction["rows"]
        if candidate_count != resolved_candidate_count:
            raise RuntimeError(
                "Chart extraction was incomplete: "
                f"{candidate_count} marked points produced "
                f"{resolved_candidate_count} valid payloads."
            )
        return [
            ExportPoint(
                id=str(row["id"]),
                model=str(row["model"]),
                cost_per_task_usd=float(row["cost_per_task_usd"]),
                intelligence_index=float(row["intelligence_index"]),
                model_url=str(row.get("model_url") or ""),
                color=str(row.get("color") or ""),
            )
            for row in rows
        ]
