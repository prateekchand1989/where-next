# Where Next: the concrete 17-step build guide

For Prateek Chand. Written 4 October 2026, Eastern time.

## What you are building

An interactive warehouse-location screening application. A user chooses a business scenario and priorities; a county map, shortlist, and comparison explain the resulting trade-offs. The first version covers PA, NJ, NY, OH, and MD on a contiguous-U.S. backdrop. Public data supplies population, labor, energy, and weather context. AI will later interpret a request and explain calculations produced by code.

The supplied starter already performs the core data and scoring workflow. Start by running it. Then make one improvement at a time. You do not need to regenerate the application from a blank prompt.

Budget: software and public datasets can remain free. The optional Codex IDE route uses the ChatGPT Plus access you already pay for and is therefore zero additional cost, not a newly free subscription. A strictly free alternative is Google AI Studio's eligible free text model for writing/reviewing files manually. Both have usage limits. Gemini API usage for visitors is separate from your coding assistant; use an eligible free API model and leave billing disabled.

Read SMOKE_TEST.md first. It distinguishes what actually ran from account-dependent and visual checks that still require your computer.

## 1. Download and extract this starter

1. Download Where_Next_Tested_Starter.zip from the conversation.
2. In Windows File Explorer, right-click it and choose Extract All.
3. Open the extracted where-next folder.
4. Confirm you can see app.py, core.py, prepare_data.py, weather.py, requirements.txt, README.md, START_HERE.md, SMOKE_TEST.md, data, and tests.
5. In File Explorer enable View > Show > File name extensions, so app.py cannot accidentally become app.py.txt.

The processed data folder contains counties.csv, counties.geojson, and sources.json. Do not open and resave the CSV in Excel before running it: Excel can alter identifiers or number formats. Looking at it without saving is fine.

Expected result: the files are extracted. You are not trying to run files inside the ZIP.

## 2. Create your GitHub account and repository

1. Open https://github.com/signup and create a free account, or sign in to your existing one.
2. Open https://github.com/new.
3. Repository name: where-next.
4. Description: Public-data warehouse location screening with interactive maps and explainable trade-offs.
5. Choose Public if you are ready to share the included prototype code. Choose Private while developing if preferred; you can change visibility later. A public repository publishes its contents, so keep it to the supplied public-data project.
6. Leave Add README, Add .gitignore, and license initialization off. The starter supplies those files.
7. Click Create repository.

Expected result: an empty repository at https://github.com/YOUR-USERNAME/where-next. Save that URL.

Do not buy GitHub Copilot or a paid GitHub plan for this workflow.

## 3. Install your local tools

Install these from their official sites:

- Python: https://www.python.org/downloads/ — choose a supported 64-bit Python 3.12 or 3.13 installation. The test used Python 3.12.14 on Linux. If the site only offers newer versions, use a currently supported Streamlit-compatible Python version and retain a local installation check; do not assume every new Python release works with pinned dependencies immediately.
- VS Code: https://code.visualstudio.com/download.
- GitHub Desktop: https://desktop.github.com/download/.

If using a traditional Python Windows installer, select Add Python to PATH when offered. If using Python's newer install manager, follow its interpreter-install prompts. Close and reopen VS Code after installation.

Open VS Code > Terminal > New Terminal and enter:

```powershell
py --version
```

Expected result: Python 3.12.x or 3.13.x. If py is unrecognized but python --version works, substitute python for py in the one virtual-environment creation command below. Do not change every subsequent command.

## 4. Clone the repository and copy in the starter

1. Open GitHub Desktop and sign in to the same GitHub account.
2. Choose File > Clone repository > URL.
3. Paste your where-next repository URL.
4. Choose a local destination such as Documents\GitHub\where-next and click Clone.
5. Copy the CONTENTS of the extracted starter folder into this cloned folder. app.py should be directly inside Documents\GitHub\where-next, not inside a second where-next subfolder.
6. In GitHub Desktop, inspect the Changes list. The code, processed data, tests, and documentation should appear.
7. Enter the summary Add tested Where Next starter; click Commit to main, then Push origin.
8. Open the repository website and confirm app.py and requirements.txt are in its top level.

Expected result: GitHub contains the source and processed sample data. The .gitignore excludes your virtual environment, secrets, raw downloads, and caches.

## 5. Install the project's dependencies

1. In VS Code, choose File > Open Folder and select the CLONED where-next folder.
2. Open Terminal > New Terminal. The prompt should end with the where-next folder.
3. Run these commands one at a time:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

No environment activation command is necessary. Using the full Python executable path avoids common PowerShell execution-policy problems.

Expected result: 7 passed. The initial package installation may take several minutes. Do not close the terminal while it is installing.

If installation fails, copy the first relevant error plus the last 30 lines to your coding assistant. Do not ask it to rewrite the app. Ask it to diagnose the dependency installation with your Python version and Windows version. The listed packages were actually installed together in the test environment; Windows itself was not tested.

## 6. Run the existing application before editing it

In the same VS Code terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the Local URL printed in the terminal, normally http://localhost:8501. Keep that terminal open.

Check these things:

1. The title is Where Next?.
2. It reports 262 counties shown, 121 ranked, 141 incomplete under the initial five-state selection.
3. A county map is visible. The browser rendering is an explicit checkpoint because the execution environment could run the app but could not launch a browser for visual inspection.
4. The initial top three for the bundled baseline are Lackawanna PA, Northampton PA, and Berks PA.
5. Changing Scenario to Temperature-controlled updates scores. The preset sensitivity table includes Lackawanna PA, Wood OH, and Northampton PA for that preset.
6. The data-source expander shows the original sources.

If the app runs but the map is blank, take a screenshot and note any browser-console error. The starter uses a white-background MapLibre layer with bundled county geometry; it needs no Mapbox token. Ask the coding assistant to fix that specific rendering issue or replace it with a Plotly geo map using bundled topology. Do not accept a fake image as proof of an interactive map.

Expected result: a usable baseline before any new feature is added. Press Ctrl+C in the terminal to stop it. Run the same command to restart.

## 7. Choose your coding assistant and establish the working rules

Recommended for your existing subscription: VS Code's official Codex extension, published by OpenAI. Install from the VS Code Extensions panel or https://developers.openai.com/codex/ide/. Open its sidebar, sign in with ChatGPT, and use your existing plan limits. This is the code editor assistant, not the runtime AI service in your public app.

Strictly free fallback: open https://aistudio.google.com/, choose an available text model with a free allowance, provide the relevant files, and ask for complete replacement files. Save those files in VS Code and run the checks locally. Do not use its website-generation mode to convert this Python application into an unrelated JavaScript stack.

Paste this first:

```text
I am building Where Next, a public-data warehouse location screening tool.
Read README.md, START_HERE.md, SMOKE_TEST.md, app.py, core.py,
prepare_data.py, weather.py, and tests/test_core.py.
Explain the current application in plain English. Do not edit it yet.
Keep Python, Streamlit, Plotly, and the supplied data pipeline.
Use free dependencies and no paid APIs.
Never invent observations, fill suppressed wages with zero, or call a
screening score a validated investment recommendation.
For each future request, implement only that request, run the relevant
tests, and report changed files, the exact command to run, and the
expected visible result. Preserve the working baseline.
```

After each successful feature, use GitHub Desktop to commit it with a specific message and push it. If a change breaks the app, ask the assistant to compare it to the last working commit and fix the cause.

## 8. Reproduce the Census data download and map join

The starter bundles processed data so you can begin immediately. Now reproduce the source pipeline rather than trusting it blindly.

These are the exact tested official downloads:

- Population CSV: https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/counties/totals/co-est2024-alldata.csv
- County representative points ZIP: https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip
- County boundaries ZIP: https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_20m.zip

Run:

```powershell
.\.venv\Scripts\python.exe prepare_data.py
```

This command downloads those files plus BLS and EIA data, stores raw files locally, and rebuilds the processed files. If a source fails, your bundled processed baseline still exists; do not delete it to force progress.

Specific fields: county population comes from POPESTIMATE2024 after keeping SUMLEV=50. County FIPS is two-digit STATE plus three-digit COUNTY. Gazetteer GEOID supplies the matching five-digit key, and INTPTLAT/INTPTLONG supply representative coordinates.

The script uses national population points for the reach calculation, even though only five states are candidate locations. Thus surrounding U.S. population is not dropped at the candidate-state boundary.

Expected result: READY: 262 counties; 121 complete labor records; all map joins matched.

Optional later ACS route: request a free Census API key from https://api.census.gov/data/key_signup.html. The no-key ACS request returned a Missing Key HTML page during this test. Do not add that dependency until you need additional demographics.

## 9. Inspect and improve the labor data carefully

Tested source: https://data.bls.gov/cew/data/api/2024/a/industry/493.csv

This is 2024 annual warehousing and storage, NAICS 493. In prepare_data.py the intended selection is own_code=5 (private ownership), agglvl_code=75 (county, three-digit industry), and size_code=0. Join real county IDs to Census rather than assuming every five-character BLS area is a county. Unknown/unallocated county records ending in 999 were found in the download.

Open data/counties.csv in the VS Code editor, or view it through the application. Check Lehigh County, FIPS 42077: the bundled snapshot has 10,091 jobs and average annual pay of $60,053. This is an industry average, not a job-offer salary.

Paste this coding task:

```text
Add a Data coverage panel showing available, suppressed, and unpublished
labor records by state. Keep NAICS 493 and private ownership consistent.
Do not replace missing or suppressed wages/employment with zero or a
different industry. Make incomplete counties searchable and visible.
Show source period and labor_status. Run tests and report counts.
```

Expected result: users can see why some counties are not ranked. A larger future labor geography is possible, but it must be explicitly labeled and tested rather than silently filling county gaps.

## 10. Inspect the energy data and add an expense scenario

Tested source: https://www.eia.gov/electricity/sales_revenue_price/xls/table_4.xlsx

Open the workbook if you want to inspect it. Its tested title is 2024 Total Electric Industry - Average Retail Price (cents/kWh). It contains Residential, Commercial, Industrial, Transportation, and Total columns. The starter explicitly uses Commercial.

This annual file is a no-key baseline. The monthly EIA API can be an upgrade after registering at https://www.eia.gov/opendata/register.php. The annual file's URL can be reused for newer years, so the script stops if its title is no longer 2024. A downloaded file is not automatically the same data vintage forever.

Paste:

```text
Add an annual electricity consumption input in kWh and an illustrative
annual electricity expense for each selected county. Calculate
annual_kWh * electricity_cents_kwh / 100. Label the rate as a 2024
state commercial average, not a building tariff. Keep the ranking
method unchanged. Add a test: 1,000 kWh at 10 cents/kWh is $100.
```

Expected result: entering 1,000,000 kWh for a PA county yields about $110,303 using the bundled benchmark, not $11 million. The cents-to-dollars conversion is essential.

## 11. Confirm scoring and add sensitivity analysis

Open core.py. The default weights are 40/30/20/10 for general merchandise and 30/25/15/30 for temperature-controlled. Their order is market reach, lower labor benchmark, workforce depth, and lower electricity benchmark. These are illustrative assumptions that the user can change.

The app already standardizes against complete five-state candidates before applying a state filter. A filter must not recalculate the reference distribution. Percentile rankings are a simple screening method; they do not express the dollar size of differences between locations.

Paste:

```text
Add a sensitivity table for the top five eligible counties. Vary one
selected weight by minus 10 and plus 10 percentage points, respecting
0-100 and proportionally redistributing the remaining weight. Handle
the edge case where remaining weights sum to zero. Reuse the fixed
five-state normalization. Show which counties remain in the top three.
Never force a change of winner. Add tests for boundaries and repeatability.
```

Expected result: changes can be traced to weights; stable results remain stable. Do not market a county as best because a sample preset happened to place it first.

## 12. Improve the visual design after the numbers work

Take a screenshot of the current page. Give it to the coding assistant with this task:

```text
Improve this Streamlit app's presentation while preserving the scoring
and data pipeline. Use a map-dominant layout, restrained colors, readable
labels, and a compact comparison panel. Use gray for incomplete or
out-of-scope counties and explain the distinction on selection.
Keep a county dropdown so all locations are accessible. Add click-to-
select if supported by the installed Plotly/Streamlit version, without
removing the dropdown. Add metric-specific map layers and show raw
units in tooltips. Do not add dummy KPIs, animated trucks, fake weather,
commercial map tokens, or claims that the AI was tested if it was not.
Check desktop and narrow-screen layouts and run the existing tests.
```

Expected result: clearer map and comparison. Verify the map yourself in Chrome at normal width and narrow width. A screenshot does not verify clicking, so select a county and check that the panel changes.

## 13. Test live NWS data and expand weather coverage deliberately

The starter's Check NWS alerts button already works. Pick a county and click it. A successful zero-alert response is legitimate. Network failure is separately labeled Weather unavailable.

Public endpoints you can inspect:

- State alerts: https://api.weather.gov/alerts/active?area=PA
- Tested point: https://api.weather.gov/alerts/active?point=40.6140,-75.5900
- Forecast discovery for that point: https://api.weather.gov/points/40.6140,-75.5900

Forecast discovery returns URLs in properties.forecast and properties.forecastHourly. Follow those returned URLs rather than inventing grid identifiers.

Paste:

```text
Extend weather.py to fetch forecast discovery for the selected coordinate
and then follow properties.forecast. Validate each response, use a User-
Agent, a timeout, and 15-minute caching. Show issue/update times and
last successful fetch. Keep live weather separate from the investment
score. A point forecast is not county-wide weather coverage.
Add success, zero-alert, timeout, and malformed-response tests using
fixtures; do not make the test suite depend on today's weather.
```

Later map overlay: use NWS geometry where supplied. Some alerts identify affected zones without a polygon; resolve those using documented affected-zone geometry or show an alert list. Never silently discard them or fabricate an outline.

Expected result: live conditions display alongside an unchanged location score.

## 14. Add FEMA as a reviewed optional layer

Start at https://www.fema.gov/flood-maps/products-tools/national-risk-index or the official catalog record https://catalog.data.gov/dataset/national-risk-index-nri-data. Follow the current official download link for COUNTY data and obtain its data dictionary.

This is intentionally a separate checkpoint. The legacy download URL returned 502 during testing, and an assumed OpenFEMA endpoint did not exist. Do not depend on either address in the app.

If you obtain a valid county CSV:

1. Save it locally as data/raw/fema_counties.csv.
2. Give the CSV and its dictionary to your coding assistant.
3. Ask it to identify the actual county FIPS column from the schema, preserve leading zeros, document version/date, convert only documented missing-value codes, and join it to your 262 counties.
4. Add flood, winter-weather, and hurricane context as separate layers; label precisely whether each field is frequency, expected loss, or a community risk rating.
5. Keep those measures outside the core score until their business interpretation is justified.

Prompt:

```text
Inspect the uploaded FEMA county CSV and official data dictionary before
choosing fields. Add optional hazard context to the existing map and
county comparison, with a source version and clear units. Do not treat
overall community risk as a warehouse's probability of damage. If the
file is absent, show Hazard layer not configured and retain the working
business map and rankings. Report join coverage and unmatched IDs.
```

If the current official download is still unavailable, leave the layer visibly unconfigured and continue. That preserves a useful product instead of returning an empty application. This is not a verified live integration in the starter.

## 15. Add the AI layer with a real account-level test

1. Open https://aistudio.google.com/ and sign in with Google.
2. Open its API Keys area: https://aistudio.google.com/apikey.
3. Create/select a project and create a Gemini API key according to the current prompts.
4. Confirm the project is in the Free Tier and do not enable paid billing for this project.
5. Check https://ai.google.dev/gemini-api/docs/pricing and your account's available model list. Choose a currently available text model that explicitly has a free tier. Copy the actual model ID; do not assume every model shown is free.
6. In VS Code create .streamlit/secrets.toml, which is already ignored by Git. Put your values there:

```toml
GEMINI_API_KEY = "paste-your-key-locally"
GEMINI_MODEL = "paste-the-verified-free-model-id"
```

7. Never paste the real key into GitHub, a public screenshot, or a coding prompt.
8. First ask the coding assistant to create a tiny check_ai.py script using the current official Google Gen AI SDK or documented REST API. It should read the secret, send one short request, print the model ID and returned text, and redact keys on errors.
9. Run that script before connecting the app. No authenticated Gemini call was performed in this test because no user API key was available.

Once the account check works, paste:

```text
Add an optional Gemini-backed AI layer to Where Next. Read the key and
model ID from Streamlit secrets. Keep the deterministic app fully usable
without a key. Start with a button that explains the selected three
counties using only the supplied calculated evidence. Limit output to
250 words, include the data period, and do not invent numbers, rents,
freight prices, hazards, sources, or guaranteed delivery times.
Use a timeout, a clear 429/quota-exhausted message, and a deterministic
fallback. Make no model call on ordinary map redraw or slider movement.
Cache repeated identical requests. Never log or expose credentials.
Show AI-generated and code-generated explanations distinctly.
```

After explanations work, request natural-language control:

```text
Add a Describe your requirement box. Have the model return only a
validated object with supported state codes and four weights. Show the
interpreted assumptions to the user before applying them. Reject unknown
states, negative/nonfinite weights, and unsupported fields; never execute
model-generated Python. Call the existing scoring function with those
validated inputs. Requests for actual rent, same-day delivery, or an
uncovered state must explain the missing capability instead of fabricating
an answer. Test the parser with fixed fixtures independent of the live API.
```

Expected result: a real request can guide the existing tools and produce a grounded explanation. If the account has no free quota or requires paid billing, leave AI disabled and retain the data tool until a free option is available. Do not claim the AI stage is tested merely because its code imports.

## 16. Review, test, commit, and deploy

Ask for a focused review in a fresh coding-assistant conversation with the current files:

```text
Review this exact repository before a public demo. Prioritize incorrect
FIPS joins, suppressed BLS values, EIA cents-to-dollars conversion,
normalization before filtering, stale weather presented as live, invented
AI numbers, secret leakage, and startup dependencies on optional APIs.
Do not redesign the app. Report concrete issues, fix them, run relevant
tests, and identify checks you could not execute. Preserve sample data.
```

Then run locally:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Perform five manual checks: initial map, scenario change, one incomplete county, a live weather request, and an AI request with/without a configured key. Test zero selected states and all-zero weights too. Verify the app responds with an explanation rather than crashing.

In GitHub Desktop: inspect changes; commit with a meaningful summary; Push origin. Confirm .streamlit/secrets.toml and .venv are absent from the remote repository. Confirm new dependencies were added to requirements.txt and the processed data files are included.

Deploy:

1. Open https://share.streamlit.io/ and sign in using GitHub.
2. Authorize access to the intended repository.
3. Click Create app and choose the existing GitHub repository option.
4. Repository: YOUR-USERNAME/where-next. Branch: main. Main file: app.py.
5. In Advanced settings select the same supported Python version you used locally, if selectable.
6. Paste secrets into the platform's secrets box only if the optional AI layer is configured. Do not put them in the repository.
7. Choose an available app URL and click Deploy.
8. Open the resulting URL in an incognito/private browser window. Check the map, one scenario change, and the source panel.

GitHub Pages is not the host for this Python app. Streamlit runs its server. Free hosted apps may sleep, and quotas/performance are not a production availability guarantee.

If deployment fails, open Manage app/logs and copy the first actual traceback to the coding assistant. Most actionable checks are wrong app.py path, omitted data files, a missing dependency, incompatible Python/package versions, or a missing optional secret incorrectly treated as required.

## 17. Record the demo and publish a defensible project story

1. Create a worked example: a company comparing a general-merchandise site with a temperature-controlled site.
2. Open your published app and allow it to load fully before recording.
3. Use your computer's existing screen recorder. Record 60-90 seconds: select scenario, inspect three counties, change a priority, show the resulting comparison, then show weather separately.
4. Use an actual result. In the tested baseline the leader stayed Lackawanna while the shortlist changed; that is a legitimate sensitivity finding.
5. Put the project URL and GitHub URL in your LinkedIn post or project entry.
6. Explain your contribution: choice of decision criteria, missing-data rules, scoring logic, scenario design, and operational interpretation. Acknowledge coding assistance if describing how it was built.
7. State what is live (weather, and AI if configured) and what is a dated snapshot (the 2024 indicators).
8. Call it a public-data screening prototype. Do not claim actual savings, a fully optimized network, or validated property recommendations.

Before posting, ask two or three trusted operations professionals to try the app themselves. Ask where they got stuck and which missing input would change their decision. Use that feedback to prioritize customer-location upload, real site quotes, road travel times, and relevant transport infrastructure.

## Quick troubleshooting

| Symptom | What to do |
|---|---|
| py is not recognized | Reopen VS Code; verify Python installation. Try python --version and use python only to create the environment if it works. |
| requirements.txt not found | Open the actual repository folder; app.py and requirements.txt must be next to each other. |
| App says a data file is missing | Restore the bundled data folder or run prepare_data.py successfully. Do not replace it with random sample numbers. |
| Census returns HTML | Use the tested bulk file or add a valid Census key for the optional API path. Validate content, not only HTTP status. |
| 141 counties are incomplete | Expected for the frozen baseline: suppressed/unpublished labor inputs are excluded from scoring. |
| No weather alerts | Check whether the request succeeded. An empty successful FeatureCollection is a valid result. |
| Weather unavailable | Keep rankings working; retry later. Do not relabel it as zero risk. |
| EIA year check fails | The publisher changed the file. Review/rebuild a consistent new baseline and update source dates/tests; retain the old snapshot until ready. |
| Map blank | Check the browser error and map figure; no paid map token is required by this starter. Test a bundled-geometry fallback. |
| Gemini 429 or unavailable | Stop additional model calls, show a code-generated summary, and wait for free quota. Do not silently activate billing. |
| Hosted app fails, local works | Check remote data files, requirements.txt, Python version, and platform secrets. |

## Official documentation

- GitHub repositories: https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository
- GitHub Desktop: https://docs.github.com/en/desktop
- Streamlit installation: https://docs.streamlit.io/get-started/installation
- Streamlit deployment: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- Streamlit secrets: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- Codex IDE: https://developers.openai.com/codex/ide/
- Codex pricing/access: https://developers.openai.com/codex/pricing/
- Gemini API keys: https://ai.google.dev/gemini-api/docs/api-key
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- BLS QCEW: https://www.bls.gov/cew/additional-resources/open-data/home.htm
- NWS API: https://www.weather.gov/documentation/services-web-api
- Census county boundaries: https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html
- EIA electricity tables: https://www.eia.gov/electricity/sales_revenue_price/

UI labels and service quotas can change. Follow these official pages if a button label differs, and verify the result at each checkpoint rather than assuming a successful click means the integration works.
