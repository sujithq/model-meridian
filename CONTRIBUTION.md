# Contributing to Model Meridian

Thank you for helping improve Model Meridian. Contributions may include bug
fixes, tests, documentation, renderer improvements, theme refinements, and data
export reliability.

By participating, you agree to follow the
[Code of Conduct](CODE_OF_CONDUCT.md). Report security-sensitive findings
privately as described in the [Security Policy](SECURITY.md), not in a public
issue or pull request.

## Before you start

- Search existing issues and pull requests before opening duplicate work.
- Open an issue before a large behavioral, architectural, dependency, or CSV
  contract change.
- Keep pull requests focused and avoid unrelated cleanup.
- Never commit credentials, tokens, private data, or generated secrets.

## Development setup

Model Meridian requires Python 3.10 or newer. Node.js is needed only when
rebuilding the committed Tailwind theme artifact. Playwright and Chromium are
needed only for live CSV exports.

```powershell
python -m pip install -r requirements.txt
python -m playwright install --with-deps chromium
npm ci
```

## Project structure

- `scripts/chart_data.py` owns CSV loading, model parsing, effort ordering,
  filters, and shared colors.
- `scripts/generate_chart.py` renders static PNG charts.
- `scripts/generate_page.py` renders self-contained interactive HTML.
- `scripts/page_data.py` builds the interactive payload.
- `scripts/page_builder.py` assembles the page and embeds local assets.
- `scripts/page_assets/` contains page templates, styles, themes, and browser
  JavaScript.
- `scripts/export_pipeline.py` owns source-independent export processing.
- `scripts/export_source.py` contains the Playwright-specific source adapter.
- `tests/` contains the standard-library `unittest` characterization suite.

Keep shared parsing and filtering behavior in `chart_data.py`; do not duplicate
it in a renderer. Keep generated HTML self-contained and do not add runtime CDN
or external asset dependencies.

## Making changes

- Preserve both renderer CLIs: each accepts a CSV path as its positional
  argument.
- Preserve the required CSV columns: `model`, `cost_per_task_usd`,
  `intelligence_index`, and `color`.
- Treat model-family parsing and reasoning-effort ordering as output contracts.
- Translate CLI input into the focused configuration dataclasses instead of
  passing `argparse.Namespace` into renderer internals.
- Keep browser-specific selectors and extraction logic behind the
  `ModelSource` boundary.
- Pin vendored framework and Tailwind build dependencies, retain their upstream
  licenses, and avoid undeclared runtime dependencies.
- Update `README.md` when CLI arguments, input requirements, dependencies, or
  generated output behavior change.

## Validation

Run the checks relevant to your change:

```powershell
python -m py_compile scripts\chart_data.py scripts\generate_chart.py scripts\generate_page.py scripts\page_data.py scripts\page_builder.py scripts\export_pipeline.py scripts\export_source.py scripts\export_artificial_analysis_csv.py
python -m unittest discover -s tests -v
python scripts\generate_chart.py data\data.csv -o out\chart.png
python scripts\generate_page.py data\data.csv -o src\index.html
```

If Tailwind sources or build dependencies changed, also run:

```powershell
npm ci
npm run build:themes
```

Inspect chart output when rendering changes. For interactive-page changes,
verify hover details, filters, and responsive behavior. Confirm that the
generated HTML remains self-contained.

## Pull requests

1. Use a short branch name that describes the change.
2. Add or update tests for behavioral changes.
3. Complete the repository pull request template.
4. List every validation command you ran and whether it passed.
5. Call out any validation that was not run and explain why.
6. Keep generated and vendored changes reproducible.

Changes to `.github/workflows/**` and changes to the documented CSV input
contract require a person to read the final diff before merge.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/), for example:

```text
fix(page): preserve filters after resize
feat(chart): add configurable family labels
docs: add contributor guidance
```

Use `feat` for backward-compatible features, `fix` for bug fixes, and a
`BREAKING CHANGE:` footer when a change intentionally breaks the public CLI,
CSV contract, or generated output contract.

## License

By contributing, you agree that your contribution will be licensed under the
repository's [MIT License](LICENSE).
