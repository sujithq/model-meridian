# Artificial Analysis chart generator

[![AI Ready](https://img.shields.io/badge/AI--Ready-yes-brightgreen?style=flat)](https://github.com/johnpapa/ai-ready)

Generate a labelled model intelligence-versus-cost chart from a CSV file. Models
in the same family are connected across reasoning-effort levels, while models
with only one data point are shown as diamonds.

The chart uses a logarithmic cost axis, colors from the input data, and
collision-aware labels. It is designed to produce charts similar to
[`data/example-chart.png`](data/example-chart.png).

## Requirements

- Python 3.10 or newer
- Matplotlib

Install the dependency:

```powershell
python -m pip install matplotlib
```

## Usage

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

## CSV format

The CSV must contain these columns:

| Column | Description |
| --- | --- |
| `model` | Model name, optionally ending in a reasoning effort in parentheses |
| `cost_per_task_usd` | Positive numeric cost per benchmark task |
| `intelligence_index` | Numeric intelligence score |
| `color` | Model vendor or family color as a hex value |

Additional columns are allowed and ignored by the chart generator.

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

| Option | Purpose |
| --- | --- |
| `-o`, `--output` | Set the output image path |
| `--min-score` | Include scores at or above the given value |
| `--max-cost` | Include costs at or below the given value |
| `--families` | Include families matching one or more substrings |
| `--top` | Include only the highest-scoring N families |
| `--no-effort-labels` | Hide labels attached to individual effort points |
| `--title` | Set the chart title |
| `--xlabel`, `--ylabel` | Set axis labels |
| `--footnote` | Set the chart footnote |
| `--width`, `--height` | Set figure dimensions in inches |
| `--dpi` | Set output resolution |
| `--family-fontsize` | Set family-label font size |
| `--effort-fontsize` | Set effort-label font size |
