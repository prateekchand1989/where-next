# Where Next — Two surgical corrections

Worktree: `P:\@@@Where Next Agent\Github\where-next-design-main`
Branch: `design-from-main-clean`
HEAD/main: `1d69619992e3e0d93731e4d4523ceae3e0a5cf01`. No development-only commits.

The navigation sidebar is rendered only when `experience_mode` is not `landing`. Landing content, styles, theme toggle, and workspace navigation are preserved. Browser checks confirm there is no native sidebar, reopening control, or reserved sidebar column on landing.

Manual analytical changes and Apply changes update the existing deterministic analysis without requesting AI. Existing submitted questions, follow-ups, Generate overall summary, and Retry actions remain explicit AI triggers. Legacy queued automatic requests are discarded. Request revision/control guards remain in place.

Saved answers retain their original history records, answers, fingerprints, and evidence (including states, scenario, and weights). Staleness uses the existing evidence comparison. A stale current answer remains in its existing keyed expander and is labeled as historical, so manually opened/collapsed panels keep their state. Older records stay in existing history panels. The AI insights panel does not display a stale recommendation as current. Saved overall interpretations also remain accessible with a historical-context notice; replacement occurs only after an explicit Generate/Retry action.

## Exact files changed by this task

Production:
- `app.py`: conditional landing/sidebar rendering; explicit-only generation gate; stale-answer notices and stable answer/summary panels.
- `interaction_state.py`: manual events and Apply no longer queue AI; explicit retry targeting; stale completion guards.

Affected tests:
- `tests/browser_interaction_improvements.py`
- `tests/test_analysis_workflow.py`
- `tests/test_default_weights.py`
- `tests/test_design_system.py`
- `tests/test_highlight.py`
- `tests/test_interaction_improvements.py`
- `tests/test_interpretation.py`
- `tests/test_operating_costs.py`
- `tests/test_question_flow.py`
- `tests/test_question_reset.py`
- `tests/test_reactive_ranking.py`
- `tests/test_targeted_ui_configuration.py`

Documentation: `SURGICAL_CORRECTIONS_REPORT.md` (this file).

## Verification

- Before edits: 39 relevant baseline tests passed (175.70 seconds).
- Focused interaction checks: 22 passed before adding two final coverage cases.
- Full suite: 241 passed, 1 newly added test failed (607.16 seconds). The failure was a test navigation mistake: it accessed the dashboard-only sensitivity selector while in Ask Where Next. Corrected the test to open Dashboard first; the targeted rerun passed (17.25 seconds), with no application changes. This verifies all 237 existing tests and all five added regressions across the full run and corrected targeted rerun. Logs: `.browser_validation/surgical_pytest_final.log` and `surgical_pytest_one-fixed.log`.
- Browser: four passed cases, 1440px and 390px, dark/light. Native controls, no automatic AI, immutable historical content, retained open/closed answer state, explicit follow-up evidence, and explicit failure/retry covered.
- Browser report: `.browser_validation/surgical_browser_report.json`; screenshots: `.browser_validation/surgical_*.png`.
- Zero live AI requests; all provider checks use mocks.

## Preservation and limitations

The 61-file pre-task backup, staged/unstaged patches, status and Git index were verified before edits. Backup: `C:\Users\prate\AppData\Local\Temp\where-next-surgical-backup-3e7db64a.zip`.

Audit verifies 26 protected main backend/data files and original weight rebalance math remain unchanged. Prompts, providers, structured validation, response formatting, styles, design tokens, operating-cost calculations, and datasets were not edited. Original development HEAD/index/status/dirty files and 147 files in the old Design worktree remain unchanged. No commits, pushes, merges, resets, or branch switches.

History continues using existing Streamlit session-state storage. This task does not add durable storage across browser/session resets. Real provider networking/billing was deliberately not exercised. No unresolved failures remain after the corrected targeted rerun.

## Local commit verification

Fresh full-suite verification before the authorized local commit: **242 passed in 626.34s (0:10:26)**. No live AI requests. The earlier corrected-test result above is retained as historical validation detail.
