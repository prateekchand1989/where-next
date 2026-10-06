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
- NWS point forecasts with a 15-minute cache, kept separate from warehouse scores.
- FEMA county hazard context and an optional FEMA risk map view; warehouse screening remains the default map and ranking.
- Optional AI-generated interpretation of supplied county evidence, with deterministic summaries retained.
- Deterministic tests for scoring, electricity expense, weight sensitivity, and failure handling; app behavior checked with Streamlit AppTest.

## Not yet implemented

Actual property screening, road routing, customer-order upload, rents, carrier prices, and a hosted public deployment. START_HERE.md tells you how to add and validate these in stages. County evidence summaries remain explicit code-generated explanations; the separate optional AI output is clearly labeled.

## Start on Windows

Open a terminal in this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Use the URL shown in the terminal, usually http://localhost:8501. The processed data is bundled, so first startup requires no Census, EIA, NWS, or Gemini account. NWS is contacted only when you click its button.

## Optional AI interpretation

Select counties and click **Explain selected locations**. Python builds a structured evidence object with an explicit field allowlist. An optional OpenAI provider sends that JSON and grounding instructions to the [Responses API](https://developers.openai.com/api/docs/guides/structured-outputs), using [`gpt-4.1-mini`](https://developers.openai.com/api/docs/models/gpt-4.1-mini) by default. No additional package is required. Model tools and external retrieval are disabled; application code, credentials, arbitrary session state, and raw error details are never included. Requests set `store=false` and have a 30-second timeout.

The evidence object contains only:

- `schema_version`, `baseline_year`, `scenario`, `candidate_states`, and `priority_weights_pct` keyed by the four business-priority labels.
- `current_leader` and `selected_counties`: `fips`, `county`, `state`, `score`, `complete`, `reach_250mi`, `employment`, `annual_pay`, `electricity_cents_kwh`, `labor_status`, and `percentile_components` keyed by the four priority labels. The current leader is the highest-ranked complete county in the candidate states and may be outside the selected comparison.
- `annual_electricity_consumption_kwh` and each selected county's `illustrative_annual_electricity_expense_usd`, calculated by Python if consumption was entered.
- Each selected county's `fema`: the exact NRI fields listed below. `fema_source` contains only `status`, `version`, `source_url`, `retrieved_utc`, and `source_data_updated_utc`.
- Each selected county's `nws`: representative-point `lat`/`lon` and separate alerts/forecast statuses. Results enter session evidence only after that session's NWS button is clicked. Successful results include `checked_utc`, `url`; alerts contain `event`, `headline`, `expires`, `area`; forecasts contain `updated`, `generated_at` and up to four periods with `name`, `temperature`, `temperatureUnit`, `shortForecast`, `windSpeed`, `windDirection`. Data older than 15 minutes is marked stale and its weather details are omitted. Failed or unfetched weather is explicit and never interpreted as no alerts.
- `sensitivity`: selected `factor` and scenarios with `name`, `weights_pct`, `top_five` (`fips`, `county`, `state`, `rank`, `score`), and `top_three_changes` (`fips`, `county`, `state`, `rank`, `change`). These are the application's already-calculated scenarios.

Missing values become the explicit string `Unavailable`, never zero or invented estimates. The model is instructed to use only this evidence, never recalculate scores, and explain unavailable evidence. It cannot infer rents, freight rates, tax incentives, property availability, delivery guarantees, hiring availability, property-level flood risk, or savings estimates. FEMA remains community hazard context; NWS remains point weather. Screening scores remain illustrative comparisons rather than validated recommendations.

The output is labeled **AI-generated interpretation** with four sections: why the current leader ranks first, selected-county trade-offs, risk/resilience considerations, and data still missing for a real site decision. The prompt targets 200–250 words; responses exceeding 250 words including headings, incomplete responses, refusals, malformed results, and API errors fall back to an unavailable notice. Structure and length are checked in Python; prose grounding still needs human review. Existing code-generated evidence summaries remain available.

Credentials are read only from Streamlit secrets or environment variables. Configure `OPENAI_API_KEY` in your private `.streamlit/secrets.toml` (already Git-ignored) or the environment. Optional settings are `OPENAI_MODEL` (default `gpt-4.1-mini`) and `AI_PROVIDER` (`openai` by default; `none` disables AI). Secrets take precedence over environment settings. For example, set these in your private secrets file, replacing the placeholder locally:

```toml
OPENAI_API_KEY = "your-api-key"
OPENAI_MODEL = "gpt-4.1-mini"
AI_PROVIDER = "openai"
```

No key is needed to use the deterministic app. Without a configured key, clicking the button shows **AI interpretation is not configured.** No model request occurs on ordinary slider, map, selection, or sensitivity changes. A saved interpretation is kept only in the current session and hidden when its evidence changes; another explicit click is required to regenerate it. Clicking the AI button sends supplied public-data evidence and your priorities/consumption input to OpenAI and may incur provider charges. Tests mock all model responses and require no live AI API.

## Rebuild the baseline

```powershell
.\.venv\Scripts\python.exe prepare_data.py
```

This downloads five official files into `data/raw/` and produces the three processed files. Raw files are not included in Git commits. Valid raw files are reused; remove a specific raw file to fetch it again. This is a frozen 2024 baseline, not an automatic latest-year updater. EIA's live file address can change its reference year; the script checks for 2024 and stops for review rather than silently mixing vintages.

## Methodology

### FEMA National Risk Index context

The separate FEMA snapshot uses the official [National Risk Index Counties layer](https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Counties/FeatureServer/0), published by `FEMA_NationalRiskIndex` ([source item and release metadata](https://www.arcgis.com/home/item.html?id=39485e8035d446a5bff03259508ae355)). The current source inspected for this integration is **December 2025, version 1.20.0**. The service reports its data update as December 16, 2025, 07:37:01 UTC. Retrieved October 5, 2026, 10:35 PM EDT (October 6, 02:35 UTC); exact retrieval time, query, field aliases, response hash, and join coverage are recorded in `data/fema_sources.json`.

The live schema was inspected before field selection. Selected fields are:

| FEMA field | Use |
| --- | --- |
| `STCOFIPS` | Five-character county FIPS; the only join key |
| `RISK_SCORE`, `RISK_RATNG` | Overall community risk score and rating |
| `EAL_VALT` | County aggregate expected annual loss, USD/year |
| `IFLD_RISKS`, `IFLD_RISKR` | Inland flooding risk score and rating |
| `CFLD_RISKS`, `CFLD_RISKR` | Coastal flooding risk score and rating |
| `WNTW_RISKS`, `WNTW_RISKR` | Winter weather risk score and rating |
| `HRCN_RISKS`, `HRCN_RISKR` | Hurricane risk score and rating |
| `NRI_VER` | Per-record source release |

The snapshot matches **262 of 262** Where Next counties: **0 unmatched, 0 duplicate FIPS**. There are 184 unavailable coastal-flood scores; FEMA applicability ratings such as `Not Applicable` are retained. Missing values remain missing, never converted to zero. Duplicate FIPS in either input abort preparation with a clear error. County names are never used to join.

Refresh FEMA separately, without rebuilding the warehouse baseline:

```powershell
.\.venv\Scripts\python.exe prepare_fema.py
```

Each refresh reads official publisher/release metadata and the live layer schema, then validates the selected fields and a one-to-one FIPS join. Schema errors and truncated responses stop preparation for review. Outputs are `data/fema_counties.csv` and `data/fema_sources.json`; raw evidence is saved under the Git-ignored `data/raw/`. The app reads the bundled snapshot locally without a live FEMA download or paid API. Missing or invalid FEMA files leave screening usable with an unavailable-data notice.

FEMA is **long-term hazard and resilience context**, based on historical/modelled community data. NWS provides **current / near-term operational weather** at a representative point. Neither changes scores, weights, sensitivity, or rankings. FEMA risk scores are relative indices, not the probability that a particular warehouse will be damaged. Overall community risk incorporates loss, social vulnerability, and resilience. Expected annual loss includes county-wide buildings, agriculture, and monetized population losses; it is not a warehouse loss estimate or an insurance quote. A county flood score is not a property-level flood assessment and does not replace flood maps, site investigation, or engineering. FEMA's hazard inputs span different historical periods; the release date is not a common observation year or a future climate forecast. FEMA source county boundaries use 2021 TIGER/Line (2024 for Connecticut), while this app retains its existing 2024 Census map boundaries.

This product uses FEMA National Risk Index data but is not endorsed by FEMA. FEMA cannot vouch for analyses derived after retrieval.

Sensitivity first normalizes the current slider weights to 100%. The chosen factor is adjusted by minus/plus 10 percentage points, clamped to 0–100%. The remaining total is shared in the other factors' existing proportions; if they were all zero, it is shared equally. Full-precision weights drive scoring. Display percentages use largest-remainder rounding to two decimals and total 100%. Top-five ranks and top-three entries/exits refer to the selected states, after scoring the full complete five-state universe.

Scores are illustrative percentile-weighted indicators calculated against the complete five-state candidate set before a state filter is applied. Market reach is U.S. population allocated to county representative points within 250 straight-line miles, not road access or guaranteed service coverage. BLS annual industry pay is not a posted hourly wage. Employment is not hiring availability. EIA state commercial prices are not a property's electricity tariff. All four indicators are required for the starter score, including if one weight is zero.

Original code is provided under the MIT license. Source data remains subject to its agencies' notices and attribution requirements. See `data/sources.json` for exact downloaded URLs and file hashes.
