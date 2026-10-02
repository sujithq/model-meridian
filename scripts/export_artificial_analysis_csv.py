#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from playwright.sync_api import sync_playwright

SITE_URL = "https://artificialanalysis.ai/models"
TARGET_SECTION_ID = "intelligence-index-vs-cost-per-intelligence-index-task"
TARGET_TITLE = "Intelligence Index vs. Cost per Intelligence Index Task"


def paris_now() -> datetime:
    """Return the current Europe/Paris time even without a Windows tz database."""
    utc_now = datetime.now(timezone.utc)
    try:
        return utc_now.astimezone(ZoneInfo("Europe/Paris"))
    except ZoneInfoNotFoundError:
        year = utc_now.year

        def last_sunday(month: int) -> datetime:
            next_month = datetime(year, month % 12 + 1, 1, tzinfo=timezone.utc)
            if month == 12:
                next_month = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            last_day = next_month - timedelta(days=1)
            return last_day - timedelta(days=(last_day.weekday() + 1) % 7)

        dst_start = last_sunday(3).replace(hour=1)
        dst_end = last_sunday(10).replace(hour=1)
        offset = timedelta(hours=2 if dst_start <= utc_now < dst_end else 1)
        return utc_now.astimezone(timezone(offset, name="Europe/Paris"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export all plotted Artificial Analysis model points from the "
            "Intelligence Index vs. Cost per Intelligence Index Task chart."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory to write the CSV output to. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--filter",
        default="",
        help="Optional case-insensitive model-name filter applied after all models are selected.",
    )
    return parser.parse_args()


def read_selected_points() -> tuple[int, int, list[dict]]:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        page.goto(
            f"{SITE_URL}#{TARGET_SECTION_ID}",
            wait_until="domcontentloaded",
            timeout=120000,
        )

        chart = page.locator(f"#{TARGET_SECTION_ID}")
        chart.wait_for(state="visible", timeout=120000)
        chart.get_by_text(TARGET_TITLE, exact=True).wait_for(timeout=120000)

        selector = chart.locator('button[role="combobox"]').filter(has_text="of")
        if selector.count() != 1:
            raise RuntimeError(
                f"Expected one model selector in the target chart, found {selector.count()}."
            )
        selector.wait_for(state="visible", timeout=120000)
        selector.click()

        dialog = page.get_by_role("dialog")
        dialog.wait_for(state="visible", timeout=30000)
        select_all = dialog.get_by_role("button", name="Select all")
        if select_all.count() != 1:
            raise RuntimeError(
                f"Expected one Select all control, found {select_all.count()}."
            )
        select_all.click()

        save = dialog.get_by_role("button", name="Save")
        if save.count() != 1:
            raise RuntimeError(f"Expected one Save control, found {save.count()}.")
        save.click()

        page.wait_for_function(
            """
            (sectionId) => {
              const chart = document.getElementById(sectionId);
              const selector = chart?.querySelector('button[role="combobox"]');
              if (!selector) return false;
              const text = (selector.textContent || '').trim();
              const match = text.match(/^(\\d+) of (\\d+) models$/);
              return !!match && match[1] === match[2];
            }
            """,
            arg=TARGET_SECTION_ID,
            timeout=120000,
        )
        selected_text = selector.inner_text().strip()
        selected_count = int(selected_text.split()[0])
        page.wait_for_timeout(3000)

        extraction = page.evaluate(
            """
            (sectionId) => {
              const chart = document.getElementById(sectionId);
              if (!chart) return { candidateCount: 0, rows: [] };
              const candidates = [
                ...chart.querySelectorAll(
                  'svg.recharts-surface circle[data-chart-item-id]'
                ),
              ];
              const rows = [];
              const seen = new Set();

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

                const id = String(payload.id).trim();
                if (!id || seen.has(id)) continue;
                seen.add(id);

                const label = payload.label || payload.model || '';
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
              return { candidateCount: candidates.length, rows };
            }
            """,
            TARGET_SECTION_ID,
        )

        browser.close()
        candidate_count = int(extraction["candidateCount"])
        rows = extraction["rows"]
        if candidate_count != len(rows):
            raise RuntimeError(
                "Chart extraction was incomplete: "
                f"{candidate_count} rendered points produced {len(rows)} unique payloads."
            )
        return selected_count, candidate_count, rows


def apply_model_filter(rows: list[dict], model_filter: str) -> list[dict]:
    if not model_filter:
        return rows
    needle = model_filter.strip().lower()
    if not needle:
        return rows
    return [row for row in rows if needle in str(row["model"]).lower()]


def sort_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            -float(row["intelligence_index"]),
            float(row["cost_per_task_usd"]),
            str(row["model"]).lower(),
        ),
    )


def validate_csv(path: Path, expected_count: int) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    if not rows:
        raise ValueError("CSV validation failed: no data rows were exported.")

    ids = [row.get("id", "") for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("CSV validation failed: duplicate ids detected.")
    if any(not row_id for row_id in ids):
        raise ValueError("CSV validation failed: an empty id was exported.")

    for row in rows:
        model = (row.get("model") or "").strip()
        if not model:
            raise ValueError("CSV validation failed: empty model value detected.")
        for field in ("cost_per_task_usd", "intelligence_index"):
            text = (row.get(field) or "").strip()
            if not text:
                raise ValueError(f"CSV validation failed: blank value for {field}.")
            try:
                value = float(text)
            except ValueError as exc:
                raise ValueError(f"CSV validation failed: non-numeric {field}={text!r}.") from exc
            if not math.isfinite(value):
                raise ValueError(f"CSV validation failed: non-finite {field}={text!r}.")

    if len(rows) != expected_count:
        raise ValueError(
            f"CSV validation failed: exported row count {len(rows)} does not match "
            f"expected {expected_count}."
        )


def write_csv(rows: list[dict], output_dir: Path) -> Path:
    local_now = paris_now()
    filename = (
        "artificial-analysis-intelligence-index-vs-cost-all-plotted-models-"
        f"{local_now.strftime('%Y-%m-%d')}.csv"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename

    fieldnames = [
        "id",
        "model",
        "cost_per_task_usd",
        "intelligence_index",
        "model_url",
        "color",
        "source_chart",
        "source_page",
        "extracted_at",
    ]

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8-sig",
            newline="",
            dir=output_dir,
            prefix=f".{filename}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            extracted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            for row in rows:
                writer.writerow(
                    {
                        "id": row["id"],
                        "model": row["model"],
                        "cost_per_task_usd": f"{float(row['cost_per_task_usd']):.15g}",
                        "intelligence_index": f"{float(row['intelligence_index']):.15g}",
                        "model_url": row["model_url"],
                        "color": row["color"],
                        "source_chart": TARGET_TITLE,
                        "source_page": SITE_URL,
                        "extracted_at": extracted_at,
                    }
                )
        validate_csv(temp_path, len(rows))
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    return path


def main() -> int:
    args = parse_args()
    selected_count, plotted_count, rows = read_selected_points()
    if not rows:
        raise RuntimeError(
            "The chart rendered no extractable model payloads; the page structure "
            "may have changed."
        )
    rows = apply_model_filter(rows, args.filter)
    rows = sort_rows(rows)
    rows = list({row["id"]: row for row in rows}.values())
    rows = sort_rows(rows)
    if not rows:
        raise RuntimeError("The model-name filter matched no plotted models.")

    path = write_csv(rows, args.output_dir)

    print(f"Selected model count: {selected_count}")
    print(f"Plotted row count: {plotted_count}")
    print(f"Exported row count: {len(rows)}")
    print(f"Output path: {path}")
    print("Top 10 rows by Intelligence Index:")
    for row in rows[:10]:
        print(
            f"- {row['model']} | intelligence={row['intelligence_index']} | "
            f"cost={row['cost_per_task_usd']} | id={row['id']}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
