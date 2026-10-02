"""Source-agnostic export pipeline for the model data refresh.

Filtering, ordering, de-duplication, validation and CSV writing live here and
depend only on the standard library, so the deterministic half of the export can
be imported and tested without a browser driver installed. The volatile,
site-specific scraping lives behind the `ModelSource` protocol in
`export_source.py`.
"""

from __future__ import annotations

import csv
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FIELDNAMES = (
    "id",
    "model",
    "cost_per_task_usd",
    "intelligence_index",
    "model_url",
    "color",
    "source_chart",
    "source_page",
    "extracted_at",
)


@dataclass(frozen=True, slots=True)
class ExportPoint:
    """One plotted model, normalized away from any source-specific payload."""

    id: str
    model: str
    cost_per_task_usd: float
    intelligence_index: float
    model_url: str = ""
    color: str = ""


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    chart: str
    page: str
    slug: str


@dataclass(frozen=True, slots=True)
class ExportOptions:
    output_dir: Path
    model_filter: str = ""


@dataclass(frozen=True, slots=True)
class ExportResult:
    path: Path
    selected_count: int
    plotted_count: int
    points: list[ExportPoint]


@runtime_checkable
class ModelSource(Protocol):
    """The unstable boundary: anything that can select and read plotted models."""

    @property
    def metadata(self) -> SourceMetadata:
        """Provenance recorded in every exported row."""

    def select_all(self) -> int:
        """Select every available model and return the resulting selected count."""

    def extract_points(self) -> list[ExportPoint]:
        """Return one record per plotted point."""


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


def apply_model_filter(points: list[ExportPoint], model_filter: str) -> list[ExportPoint]:
    needle = (model_filter or "").strip().lower()
    if not needle:
        return points
    return [point for point in points if needle in point.model.lower()]


def sort_points(points: list[ExportPoint]) -> list[ExportPoint]:
    return sorted(
        points,
        key=lambda point: (
            -point.intelligence_index,
            point.cost_per_task_usd,
            point.model.lower(),
        ),
    )


def dedupe_points(points: list[ExportPoint]) -> list[ExportPoint]:
    return list({point.id: point for point in points}.values())


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


def write_csv(points: list[ExportPoint], output_dir: Path, metadata: SourceMetadata) -> Path:
    local_now = paris_now()
    filename = f"{metadata.slug}-{local_now.strftime('%Y-%m-%d')}.csv"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename

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
            writer = csv.DictWriter(handle, fieldnames=list(FIELDNAMES), lineterminator="\n")
            writer.writeheader()
            extracted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            for point in points:
                writer.writerow(
                    {
                        "id": point.id,
                        "model": point.model,
                        "cost_per_task_usd": f"{point.cost_per_task_usd:.15g}",
                        "intelligence_index": f"{point.intelligence_index:.15g}",
                        "model_url": point.model_url,
                        "color": point.color,
                        "source_chart": metadata.chart,
                        "source_page": metadata.page,
                        "extracted_at": extracted_at,
                    }
                )
        validate_csv(temp_path, len(points))
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    return path


def run_export(source: ModelSource, options: ExportOptions) -> ExportResult:
    """Drive any model source through the deterministic export pipeline."""
    selected_count = source.select_all()
    points = source.extract_points()
    if not points:
        raise RuntimeError(
            "The chart rendered no extractable model payloads; the page structure "
            "may have changed."
        )
    plotted_count = len(points)

    points = apply_model_filter(points, options.model_filter)
    points = sort_points(points)
    points = dedupe_points(points)
    points = sort_points(points)
    if not points:
        raise RuntimeError("The model-name filter matched no plotted models.")

    path = write_csv(points, options.output_dir, source.metadata)
    return ExportResult(
        path=path,
        selected_count=selected_count,
        plotted_count=plotted_count,
        points=points,
    )
