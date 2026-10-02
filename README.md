# Artificial Analysis chart generator

[![AI Ready](https://img.shields.io/badge/AI--Ready-yes-brightgreen?style=flat)](https://github.com/johnpapa/ai-ready)

Generate a labelled model intelligence-versus-cost chart from a CSV file. Models
in the same family are connected across reasoning-effort levels, while models
with only one data point are shown as diamonds.

The chart uses a logarithmic cost axis, colors from the input data, and
collision-aware labels. It is designed to produce charts similar to
[`data/example-chart.png`](data/example-chart.png).

Two renderers share the same data model in [`chart_data.py`](chart_data.py):

| Script | Output | Use it for |
| --- | --- | --- |
| `generate_chart.py` | Static PNG image | Slides, documents, reports |
| `generate_page.py` | Self-contained interactive HTML page | Exploring the data with hover details and live filtering |

## Requirements

- Python 3.10 or newer
- Matplotlib (required for the PNG renderer only)

Install the dependency:

```powershell
python -m pip install -r requirements.txt
```

## Usage

### Static chart

Pass the input CSV file as the positional argument:

```powershell
python generate_chart.py data\data.csv
```

By default, the image is written next to the CSV with a `.png` extension. The
command above creates `data\data.png`.

Choose a different output path:

```powershell
python generate_chart.py data\data.csv -o out\chart.png
```

Create a less crowded chart by filtering the data:

```powershell
python generate_chart.py data\data.csv `
  -o out\frontier.png `
  --min-score 33 `
  --max-cost 12
```

Filter by one or more family-name substrings:

```powershell
python generate_chart.py data\data.csv --families GPT Claude Gemini
```

Run `python generate_chart.py --help` for all available options.

### Interactive page

```powershell
python generate_page.py data\data.csv -o out\index.html
```

By default the page is written next to the CSV with an `.html` extension. Open
the file directly in a browser, or publish it as a static page — it embeds its
data and has no external dependencies.

The page supports:

- **Hover details** — point at any marker for the model name, score, cost,
  family, reasoning effort, fallback flag, and source URL.
- **Synchronized filters** — search, score, cost, family, and reasoning effort
  narrow the applicable choices and slider ranges in the other filter groups.
  Broadening a filter restores wider choices without losing slider thresholds
  explicitly chosen by the user.
- **Score and cost sliders** — raise the minimum score or lower the maximum cost.
- **Reasoning effort and family checkboxes** — toggle individual series.
- **Display toggles** — connect efforts within a family, show family labels, and
  show per-point effort labels.

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
