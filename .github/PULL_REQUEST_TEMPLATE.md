## Description

<!-- What changed and why? -->

## Changes

- 

## How to test

```powershell
python -m py_compile scripts\chart_data.py scripts\generate_chart.py scripts\generate_page.py scripts\export_artificial_analysis_csv.py
python scripts\generate_chart.py data\data.csv -o out\chart.png
python scripts\generate_page.py data\data.csv -o src\index.html
```

## Checklist

- [ ] The documented CLI and CSV contract remain accurate.
- [ ] `requirements.txt` includes any new runtime dependency.
- [ ] The validation commands pass.
- [ ] Generated chart output was inspected when chart behavior changed.
- [ ] Interactive page changes were verified in a browser (hover details and filters).
