# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Model Meridian product branding for the interactive page and static chart.
- Responsive, non-distorting chart sizing for ultrawide screens.
- Characterization tests for shared chart data, both renderers, and CSV export
  transformations and validation.
- CSV-driven intelligence-versus-cost chart generation.
- Interactive self-contained HTML page with hover details and live filtering by
  search text, score, cost, reasoning effort and model family.
- Synchronized family and reasoning-effort options that respond to search,
  numeric bounds, and one another while preserving existing selections, plus
  score and cost slider ranges that adapt to the active text and categories.
- Comma-separated multi-term search matching any of the given models or
  families.
- Shared `chart_data` module so the image and page renderers group, order and
  colour models identically.
- Model-family and reasoning-effort parsing with collision-aware labels.
- Command-line filtering and output customization.
- Repository guidance and contribution workflow files.
- Daily data-refresh and GitHub Pages deployment automation.
- Python entry points organized under `scripts/`.

### Changed

- Load complete typed model records in one CSV pass shared by both renderers.
