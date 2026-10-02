## Description

<!-- What changed and why? -->

## Changes

- 

## How to test

```powershell
python -m py_compile chart_data.py generate_chart.py generate_page.py
python generate_chart.py data\data.csv -o out\chart.png
python generate_page.py data\data.csv -o out\index.html
```

## Checklist

- [ ] The documented CLI and CSV contract remain accurate.
- [ ] `requirements.txt` includes any new runtime dependency.
- [ ] The validation commands pass.
- [ ] Generated chart output was inspected when chart behavior changed.
- [ ] Interactive page changes were verified in a browser (hover details and filters).
