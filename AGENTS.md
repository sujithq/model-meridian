# Repository guidance

## Working agreements

- The chart entry point is `generate_chart.py`; keep the CLI usable with a CSV path as its positional argument.
- Keep CSV parsing tolerant of extra columns, but preserve the required `model`, `cost_per_task_usd`, `intelligence_index`, and `color` fields.
- Treat model-family parsing and reasoning-effort ordering as part of the chart's output contract.
- Update `README.md` when CLI arguments, input requirements, or generated output behavior change.
- Use the dependency versions declared in `requirements.txt`; do not add an undeclared runtime dependency.

## Commands

```powershell
python -m pip install -r requirements.txt
python -m py_compile generate_chart.py
python generate_chart.py data\data.csv -o out\chart.png
```

The repository currently has no automated test suite. For chart behavior changes, run the example command and inspect the generated PNG.

## Maintenance matrix

| Change | Also update |
| --- | --- |
| CLI argument or output behavior in `generate_chart.py` | `README.md`, the CLI example in CI |
| Runtime dependency imports in `generate_chart.py` | `requirements.txt` |
| Required CSV columns or model-name parsing | `README.md`, `data\data.csv` example/fixtures |

## Done means

- `python -m py_compile generate_chart.py` exits successfully.
- The documented example command generates a readable PNG from `data\data.csv`.
- `README.md` and `requirements.txt` reflect any changed interface or dependency.

## Never merges without a human

A person has to have **read this diff** before it lands. Telling an agent "merge it when you're done" is
approving a goal, not this change — so it does not count for anything on this list. Everywhere else it counts
fine, which is the point of having a list.

- Changes to `.github/workflows/**`.
- Changes that alter the documented CSV input contract.
