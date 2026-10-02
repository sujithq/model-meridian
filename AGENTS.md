# Repository guidance

## Working agreements

- The renderers are `generate_chart.py` (static PNG) and `generate_page.py` (interactive HTML); keep both usable with a CSV path as the positional argument.
- CSV loading, model-family parsing, effort ordering and series colouring live in `chart_data.py`; both renderers must stay on that shared logic rather than reimplementing it.
- Keep CSV parsing tolerant of extra columns, but preserve the required `model`, `cost_per_task_usd`, `intelligence_index`, and `color` fields.
- Treat model-family parsing and reasoning-effort ordering as part of the chart's output contract.
- Keep the generated HTML self-contained; do not add a runtime CDN or external asset dependency.
- Update `README.md` when CLI arguments, input requirements, or generated output behavior change.
- Use the dependency versions declared in `requirements.txt`; do not add an undeclared runtime dependency.

## Commands

```powershell
python -m pip install -r requirements.txt
python -m py_compile chart_data.py generate_chart.py generate_page.py
python generate_chart.py data\data.csv -o out\chart.png
python generate_page.py data\data.csv -o out\index.html
```

The repository currently has no automated test suite. For chart behavior changes, run the example commands and inspect the generated PNG and HTML output.

## Maintenance matrix

| Change | Also update |
| --- | --- |
| CLI argument or output behavior in `generate_chart.py` or `generate_page.py` | `README.md`, the CLI examples in CI |
| Shared parsing or series logic in `chart_data.py` | Both renderers, then re-verify PNG and HTML output |
| Runtime dependency imports in any script | `requirements.txt` |
| Required CSV columns or model-name parsing | `README.md`, `data\data.csv` example/fixtures |

## Done means

- `python -m py_compile chart_data.py generate_chart.py generate_page.py` exits successfully.
- The documented example commands generate a readable PNG and a working HTML page from `data\data.csv`.
- Interactive page changes were verified in a browser, including hover details and each filter control.
- `README.md` and `requirements.txt` reflect any changed interface or dependency.

## Never merges without a human

A person has to have **read this diff** before it lands. Telling an agent "merge it when you're done" is
approving a goal, not this change — so it does not count for anything on this list. Everywhere else it counts
fine, which is the point of having a list.

- Changes to `.github/workflows/**`.
- Changes that alter the documented CSV input contract.
