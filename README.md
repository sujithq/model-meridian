# Model Meridian

[![AI Ready](https://img.shields.io/badge/AI--Ready-yes-brightgreen?style=flat)](https://github.com/johnpapa/ai-ready)

Model Meridian is an interactive AI model intelligence-and-cost explorer. It
also generates labelled static charts from the same CSV data. Models in the
same family are connected across reasoning-effort levels, while models with
only one data point are shown as diamonds.

The chart uses a logarithmic cost axis, colors from the input data, and
collision-aware labels. It is designed to produce charts similar to
[`data/example-chart.png`](data/example-chart.png).

The generators live under [`scripts/`](scripts/) and share the same data model in [`scripts/chart_data.py`](scripts/chart_data.py):

| Script | Output | Use it for |
| --- | --- | --- |
| `scripts/generate_chart.py` | Static PNG image | Slides, documents, reports |
| `scripts/generate_page.py` | Self-contained interactive HTML page | Exploring the data with hover details and live filtering |

Each renderer loads the CSV once into shared typed model records containing the
parsed family, effort, score, cost, source color, and optional model URL.
Command-line input is translated at each entry point into focused, immutable
configuration dataclasses for shared filters, chart text, figure rendering, and
page assembly; renderer internals do not depend on `argparse.Namespace`.

The interactive-page source is separated by responsibility while keeping
`generate_page.py` as the stable CLI entry point:

- `scripts/page_data.py` builds the serialized chart payload and configuration.
- `scripts/page_builder.py` loads and embeds the page assets.
- `scripts/page_assets/` contains the HTML template, CSS, and focused browser
  JavaScript modules for chart math, filter state, SVG rendering, and UI
  orchestration.
  - `base.css` contains framework-independent layout, responsive, and chart
    structure.
  - `themes/native.css` contains the default visual theme. The typed theme
    registry keeps theme selection isolated from chart and filter behavior.
  - `chart_math.js` contains formatting, tick, and collision helpers.
  - `filter_state.js` owns filter bounds, selections, matching, and faceting.
  - `chart_renderer.js` owns the responsive SVG, labels, and tooltip rendering.
  - `app.js` binds controls and browser events and initializes the page.

These build-time assets are resolved relative to the scripts directory and are
inlined into the generated HTML, so the published page remains a single
self-contained file.

The data export is split the same way, keeping the volatile browser boundary
isolated behind the `ModelSource` protocol:

- `scripts/export_pipeline.py` holds the source-agnostic pipeline — filtering,
  ordering, de-duplication, CSV validation, and atomic CSV writing. It is
  standard-library only, so it imports and tests without a browser driver.
- `scripts/export_source.py` holds the only Playwright-dependent code: the site
  URL, chart selectors, and the in-page extraction script.
- `scripts/export_artificial_analysis_csv.py` stays the CLI entry point and just
  wires the source to the pipeline.

GitHub automation is configured with two workflows in [`.github/workflows/`](.github/workflows/):

- `data-export.yml` refreshes the original source data in `data/data.csv` on a daily schedule or on demand.
- `deploy-pages.yml` builds `src/index.html` from the exported CSV and deploys it to GitHub Pages.

## Data source

Model and benchmark data originates from
[Artificial Analysis](https://artificialanalysis.ai/models). Model Meridian is
an independent visualization and is not affiliated with the original source.

## Requirements

- Python 3.10 or newer
- Matplotlib (required for the PNG renderer only)
- Playwright with Chromium (required for live CSV refreshes only)

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
python -m playwright install --with-deps chromium
```

## Testing

Run the standard-library characterization suite:

```powershell
python -m unittest discover -s tests -v
```

The tests cover model parsing, CSV loading and filtering, series ordering and
color assignment, interactive-page payload and self-contained output, static
PNG generation, export sorting and CSV validation, and the export pipeline
driven by an in-memory stand-in for the browser source.

## Usage

### Static chart

Pass the input CSV file as the positional argument:

```powershell
python scripts\generate_chart.py data\data.csv
```

By default, the image is written next to the CSV with a `.png` extension. The
command above creates `data\data.png`.

Choose a different output path:

```powershell
python scripts\generate_chart.py data\data.csv -o out\chart.png
```

Create a less crowded chart by filtering the data:

```powershell
python scripts\generate_chart.py data\data.csv `
  -o out\frontier.png `
  --min-score 33 `
  --max-cost 12
```

Filter by one or more family-name substrings:

```powershell
python scripts\generate_chart.py data\data.csv --families GPT Claude Gemini
```

Run `python scripts\generate_chart.py --help` for all available options.

### Interactive page

```powershell
python scripts/generate_page.py data\data.csv -o src\index.html
```

By default the page is written next to the CSV with an `.html` extension. Open
the file directly in a browser, or publish it as a static page — it embeds its
data and has no external dependencies.

Select the visual theme explicitly:

```powershell
python scripts\generate_page.py data\data.csv -o src\index.html --theme native
```

`native` is currently the only available theme and remains the default. The
theme seam keeps framework-independent layout and chart behavior separate from
replaceable visual styling so additional themes can be evaluated without
changing the page logic.

### GitHub Pages deployment

The repository uses two chained, non-agentic workflows for a daily refresh and
deployment flow:

```powershell
python scripts/export_artificial_analysis_csv.py --output-dir data
python scripts/generate_page.py data\data.csv -o src\index.html
```

`data-export.yml` runs daily at 02:00 UTC (and on demand), validates the live
export, replaces `data/data.csv`, and commits it only when data changed.
`deploy-pages.yml` runs after a successful export, generates `src/index.html`,
uploads `src/` as the Pages artifact, and deploys it. It can also be started
manually to publish the currently committed CSV. This deterministic script flow
does not require the custom Copilot agent at runtime.

The page supports:

- **Hover details** — point at any marker for the model name, score, cost,
  family, reasoning effort, fallback flag, and source URL.
- **Synchronized filters** — search, score, cost, family, and reasoning effort
  narrow the applicable choices and slider ranges in the other filter groups.
  Broadening a filter restores wider choices without losing slider thresholds
  explicitly chosen by the user.
- **Multi-term search** — separate terms with commas (for example
  `gpt-6, claude opus, gemini`) to show every model matching any term.
- **Score and cost sliders** — raise the minimum score or lower the maximum cost.
- **Reasoning effort and family checkboxes** — toggle individual series.
- **Display toggles** — connect efforts within a family, show family labels, and
  show per-point effort labels.
- **Responsive wide-screen layout** — ultrawide viewports use a height-aware,
  wider chart canvas so the lower axis and status remain visible without
  stretching the plot.

`generate_page.py` accepts the same `--min-score`, `--max-cost`, `--families`,
and `--top` flags to bake a starting subset into the page.

## CSV format

The CSV must contain these columns:

| Column | Description |
| --- | --- |
| `model` | Model name, optionally ending in a reasoning effort in parentheses |
| `cost_per_task_usd` | Positive numeric cost per benchmark task |
| `intelligence_index` | Numeric intelligence score |
| `color` | Model vendor or family color as a hex value |

An optional `model_url` column is shown in the interactive page's hover details.
Additional columns are allowed and ignored by both generators.

Example:

```csv
model,cost_per_task_usd,intelligence_index,color
GPT-6 Astra (low),0.80,46.0,#1f1f1f
GPT-6 Astra (medium),1.20,49.5,#1f1f1f
GPT-6 Astra (max),1.75,52.7,#1f1f1f
Kimi K2.6,1.55,43.6,#047AFE
```

Rows with a missing model, invalid numeric values, non-finite values, or a
non-positive cost are skipped. If no usable rows remain, the script exits with
an error.

## Model-name parsing

Text before the final parenthesized value is treated as the model family.
Models with the same family are connected in reasoning-effort order.

| Model value | Family | Reasoning effort |
| --- | --- | --- |
| `GPT-6 Astra (xhigh)` | `GPT-6 Astra` | `xhigh` |
| `Claude Opus 5.5 (max with fallback)` | `Claude Opus 5.5` | `max` |
| `Kimi K2.6` | `Kimi K2.6` | none |

Supported effort ordering is:

`non-reasoning`, `reasoning`, `minimal`, `low`, `medium`, `high`, `xhigh`,
`max`.

Unknown effort names remain supported and are ordered after the known values.
The phrase `with fallback` is displayed as a separate fallback annotation.

## Options

Shared by both generators:

| Option | Purpose |
| --- | --- |
| `-o`, `--output` | Set the output file path |
| `--min-score` | Include scores at or above the given value |
| `--max-cost` | Include costs at or below the given value |
| `--families` | Include families matching one or more substrings |
| `--top` | Include only the highest-scoring N families |
| `--title` | Set the chart title |
| `--xlabel`, `--ylabel` | Set axis labels |
| `--footnote` | Set the chart footnote |

`generate_chart.py` only:

| Option | Purpose |
| --- | --- |
| `--no-effort-labels` | Hide labels attached to individual effort points |
| `--width`, `--height` | Set figure dimensions in inches |
| `--dpi` | Set output resolution |
| `--family-fontsize` | Set family-label font size |
| `--effort-fontsize` | Set effort-label font size |

`generate_page.py` only:

| Option | Purpose |
| --- | --- |
| `--subtitle` | Set the text shown under the page title |
