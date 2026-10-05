# Execution report

Tested on 4 October 2026, U.S. Eastern time (5 October UTC), in a Linux Python 3.12.14 execution environment. Windows commands are supplied in the guide; Windows itself was not tested.

## What ran successfully

1. Downloaded the official Census 2024 county population CSV: 1,769,182 bytes.
2. Downloaded the official Census 2024 county representative-point ZIP: 141,679 bytes.
3. Downloaded the official Census 2024 county boundary ZIP: 900,230 bytes.
4. Downloaded the official BLS 2024 annual NAICS 493 CSV: 380,327 bytes.
5. Downloaded EIA Table 4 XLSX: 15,262 bytes; confirmed its title is 2024 and selected its Commercial column.
6. Parsed and joined the datasets: 262 unique candidate counties, all matched to map geometry.
7. Excluded BLS records ending in 999 that represent unknown/unallocated county locations; they are not additional counties.
8. Generated 121 complete county scores; 141 incomplete counties remain unranked.
9. Ran seven tests: geometry matching, missing data, direction of cost scoring/weight validation, determinism/ranges, distance calculation, HTML rejection, and weather failure handling. Result: 7 passed.
10. Executed Streamlit AppTest for initial startup: no app exceptions, one Plotly map figure, two tables.
11. Changed the Scenario control to Temperature-controlled with AppTest: no app exceptions.
12. Called live NWS point alerts near Lehigh County at 40.6140,-75.5900: valid FeatureCollection, zero active alerts at 2026-10-05T01:35:26Z. Zero was a valid response, not a network failure.

## Scenario outputs from the included snapshot

These are outputs of an illustrative proxy model, not verified investment recommendations.

| Preset | Rank 1 | Rank 2 | Rank 3 |
|---|---|---|---|
| General merchandise | Lackawanna PA: 88.875 | Northampton PA: 79.958 | Berks PA: 79.625 |
| Temperature-controlled | Lackawanna PA: 80.833 | Wood OH: 73.583 | Northampton PA: 73.250 |

The leader did not change; the shortlist did. The model was not tuned to make a particular county win.

## Failures discovered and addressed

- A Census ACS request without a key returned an HTML Missing Key page with HTTP 200. Starter uses the official population bulk download, validates file contents, and does not require that API.
- Many BLS rows are suppressed and carry zeros. Starter treats them as missing and does not score those counties.
- The EIA workbook has title/header rows and prices in cents/kWh. Parser locates the State header, checks the year, and uses the named Commercial column.
- The Gazetteer longitude header has trailing whitespace. Parser strips column names before joining.
- The legacy FEMA county ZIP and CSV addresses returned HTTP 502. An attempted guessed OpenFEMA NRI endpoint returned 404; it is not used in the starter. The guide makes FEMA a reviewed optional extension, not a startup dependency.

## What was not verified

- Actual browser visual rendering: browser launch was blocked by this execution environment's socket restrictions. The map figure and Streamlit server code executed, but a rendered map screenshot was not obtained. The guide includes an explicit browser checkpoint before further work.
- GitHub account creation, GitHub Desktop authentication, and Streamlit Cloud deployment in the user's accounts.
- Google account eligibility, API-key creation, free AI model quota, or an authenticated Gemini model call.
- FEMA live data retrieval or historical risk integration.
- Windows installation and performance on the user's hardware.

No guarantee is made that third-party services will remain available or that future package/data versions will behave identically. The bundled processed snapshot provides an offline starting point; optional services fail separately from the core rankings.
