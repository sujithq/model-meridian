from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


FIELDNAMES = [
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


def write_fixture_csv(path: Path) -> Path:
    rows = [
        {
            "id": "alpha-low",
            "model": "Alpha 1 (low with fallback)",
            "cost_per_task_usd": "1.0",
            "intelligence_index": "40",
            "model_url": "https://example.test/alpha-low",
            "color": "#1f1f1f",
        },
        {
            "id": "alpha-max",
            "model": "Alpha 1 (max)",
            "cost_per_task_usd": "2.0",
            "intelligence_index": "50",
            "model_url": "https://example.test/alpha-max",
            "color": "#1f1f1f",
        },
        {
            "id": "beta",
            "model": "Beta",
            "cost_per_task_usd": "0.5",
            "intelligence_index": "45",
            "model_url": "https://example.test/beta",
            "color": "#ff0000",
        },
        {
            "id": "invalid-cost",
            "model": "Invalid Cost",
            "cost_per_task_usd": "-1",
            "intelligence_index": "99",
            "model_url": "",
            "color": "#00ff00",
        },
        {
            "id": "invalid-score",
            "model": "Invalid Score",
            "cost_per_task_usd": "1",
            "intelligence_index": "not-a-number",
            "model_url": "",
            "color": "#00ff00",
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return path
