# Repository guidance

## Working agreements

- The renderers are `scripts/generate_chart.py` (static PNG) and `scripts/generate_page.py` (interactive HTML); keep both usable with a CSV path as the positional argument.
- CSV loading, model-family parsing, effort ordering and series colouring live in `scripts/chart_data.py`; both renderers must stay on that shared logic rather than reimplementing it.
- CLI parsing stays in the renderer entry points and translates arguments into focused configuration dataclasses; renderer internals must not depend on `argparse.Namespace`.
- Interactive-page payload construction lives in `scripts/page_data.py`; document assembly and build-time asset loading live in `scripts/page_builder.py`.
- Interactive-page HTML, CSS and browser JavaScript live in `scripts/page_assets/`; keep `chart_math.js`, `filter_state.js`, `chart_renderer.js`, and `app.js` focused on their named responsibility, resolve them relative to the scripts directory, and embed them in that dependency order.
- Framework-independent page structure lives in `scripts/page_assets/base.css`; replaceable visual styling lives under `scripts/page_assets/themes/`. Register themes through the typed theme registry in `scripts/page_builder.py`, keep `native` as the default unless an intentional output change is approved, and never add a runtime CDN dependency.
- Vendored framework CSS lives in a versioned directory under `scripts/page_assets/vendor/` with its upstream license. Pin exact versions, keep framework-specific corrections in a small theme adapter, and verify vendored CSS contains no external imports or HTTP asset references.
- Tailwind source lives in `scripts/page_assets/theme_sources/tailwind.css`; its pinned build dependencies live in `package.json`/`package-lock.json`, and `npm run build:themes` must reproduce the committed versioned CSS artifact.
- `scripts/export_artificial_analysis_csv.py` is the deterministic data-refresh entry point used by automation; it only wires a source to the pipeline.
- Export filtering, ordering, de-duplication, validation and CSV writing live in `scripts/export_pipeline.py` and must stay standard-library only so they are testable without a browser driver. Site selectors, the in-page extraction script, and the Playwright import stay in `scripts/export_source.py` behind the `ModelSource` protocol.
- Keep CSV parsing tolerant of extra columns, but preserve the required `model`, `cost_per_task_usd`, `intelligence_index`, and `color` fields.
- Treat model-family parsing and reasoning-effort ordering as part of the chart's output contract.
- Keep the generated HTML self-contained; do not add a runtime CDN or external asset dependency.
- Update `README.md` when CLI arguments, input requirements, or generated output behavior change.
- Use the dependency versions declared in `requirements.txt`; do not add an undeclared runtime dependency.
- Use exact versions from `package-lock.json` for theme build dependencies; Node.js is not part of normal page generation.

## Commands

```powershell
python -m pip install -r requirements.txt
npm ci
npm run build:themes
python -m py_compile scripts\chart_data.py scripts\generate_chart.py scripts\generate_page.py scripts\page_data.py scripts\page_builder.py scripts\export_pipeline.py scripts\export_source.py scripts\export_artificial_analysis_csv.py
python -m unittest discover -s tests -v
python scripts\generate_chart.py data\data.csv -o out\chart.png
python scripts\generate_page.py data\data.csv -o src\index.html
```

The repository uses standard-library `unittest` characterization tests. For
chart behavior changes, also run the example commands and inspect the generated
PNG and HTML output.

## Maintenance matrix

| Change | Also update |
| --- | --- |
| CLI argument or output behavior in `scripts/generate_chart.py` or `scripts/generate_page.py` | `README.md`, the CLI examples in CI |
| Shared parsing or series logic in `scripts/chart_data.py` | Both renderers, then re-verify PNG and HTML output |
| Shared configuration dataclasses | Both renderers and their characterization tests |
| Interactive page payload, assembly, or assets | `scripts/page_data.py`, `scripts/page_builder.py`, and `scripts/page_assets/`, then re-verify the self-contained HTML |
| Page theme registry or theme assets | `scripts/generate_page.py`, `scripts/page_builder.py`, theme tests, and `README.md`, then compare desktop, mobile, and ultrawide output |
| Vendored CSS framework version | Its versioned asset directory, upstream license, theme adapter, tests, and the framework version documented in `README.md` |
| Tailwind theme source or build dependency | `package.json`, `package-lock.json`, the compiled versioned Tailwind asset, theme tests, and `README.md` |
| Data-export behavior in `scripts/export_pipeline.py` or `scripts/export_artificial_analysis_csv.py` | `README.md`, `requirements.txt`, and the export workflow |
| Site selectors or the in-page extraction script in `scripts/export_source.py` | `scripts/export_pipeline.py` only if the `ModelSource` protocol changes |
| GitHub Pages output path | `README.md`, `.gitignore`, and the deploy workflow |
| Runtime dependency imports in any script | `requirements.txt` |
| Required CSV columns or model-name parsing | `README.md`, `data\data.csv` example/fixtures |

## Done means

- `python -m py_compile scripts\chart_data.py scripts\generate_chart.py scripts\generate_page.py scripts\page_data.py scripts\page_builder.py scripts\export_pipeline.py scripts\export_source.py scripts\export_artificial_analysis_csv.py` exits successfully.
- `python -m unittest discover -s tests -v` passes.
- The documented example commands generate a readable PNG and a working HTML page from `data\data.csv`.
- Interactive page changes were verified in a browser, including hover details and each filter control.
- `README.md` and `requirements.txt` reflect any changed interface or dependency.

## Never merges without a human

A person has to have **read this diff** before it lands. Telling an agent "merge it when you're done" is
approving a goal, not this change — so it does not count for anything on this list. Everywhere else it counts
fine, which is the point of having a list.

- Changes to `.github/workflows/**`.
- Changes that alter the documented CSV input contract.
