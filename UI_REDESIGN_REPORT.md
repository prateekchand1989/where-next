# Where Next: main-only UI migration

## Branch and preservation

The redesign is in `design-from-main-clean`, at `P:\@@@Where Next Agent\Github\where-next-design-main`.
HEAD was created directly from main and remains `1d69619992e3e0d93731e4d4523ceae3e0a5cf01`. There are zero commits in `main..HEAD`; all redesign work is uncommitted. No development-only commits were brought across.

The original `Design_branch` worktree remains at `P:\@@@Where Next Agent\Github\where-next-design` with its original branch, index, status, and 147 files preserved. Development and its modified/untracked files were verified against the preservation snapshot. Main's branch pointer was not changed.

Verified complete backup: `P:\@@@Where Next Agent\Github\where-next-design-backup-20261008-5877bf94.zip`. It contains all 147 tracked, untracked, and ignored worktree files, SHA-256 manifests, the worktree index, staged/unstaged binary patches, and Git status/branch/worktree snapshots. ZIP integrity and every backed-up file hash were checked before migration and again afterward. The backup can include local/private content and should remain local.

## Selectively transferred design work

| File | Main-only adaptation |
| --- | --- |
| `app.py` | Surgical changes against main: landing, sidebar navigation, native theme button, responsive dashboard arrangement, themed plots/tables, searchable county pickers, four-factor weight visualization, original sensitivity display, and original validated AI insights. All 15 existing top-level functions retain identical ASTs. |
| `ui_styles.py` | Shared semantic theme tokens, forest-green surfaces, light surfaces, responsive cards, native widget styling, focus/reduced-motion handling. Development coverage styling removed. |
| `summary_cards.py` | Existing escaped metric rendering with shared theme styles; all five main summary metrics retained. |
| `.streamlit/config.toml` | Forest-green dark default and native widget baseline. |
| `design_system.py` | Theme, presentation and selection helpers adapted to main. Ranking table rent is main's existing cost-model benchmark, separate from scoring. |
| `cost_panel.py` | Only chart and dataframe presentation wrappers; original inputs, assumptions, estimates and lease provenance remain intact. |
| `.gitignore` | Ignore local `.browser_validation` artifacts. Existing inherited bytes otherwise retained. |
| `tests/test_design_system.py` | Five tests for main-only theme/navigation/selection/state/escaping behavior. |
| `tests/browser_design_preview.py` | Local mocked provider/weather fixture for browser verification, using main's evidence format. |
| `tests/browser_design_visual.py` | Dark/light screenshots and overflow/state checks at 1440, 1280, 1024, 768 and 390 px. |
| `tests/browser_design_workflow.py` | Main-only four-factor ranking/map/control, CSV, selection and mocked-answer/history checks. |

The layout adapts [Magic UI Bento Grid](https://magicui.design/docs/components/bento-grid) and [shadcn/ui dashboard/sidebar](https://ui.shadcn.com/blocks#dashboard-01) patterns using existing Streamlit/Python. No React conversion, extra UI dependency, or fabricated dashboard metrics were added.

## Excluded development work

No development versions of `core.py`, `analysis_intent.py`, `interpretation.py`, `question_state.py`, `operating_costs.py`, `question_targeting.py`, weather/FEMA/backend modules, datasets, README, requirements, or original tests were copied. All 42 protected main files retain their original checkout hashes.

Excluded: leasing ranking/fifth factor, a leasing-weight floor, development presets/rebalancing, ranking/data coverage changes, added county/lease data, development AI intent changes, leasing coverage/development reports, development test modifications, and leasing browser fixtures/regressions. Mixed `app.py` changes were integrated against main rather than replacing the file.

Main keeps four factors: market reach, lower labor benchmark, workforce depth, and lower electricity benchmark. Its original General merchandise and Temperature-controlled presets are unchanged. Existing cost assumptions, lease benchmark provenance, unavailable-data handling, map hover/highlight/FEMA interactions, comparison, sensitivity, weather, AI validation/history and CSV export remain.

## Verification

- Untouched main baseline: **206 passed in 745.51 seconds**.
- Focused design/polish verification: **26 passed in 77.08 seconds** after the final contrast adjustment.
- Complete final suite: **211 passed in 593.36 seconds**.
- Visual browser checks: **10 cases passed** (both themes at five widths), including keyboard theme activation, preserved state, no page overflow and no clipped metric cards. Functional browser verification: **7 cases passed**, covering both original presets at 1440/768/390 px, four-factor controls and resets, scores/map values compared with main, missing rent, synchronized county selection, original CSV schema/scores, two mocked AI answers, saved history, and theme/navigation without new calls. **No live model calls** were made.
- Integrity: 42 protected main files, 15 original application functions, 147 old design files, development HEAD/index/status/dirty files, main reference and backup hashes verified.
- `git diff --check`: passed.

Local screenshots and JSON results are in `.browser_validation/`, including original-main before images and dark/light redesign images.

## Remaining limits and opening the worktree

Native Streamlit dataframe canvas headers retain the configured dark style in light mode; cells and surrounding panels switch themes. Theme choice persists for the current Streamlit session; a fresh session defaults to dark. Browser AI tests use a mock provider, so they do not verify live provider credentials or model output. Styling targets stable Streamlit keys/test identifiers and should be rechecked after a Streamlit upgrade.

Open the clean folder in VS Code:

```powershell
code "P:\@@@Where Next Agent\Github\where-next-design-main"
```

Run from that folder using the existing environment:

```powershell
& "..\where-next\.venv\Scripts\python.exe" -m streamlit run app.py --server.port 8503 --server.address 127.0.0.1
```

The old Design_branch/worktree has not been renamed, replaced, reset or removed. No commits, pushes or merges were made.
