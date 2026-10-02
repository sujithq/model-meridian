---
name: Artificial Analysis CSV Exporter
description: Export every plotted model from the Artificial Analysis Intelligence Index versus Cost per Task chart to a validated CSV.
argument-hint: Optionally provide an output directory or a model-name filter such as gpt-.
tools: [read, search, edit, execute, "playwright/*"]
---

You export data from the interactive chart at https://artificialanalysis.ai/models.

## Goal

Create a UTF-8 CSV containing every plotted point from the chart under **Intelligence Index Comparisons** titled **Intelligence Index vs. Cost per Intelligence Index Task**.

## Workflow

1. Open the models page with Playwright and locate the target chart by its section ID or visible title.
2. Open the chart's model selection box, choose **Select all**, and wait until the selector reports that all available models are selected.
3. If the user supplied a model-name filter, apply it only after selecting all models. Match case-insensitively against the displayed model label.
4. Do not use the site's **Download data** button; it may be subscription-gated.
5. Extract the rendered Recharts scatter-point payloads:
   - Find `svg.recharts-surface circle[data-chart-item-id]` within the target chart.
   - For each circle, locate its React fiber key whose name starts with `__reactFiber$`.
   - Walk the fiber's `return` chain until `memoizedProps.payload` contains an `id`, finite numeric `x`, and finite numeric `y`.
   - Map the payload fields as follows:
     - `id`
     - `model` from `label`
     - `cost_per_task_usd` from `x`
     - `intelligence_index` from `y`
     - `model_url`, prefixing relative `url` values with `https://artificialanalysis.ai`
     - `color`
6. Deduplicate by `id`.
7. Sort by `intelligence_index` descending, then `cost_per_task_usd` ascending, then `model` ascending.
8. Add these provenance columns:
   - `source_chart`: `Intelligence Index vs. Cost per Intelligence Index Task`
   - `source_page`: `https://artificialanalysis.ai/models`
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
