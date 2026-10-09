# Where Next — Interaction Improvements

## Scope and preservation

Implemented in `P:\@@@Where Next Agent\Github\where-next-design-main`, branch `design-from-main-clean`. HEAD and `main` remain `1d69619992e3e0d93731e4d4523ceae3e0a5cf01`, with zero commits in `main..HEAD`. No commits, pushes, merges, resets, stashes, or branch switches were performed.

Before editing, the current design work was archived and verified in `C:\Users\prate\AppData\Local\Temp\where-next-interactions-backup-cd1c92c4.zip`, including tracked/untracked source files, staged/unstaged patches, status, and a SHA-256 manifest. The original development working directory, index, dirty files, and HEAD remain unchanged. The old Design_branch's 147 preserved files, index, and status also remain unchanged.

The preservation audit verified 26 protected main backend/data files against their original hashes, including scoring, operating costs, intent parsing, targeting, weather/FEMA, evidence/provider code, and bundled datasets. The original four-factor rebalance math is unchanged. Existing design files, configuration, summary cards, and cost-panel presentation were retained. No development-only leasing ranking factor or data was introduced.

## Candidate States root cause and repair

The native Streamlit multiselect had correct supported options and session values. Browser measurements identified a broad sidebar `button {width:100%}` rule as the rendering defect: native Clear all/Open buttons expanded to approximately 257px, squeezing selection tags to approximately 16px and producing the blank-looking rectangle.

Sidebar action sizing now targets Streamlit action buttons only. The native combobox keeps its own dropdown/clear controls, and visible state chips have a compact minimum width. The exact main state set remains MD, NJ, NY, OH, PA. Chip removal, keyboard selection, multistate selection, and all-five selection work in both themes. Empty or invalid scopes are rejected with a warning and the previous valid scope restored.

`interaction_state.py` routes state, scenario, and normalized weight patches through main's existing atomic intent validator. Widgets and AI intent share authoritative Python session state. Main's existing comparison reconciliation, deterministic state restrictions, and county targeting remain in use. A revision/control snapshot prevents an older parsed intent from overwriting newer manual controls.

## Persistent navigation

Ask Where Next, Dashboard, and Start a new question now appear beneath the existing sidebar brand. Native buttons share full available width, 40px height, padding, radius, typography, and icon placement; the current view uses the existing green active treatment. The duplicate primary main-content navigation was removed. Analytical content uses a native keyed container per view, preventing faded dashboard fragments from being retained when the conversation and dashboard layouts are reconciled. The native question text also explicitly follows the current theme color for light-mode readability.

The sidebar navigation's native layout wrapper is sticky inside the sidebar scroll region. It stays reachable when either main content or sidebar filters scroll. Native sidebar collapse/reopen controls remain available; narrow screens use Streamlit's collapsible sidebar. Streamlit intentionally dismisses the mobile sidebar on an outside click, including a theme-toggle click. Browser tests reopen it through the native control before assessing sidebar navigation.

Switching Ask/Dashboard retains controls, selected counties, and conversation history without generating requests. Only Start a new question invokes the existing reset workflow; theme and session weather behavior are preserved.

## Reactive AI

Material state, scenario, comparison/map selection, sensitivity, annual-electricity evidence, or explicitly refreshed weather changes recalculate existing Python evidence and refresh the latest meaningful question. Operating-cost assumptions retain their existing independent model and remain outside main's AI evidence allowlist; changing them does not create requests. Refreshes skip intent parsing and use the unchanged main answer provider, model, schema, prompts, evidence allowlist, and grounding safeguards.

Newer manual state filters take precedence over the previous question's screening-state restriction. For example, second-best in NJ followed by PA selection becomes second-best in Pennsylvania; it does not reapply the old NJ intent. Named-county questions retain their existing targeting semantics.

Weight sliders retain immediate normalized ranking previews. A compact Apply changes button batches their AI refresh into one request after the user finishes adjusting weights. No timer or background worker was introduced. Existing overall-summary interpretations also refresh after material changes, using their unchanged four-section schema; an empty dashboard session does not invent a question or interpretation.

Request efficiency and safety:

- Question plus evidence fingerprint identifies the exact analytical context.
- Unchanged contexts do not generate requests on reruns, theme changes, view changes, or history toggles.
- Previously successful identical contexts can reuse their session history result.
- Pending, pending-apply, running, succeeded, and failed states are tracked.
- Monotonic request IDs, interaction revisions, and control signatures reject stale completions, including after a new-question reset.
- Failed requests retain the usable deterministic dashboard and earlier answers. A retry button is explicit; presentation changes do not start automatic retries.
- No provider credentials are copied, exposed, or altered by these changes. Browser and automated AI checks use mocks only.

## Answer history

The latest successful answer is expanded in the existing green answer panel. Superseded responses remain collapsed and labeled Historical. Each turn retains its original question, immutable evidence snapshot, fingerprint, scenario/scope, and result. Earlier overall summaries similarly remain in collapsed interpretation history. Old answers are not rewritten with current rankings or presented as current recommendations.

## Files changed in this task

| Files | Purpose |
| --- | --- |
| `app.py` | Sidebar navigation, validated event callbacks, reactive request orchestration, weight Apply action, retry/status, historical evidence presentation, overall-summary refresh. |
| `ui_styles.py` | Native multiselect sizing repair, uniform navigation, sticky sidebar wrapper, native question color. |
| `interaction_state.py` (new) | Validation/event helpers, manual scope precedence, request fingerprints/cache and stale-result guards. |
| `tests/test_interaction_improvements.py` (new) | Focused state, targeting, refresh, cache, history, failure/retry, concurrency, reset, and overall-summary regressions. |
| `tests/browser_interaction_improvements.py` (new) | Native mouse/keyboard checks in both themes at all requested widths; mocked failure/retry and exact main-score comparisons. |
| `tests/browser_design_preview.py` | Mock evidence logging and a one-shot mocked provider failure; isolated temporary mock secrets and optional independent mock ports/logs. |
| `tests/browser_design_visual.py`, `tests/browser_design_workflow.py` | Updated navigation selectors and optional isolated browser targets for existing visual and CSV/workflow checks. |
| `tests/browser_targeted_navigation_ai.py` | Compatibility entry point to the replacement sidebar/navigation interaction checks. |
| Existing tests: `test_analysis_workflow`, `test_default_weights`, `test_design_system`, `test_highlight`, `test_interpretation`, `test_operating_costs`, `test_question_flow`, `test_question_reset`, `test_reactive_ranking`, `test_targeted_ui_configuration`, `test_targeting` | Adapted navigation locators and intentionally changed refresh/history expectations; original formula, ranking, evidence, provenance, missing-data, weather, and export assertions retained. |

## Validation

- Full pre-change baseline: **218 passed** (402.25 seconds).
- Full post-change functional suite: **237 passed, 0 failed** (684.14 seconds). After the view-boundary fix, **32 targeted regressions passed**; the final stylesheet check also passed.
- Final interaction checks: **10 passed, 0 failed** — dark and light at 1440, 1280, 1024, 768, and 390px. Checks include native chips/keyboard, synchronized main scores, persistent navigation, batched weights, scenario refresh, history, failure/retry, no duplicate requests, question contrast, and no visible stale fragments. **0 live billable API calls**.
- Existing visual checks: **10 viewport/theme cases passed**. Existing workflow checks: **7 cases passed**, including six width/scenario combinations and actual CSV download, original score/schema comparison, county selection, mocked answers/history, and presentation changes without new calls.
- `git diff --check`: passed.
- Final preservation/ancestry audit: passed; `.browser_validation/interaction_integrity_report.json` contains the results.

Intermediate diagnostic runs exposed obsolete no-refresh expectations, normalized state ordering, test status/fingerprint assertions, and browser synchronization assumptions. These were corrected without changing analytical formulas. Screenshot review also exposed faded stale fragments after repeated view changes and unreadable native question text in light mode; the native view boundary and scoped text-color rule fixed both, and final browser assertions explicitly cover them. The first mobile navigation check assumed an outside theme click left the native mobile sidebar open; the corrected check uses the native reopen control.

Browser evidence lives in the ignored `.browser_validation` directory. The interaction report is `interaction_browser_report.json`. Screenshots include, for each dark/light theme and 1440/1280/1024/768/390px width:

- `interaction_sidebar_all_states_{theme}_{width}.png`
- `interaction_sidebar_manual_PA_{theme}_{width}.png`
- `interaction_persistent_navigation_{theme}_{width}.png`
- `interaction_latest_PA_cold_{theme}_{width}.png`

## Operational limits

AI validation used mocked responses; no live billable API calls were made. The existing synchronous Streamlit/Python provider architecture remains in place. Request guards prevent stale responses from becoming current but do not cancel an already sent provider request. Cache and history are session-scoped, consistent with the existing application; starting a new question clears the established transient conversation context. Weight changes require the explicit compact Apply action to refresh AI while rankings preview immediately.

Final status: no known unresolved issues within the automated and mocked browser coverage. All changes remain uncommitted in `design-from-main-clean`.
