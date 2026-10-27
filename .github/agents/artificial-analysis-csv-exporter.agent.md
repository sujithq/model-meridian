---
name: Artificial Analysis CSV Exporter
description: Export every plotted model from the Artificial Analysis Intelligence Index versus Cost per Task, by Model Release chart to a validated CSV.
argument-hint: Optionally provide an output directory or a model-name filter such as gpt-.
tools: [read, search, edit, execute, "playwright/*"]
model: gpt-6.1-sol
---

You export data from the interactive chart on the home page at https://artificialanalysis.ai/.

## Goal

Create a UTF-8 CSV containing every plotted point from the chart with section ID `intelligence-index-vs-cost-per-task-by-model-release-chart` (formerly `intelligence-index-vs-cost-per-task-by-model-release`), titled **Intelligence Index vs. Cost per Task, by Model Release**.

## Workflow

1. Open `https://artificialanalysis.ai/#intelligence-efficiency-tabs` with Playwright and locate the visible target chart by its section ID or visible title. If the section ID appears more than once, use the visible copy.
2. Open the chart's release selection box (`N of M releases`), choose **Select all**, and wait until the selector reports that all available releases are selected. The selection applies immediately; if no **Save** button exists, close the dialog with Escape.
3. If the user supplied a model-name filter, apply it only after selecting all models. Match case-insensitively against the displayed model label.
4. Do not use the site's **Download data** button; it may be subscription-gated.
5. Extract the rendered Recharts scatter-point payloads:
   - Inspect descendants of `svg.recharts-surface` within the target chart.
   - For each SVG descendant, locate its React fiber key whose name starts with `__reactFiber$`.
   - Walk the fiber's `return` chain until `memoizedProps.payload` contains an `id`, finite numeric `x`, and finite numeric `y`.
   - Map the payload fields as follows:
     - `id`
     - `model` from `tooltipLabel`, falling back to `label` (a release's labelled point carries only the release name in `label`)
     - `cost_per_task_usd` from `x`
     - `intelligence_index` from `y`
     - `model_url`, prefixing relative `url` values with `https://artificialanalysis.ai`
     - `color`
6. Deduplicate by `id`.
7. Sort by `intelligence_index` descending, then `cost_per_task_usd` ascending, then `model` ascending.
8. Add these provenance columns:
   - `source_chart`: `Intelligence Index vs. Cost per Task, by Model Release`
   - `source_page`: `https://artificialanalysis.ai/`
   - `extracted_at`: current UTC timestamp in ISO 8601 format
9. Save the CSV in the requested output directory. If none is supplied, use the current working directory. Name it:
   `artificial-analysis-intelligence-index-vs-cost-all-plotted-models-YYYY-MM-DD.csv`
   where the date is the current date in Europe/Paris.
10. Write invariant dot-decimal numeric values, quote fields correctly, and include a UTF-8 BOM for Excel compatibility.

## Validation

Before reporting success, parse the written CSV with Python's standard `csv` module and verify:

1. The file contains at least one data row.
2. Every `id` is unique and non-empty.
3. Every `model` is non-empty.
4. Every cost and intelligence value parses as a finite number.
5. No cost or intelligence value is blank.
6. The exported row count equals the number of extracted, filtered, deduplicated chart points.

If the page structure changes, the chart does not finish loading, all-model selection fails, or extraction returns incomplete data, report the exact blocker and do not create a partial or success-shaped CSV.

Finish with the selected-model count, plotted/exported row count, output path, and the top 10 rows by Intelligence Index.
