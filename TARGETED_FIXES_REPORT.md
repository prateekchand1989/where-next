# Targeted navigation and AI configuration fixes

## Navigation root cause and minimal fix

The native Streamlit header is fixed and **60 px** high. Custom main-content padding placed the navigation at **41.6 px** on desktop, so the header covered the upper portion of every navigation control. Browser rectangle measurements and `elementFromPoint` hit tests reproduced the obstruction.

A workspace-only padding override now places navigation at **72 px**, leaving **12 px** below the existing header. A scroll margin keeps the navigation clear when scrolled into view. Landing-page spacing is unchanged. Existing controls, button shapes, typography, colors, borders, animations, and responsive wrapping are preserved; no new navigation system or taller header was introduced.

## AI configuration root cause and restoration

`interpretation.py` and the application configuration-loading code are identical to main. They read Streamlit secrets with environment-variable fallback; they do not load `.env` files. The clean worktree had neither local secrets nor an environment API key. The original project has the needed local `.streamlit/secrets.toml`.

The clean worktree's native `[secrets] files` setting now reads `../where-next/.streamlit/secrets.toml`, then `.streamlit/secrets.toml` if present. A worktree-local file takes precedence. This references the existing secure file rather than copying credentials. No keys or model values were logged or added to source control. The source secrets file was not modified.

A read-only check confirmed provider detection, matching existing credentials, and preservation of the existing model setting. No live API request was made, so external key validity, quota and provider availability have not been tested. Prompts, provider architecture, evidence schema, structured validation, rankings and all analytical calculations are unchanged.

**Restart Streamlit from the clean worktree** so it reloads the configuration. No new credentials are needed in the current folder arrangement. If folders are moved, update the reference path or use an ignored worktree-local secrets file or the existing environment-variable settings.

## Evidence-state warning

No false warning was reproduced immediately after submission, navigation or theme switching, with either configured or absent credentials. The regression tests confirm a real factor-weight change correctly marks the saved answer stale without another AI call. Existing tests cover scenario, county selection and weather changes. The warning was retained unchanged. The screenshot's precise earlier evidence state is unavailable, so its individual warning cannot be conclusively attributed to a particular change.

## Exact files changed by this task

- `ui_styles.py`: workspace-only header clearance and scroll margin.
- `.streamlit/config.toml`: native reference to existing secure local configuration.
- `tests/browser_design_preview.py`: native discovery of temporary mocked credentials instead of replacing the provider factory; all provider/weather responses remain mocked.
- `tests/test_targeted_ui_configuration.py` (new): configuration precedence, environment fallback, no-key analytical behavior, presentation-only state preservation and legitimate stale-answer warnings.
- `tests/browser_targeted_navigation_ai.py` (new): real browser geometry/hit testing, question submission, navigation, reset, theme, overflow, answer rendering and call-count checks at five widths in both themes.
- `TARGETED_FIXES_REPORT.md` (new): this report.

Every other pre-existing clean-worktree file matches the task-start hash snapshot. Main/development and the old design worktree remain untouched. The current branch remains `design-from-main-clean`, with HEAD equal to main `1d69619992e3e0d93731e4d4523ceae3e0a5cf01`. No development-only commits, commits, pushes, merges, resets or branch switches occurred.

## Validation

- Focused configuration/design tests: **12 passed in 35.56 seconds**.
- Complete suite: **218 passed in 436.88 seconds**; real credentials were isolated from tests.
- Browser checks: **10 cases passed** at 1440, 1280, 1024, 768 and 390 px in both themes. Each verifies label bounds, header clearance, button hit tests, native navigation/reset, theme accessibility, page overflow, configured mocked answer rendering and exactly one intent plus one answer request per submitted question. Navigation and theme changes add zero requests.
- Preservation/ancestry audit and `git diff --check`: passed.

Screenshots and machine-readable results are in `.browser_validation/`, including `fixed_navigation_ask_*`, `fixed_navigation_dashboard_*`, `fixed_ai_answer_*`, `targeted_navigation_ai_report.json` and `targeted_integrity_report.json`. All browser questions use temporary mocked credentials and responses; no live billable requests are made.

Run from `P:\@@@Where Next Agent\Github\where-next-design-main`:

```powershell
& "..\where-next\.venv\Scripts\python.exe" -m streamlit run app.py --server.port 8503 --server.address 127.0.0.1
```
