# Where Next?

A working warehouse-location screening starter using public U.S. data.

Start with **START_HERE.md**, which contains the 17-step Windows-oriented build guide, exact download links, coding prompts, checkpoints, troubleshooting, and deployment instructions.

## What already works

- 262 counties in Maryland, New Jersey, New York, Ohio, and Pennsylvania.
- Real 2024 Census population, Census county boundaries and representative points, private-sector BLS QCEW NAICS 493 employment/pay, and EIA commercial electricity benchmarks.
- 121 counties with complete data receive scores; 141 incomplete counties remain unranked.
- Interactive Plotly county map with a contiguous-U.S. backdrop and no commercial map token.
- Editable weights, two illustrative business presets, three-county comparison, source metadata, CSV export.
- Weight sensitivity from current priorities: test any factor at current, minus 10, and plus 10 percentage points, with top-five rankings and top-three membership changes.
- On-demand NWS alerts at a county representative point, with unavailable-data handling.
- Deterministic tests for scoring, electricity expense, weight sensitivity, and failure handling; app behavior checked with Streamlit AppTest.

## Not yet implemented

AI interpretation, generated AI explanations, FEMA risk layers, actual property screening, road routing, customer-order upload, rents, carrier prices, and a hosted public deployment. START_HERE.md tells you how to add and validate these in stages. The built-in explanation is an explicit code-generated evidence summary, not an LLM output.

## Start on Windows

Open a terminal in this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Use the URL shown in the terminal, usually http://localhost:8501. The processed data is bundled, so first startup requires no Census, EIA, NWS, or Gemini account. NWS is contacted only when you click its button.

## Rebuild the baseline

```powershell
.\.venv\Scripts\python.exe prepare_data.py
```

This downloads five official files into `data/raw/` and produces the three processed files. Raw files are not included in Git commits. Valid raw files are reused; remove a specific raw file to fetch it again. This is a frozen 2024 baseline, not an automatic latest-year updater. EIA's live file address can change its reference year; the script checks for 2024 and stops for review rather than silently mixing vintages.

## Methodology

Sensitivity first normalizes the current slider weights to 100%. The chosen factor is adjusted by minus/plus 10 percentage points, clamped to 0–100%. The remaining total is shared in the other factors' existing proportions; if they were all zero, it is shared equally. Full-precision weights drive scoring. Display percentages use largest-remainder rounding to two decimals and total 100%. Top-five ranks and top-three entries/exits refer to the selected states, after scoring the full complete five-state universe.

Scores are illustrative percentile-weighted indicators calculated against the complete five-state candidate set before a state filter is applied. Market reach is U.S. population allocated to county representative points within 250 straight-line miles, not road access or guaranteed service coverage. BLS annual industry pay is not a posted hourly wage. Employment is not hiring availability. EIA state commercial prices are not a property's electricity tariff. All four indicators are required for the starter score, including if one weight is zero.

Original code is provided under the MIT license. Source data remains subject to its agencies' notices and attribution requirements. See `data/sources.json` for exact downloaded URLs and file hashes.
