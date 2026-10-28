"""Playwright-backed Artificial Analysis chart source.

This module is the unstable, source-specific boundary of the export: it owns the
site URL, the chart selectors and the in-page extraction script, and it is the
only export module that imports a browser driver. Everything downstream works
against the `ModelSource` protocol in `export_pipeline.py`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from time import monotonic
from types import TracebackType
from urllib.parse import parse_qs, urlsplit, urlunsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Request
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from export_pipeline import ExportPoint, SourceMetadata

SITE_URL = "https://artificialanalysis.ai/"
TARGET_TAB_ID = "intelligence-efficiency-tabs"
TARGET_SECTION_ID = "intelligence-index-vs-cost-per-task-by-model-release-chart"
# Earlier section IDs, tried after the current one so a revert keeps working.
LEGACY_SECTION_IDS = ("intelligence-index-vs-cost-per-task-by-model-release",)
SECTION_IDS = (TARGET_SECTION_ID, *LEGACY_SECTION_IDS)
TARGET_TITLE = "Intelligence Index vs. Cost per Task, by Model Release"
OUTPUT_SLUG = "artificial-analysis-intelligence-index-vs-cost-all-plotted-models"

PAGE_TIMEOUT = 600000
DIALOG_TIMEOUT = 60000
SETTLE_DELAY = 6000
VIEWPORT = {"width": 1600, "height": 1200}
LOGGER = logging.getLogger(__name__)
MAX_DIAGNOSTIC_EVENTS = 1000


def is_retryable_source_error(error: Exception) -> bool:
    if isinstance(error, PlaywrightTimeoutError):
        return True
    return isinstance(error, PlaywrightError) and any(
        code in str(error)
        for code in (
            "net::ERR_CONNECTION_RESET",
            "net::ERR_CONNECTION_CLOSED",
            "net::ERR_CONNECTION_REFUSED",
            "net::ERR_NAME_NOT_RESOLVED",
            "net::ERR_NETWORK_CHANGED",
            "net::ERR_INTERNET_DISCONNECTED",
            "net::ERR_TIMED_OUT",
        )
    )

# The site has rendered the same section ID in several tab panels; only the
# visible copy is the one the user (and the selector dialog) interacts with.
# The title fallback only accepts a container holding both the selector and the
# plot, so a heading inside a broader layout cannot resolve to a plotless node.
_FIND_VISIBLE_CHART = """
  let chart = null;
  for (const sectionId of sectionIds) {
    chart = [...document.querySelectorAll('#' + CSS.escape(sectionId))]
      .find((node) => node.getClientRects().length > 0) || null;
    if (chart) break;
  }
  if (!chart) {
    const targetTitle = """ + repr(TARGET_TITLE) + """;
    const titles = [...document.querySelectorAll('body *')]
      .filter((node) =>
        node.getClientRects().length > 0 &&
        node.textContent.trim() === targetTitle
      );
    for (const title of titles) {
      for (let ancestor = title.parentElement; ancestor && ancestor !== document.body;
        ancestor = ancestor.parentElement) {
        if (
          ancestor.querySelector('button[role="combobox"]') &&
          ancestor.querySelector('svg.recharts-surface')
        ) {
          chart = ancestor;
          break;
        }
      }
      if (chart) break;
    }
  }
"""

SELECTION_COMPLETE_SCRIPT = """
(sectionIds) => {""" + _FIND_VISIBLE_CHART + """
  const selector = chart?.querySelector('button[role="combobox"]');
  if (!selector) return false;
  const text = (selector.textContent || '').trim();
  const match = text.match(/^(\\d+) of (\\d+) (?:releases|models)$/);
  return !!match && match[1] === match[2];
}
"""

SELECTION_STATE_SCRIPT = """
(dialog) => {
  const controls = [...dialog.querySelectorAll('input[type="checkbox"], [role="checkbox"]')];
  const checked = (node) => node.tagName === 'INPUT'
    ? node.checked
    : node.getAttribute('aria-checked') === 'true';
  return {
    checkboxCount: controls.length,
    checkedCount: controls.filter(checked).length,
    uncheckedCount: controls.filter(node => !checked(node)).length,
  };
}
"""

EXTRACTION_SCRIPT = """
(sectionIds) => {""" + _FIND_VISIBLE_CHART + """
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

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout: int = PAGE_TIMEOUT,
        diagnostics_dir: Path | None = None,
    ) -> None:
        self._headless = headless
        self._timeout = timeout
        self._diagnostics_dir = diagnostics_dir
        self._playwright = None
        self._browser = None
        self._page = None
        self._diagnostic_events: list[dict[str, object]] = []
        self._dropped_diagnostic_events = 0
        self._last_extraction: dict[str, object] | None = None
        self._selection_diagnostics: dict[str, object] = {}
        self._diagnostics_started = monotonic()

    @property
    def metadata(self) -> SourceMetadata:
        return SourceMetadata(chart=TARGET_TITLE, page=SITE_URL, slug=OUTPUT_SLUG)

    def __enter__(self) -> PlaywrightChartSource:
        self._diagnostic_events.clear()
        self._dropped_diagnostic_events = 0
        self._last_extraction = None
        self._selection_diagnostics.clear()
        self._diagnostics_started = monotonic()
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(headless=self._headless)
            self._page = self._browser.new_page(viewport=VIEWPORT)
            self._start_diagnostics()
            self._open_chart()
        except BaseException as exc:
            if isinstance(exc, Exception):
                self._save_diagnostics(exc)
            self.close()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if exc is None or isinstance(exc, Exception):
                self._save_diagnostics(exc)
        finally:
            self.close()

    def _record_diagnostic_event(self, event: dict[str, object]) -> None:
        if len(self._diagnostic_events) < MAX_DIAGNOSTIC_EVENTS:
            self._diagnostic_events.append(
                {"elapsed_ms": round((monotonic() - self._diagnostics_started) * 1000), **event}
            )
        else:
            self._dropped_diagnostic_events += 1

    def _start_diagnostics(self) -> None:
        if self._diagnostics_dir is None:
            return
        page = self._active_page
        origin = urlsplit(SITE_URL)

        def network_event(kind: str, request: Request, **details: object) -> None:
            url = urlsplit(request.url)
            if (url.scheme, url.netloc) != (origin.scheme, origin.netloc):
                return
            if request.resource_type not in ("document", "script", "fetch", "xhr"):
                return
            self._record_diagnostic_event(
                {
                    "event": kind,
                    "url": urlunsplit((url.scheme, url.netloc, url.path, "", "")),
                    "resource_type": request.resource_type,
                    **details,
                }
            )

        page.on("request", lambda request: network_event("request", request))
        page.on(
            "response",
            lambda response: network_event(
                "response", response.request, status=response.status
            ),
        )
        page.on(
            "requestfinished",
            lambda request: network_event("requestfinished", request),
        )
        page.on(
            "requestfailed",
            lambda request: network_event(
                "requestfailed", request, failure=request.failure
            ),
        )
        page.on(
            "pageerror",
            lambda error: self._record_diagnostic_event(
                {"event": "pageerror", "message": str(error)[:2000]}
            ),
        )
        page.on(
            "console",
            lambda message: self._record_diagnostic_event(
                {"event": "console", "level": message.type, "message": message.text[:2000]}
            )
            if message.type in ("warning", "error")
            else None,
        )

    def _save_diagnostics(self, error: Exception | None) -> None:
        directory = self._diagnostics_dir
        if directory is None:
            return
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            LOGGER.warning("Could not create export diagnostics directory %s", directory, exc_info=True)
            return

        details: dict[str, object] = {
            "error_type": type(error).__name__ if error is not None else None,
            "error": str(error) if error is not None else None,
            "events": self._diagnostic_events,
            "dropped_event_count": self._dropped_diagnostic_events,
            "extraction": self._last_extraction,
            "selection": self._selection_diagnostics,
        }
        if self._page is not None:
            page = self._page
            for filename, capture in (
                (
                    "page.png",
                    lambda: page.screenshot(
                        path=str(directory / "page.png"), full_page=True, timeout=10000
                    ),
                ),
                (
                    "page.html",
                    lambda: (directory / "page.html").write_text(
                        page.content(), encoding="utf-8"
                    ),
                ),
            ):
                try:
                    capture()
                except (PlaywrightError, OSError):
                    LOGGER.warning("Could not capture %s", filename, exc_info=True)
            try:
                details["page"] = page.evaluate(
                    """() => ({
                      url: location.href,
                      viewport: {
                        width: window.innerWidth,
                        height: window.innerHeight,
                        devicePixelRatio: window.devicePixelRatio
                      },
                      sectionIds: [...document.querySelectorAll('[id]')]
                        .map(node => node.id)
                        .filter(id => /intelligence|efficiency|cost|release/i.test(id)),
                      selectors: [...document.querySelectorAll('button[role="combobox"]')]
                        .filter(node => node.getClientRects().length > 0)
                        .map(node => node.textContent.trim()),
                      titles: [...document.querySelectorAll('h1,h2,h3')]
                        .filter(node => node.getClientRects().length > 0)
                        .map(node => node.textContent.trim()),
                      plotCount: document.querySelectorAll('svg.recharts-surface').length,
                      markedPointCount: document.querySelectorAll('[data-chart-item-id]').length
                    })"""
                )
            except PlaywrightError:
                LOGGER.warning("Could not capture chart metadata", exc_info=True)
        try:
            (directory / "diagnostics.json").write_text(
                json.dumps(details, indent=2), encoding="utf-8"
            )
        except OSError:
            LOGGER.warning("Could not write export diagnostics metadata", exc_info=True)

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
        for section_id in SECTION_IDS:
            chart = page.locator(f"#{section_id}").filter(visible=True)
            if chart.count():
                return chart

        title = page.get_by_text(TARGET_TITLE, exact=True).filter(visible=True)
        return title.locator(
            "xpath=ancestor::*[not(self::body) and not(self::html) and "
            ".//button[@role='combobox'] and "
            ".//*[local-name()='svg' and contains(concat(' ', normalize-space(@class), ' '), "
            "' recharts-surface ')]][1]"
        ).first

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
        if self._diagnostics_dir is not None:
            self._selection_diagnostics["before_label"] = selector.inner_text().strip()
        selector.click()

        dialog = page.get_by_role("dialog")
        dialog.wait_for(state="visible", timeout=DIALOG_TIMEOUT)
        if self._diagnostics_dir is not None:
            self._selection_diagnostics["before_dialog"] = dialog.evaluate(SELECTION_STATE_SCRIPT)
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
            arg=list(SECTION_IDS),
            timeout=self._timeout,
        )
        if self._diagnostics_dir is not None:
            self._selection_diagnostics["after_label"] = selector.inner_text().strip()
            if dialog.is_visible():
                self._selection_diagnostics["after_dialog"] = dialog.evaluate(SELECTION_STATE_SCRIPT)
        if dialog.is_visible():
            page.keyboard.press("Escape")
            dialog.wait_for(state="hidden", timeout=DIALOG_TIMEOUT)
        selected_count = int(selector.inner_text().strip().split()[0])
        releases = parse_qs(urlsplit(page.url).query).get("releases")
        if self._diagnostics_dir is not None and releases:
            self._selection_diagnostics["persisted_release_count"] = len(
                set(releases[0].split(","))
            )

        # The selector can update the URL and count before the plot consumes the
        # new release set. Rehydrate from that URL instead of exporting stale dots.
        if releases:
            page.reload(wait_until="domcontentloaded", timeout=self._timeout)
            self._chart().wait_for(state="visible", timeout=self._timeout)
            page.wait_for_function(
                SELECTION_COMPLETE_SCRIPT,
                arg=list(SECTION_IDS),
                timeout=self._timeout,
            )
            reloaded_count = int(selector.inner_text().strip().split()[0])
            if self._diagnostics_dir is not None:
                self._selection_diagnostics["reloaded_label"] = selector.inner_text().strip()
            if reloaded_count != selected_count:
                raise RuntimeError(
                    "Release selection changed after reloading the chart: "
                    f"expected {selected_count}, found {reloaded_count}."
                )
        return selected_count

    def extract_points(self) -> list[ExportPoint]:
        page = self._active_page
        page.wait_for_timeout(SETTLE_DELAY)
        extraction = page.evaluate(EXTRACTION_SCRIPT, list(SECTION_IDS))
        self._last_extraction = extraction

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
