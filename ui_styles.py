"""Reusable application theme tokens and styles scoped to stable Streamlit keys."""
from design_system import THEMES


def application_styles(landing=False, theme='dark'):
    tokens = THEMES[theme]
    variables = ';'.join(f'--wn-{key}:{value}' for key, value in tokens.items())
    clearance = '' if landing else WORKSPACE_CLEARANCE
    return '<style>:root{' + variables + ';--wn-radius:12px;color-scheme:' + theme + ';}' + CSS + clearance + '</style>'


CSS = r"""
[data-testid="stExpander"] summary:hover {background:var(--wn-hover)!important;}
[data-testid="stExpanderDetails"] {background:var(--wn-surface)!important;color:var(--wn-text)!important;}
[role="tab"], [role="tab"] p {color:var(--wn-text)!important;}

.wn-brand,.wn-preview,.wn-table {color:var(--wn-text);font-family:Arial,sans-serif;}
[data-testid="stCaptionContainer"] p,[data-testid="stCaption"] p {color:var(--wn-muted)!important;}
[data-testid="stSidebar"] a {color:var(--wn-accent)!important;}
[data-testid="stSidebar"] [data-testid="stHeading"] h1,
[data-testid="stSidebar"] [data-testid="stHeading"] h2,
[data-testid="stSidebar"] [data-testid="stHeading"] h3 {color:var(--wn-text)!important;}
.react-aria-ComboBox [role="group"] {background:var(--wn-raised)!important;color:var(--wn-text)!important;border-color:var(--wn-border)!important;}
.react-aria-ComboBox input {background:transparent!important;color:var(--wn-text)!important;}
[data-tag],[data-tag] span {background:var(--wn-hover)!important;color:var(--wn-text)!important;}
[data-testid="stSidebar"] [data-testid="stIconMaterial"],
[data-testid="stExpandSidebarButton"] svg {color:var(--wn-text)!important;}

[data-testid="stAppDeployButton"] {display:none;}
button[kind="primary"] [data-testid="stMarkdownContainer"] p,.st-key-default_weights button p {color:var(--wn-bg)!important;}
.wn-location-mark {display:block;width:25px;height:25px;background:var(--wn-accent);border-radius:50% 50% 50% 0;transform:rotate(-45deg);margin:0 5px 8px;flex-shrink:0;}
.wn-location-mark:after {content:'';position:absolute;width:11px;height:11px;top:7px;left:7px;background:var(--wn-sidebar);border-radius:50%;}
.wn-geospatial {position:relative;height:200px;margin:14px -8px;color:var(--wn-accent);overflow:hidden;
 background:repeating-radial-gradient(ellipse at 20% 110%,transparent 0 21px,color-mix(in srgb,var(--wn-accent) 14%,transparent) 22px 23px,transparent 24px 38px);}
.wn-region {position:absolute;display:block;background:var(--wn-accent);border:1px solid var(--wn-highlight);opacity:.3;}
.wn-region-one {width:120px;height:95px;left:20%;top:25%;clip-path:polygon(10% 0,80% 8%,100% 60%,65% 100%,0 75%);}
.wn-region-two {width:135px;height:105px;left:42%;top:35%;clip-path:polygon(15% 0,90% 18%,100% 78%,50% 100%,0 80%);opacity:.65;}
.wn-region-three {width:120px;height:90px;left:67%;top:20%;clip-path:polygon(15% 0,90% 18%,100% 78%,50% 100%,0 80%);}
.wn-map-pin {position:absolute;left:53%;top:62%;height:12px;width:12px;background:var(--wn-text);border:5px solid var(--wn-accent);border-radius:50%;box-shadow:0 0 0 10px color-mix(in srgb,var(--wn-accent) 18%,transparent);}

.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"], [data-testid="stHeader"] {
 background:var(--wn-bg);color:var(--wn-text);}
.stApp {font-family:Arial, sans-serif;font-size:14px;}
[data-testid="stMainBlockContainer"] {padding:1.6rem 1.3rem 3rem;max-width:1800px;}
h1 {font-size:clamp(24px,2.3vw,32px)!important;line-height:1.2!important;letter-spacing:-.035em;}
h2 {font-size:24px!important;} h3 {font-size:18px!important;letter-spacing:-.025em;}
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"],label,
[data-testid="stMarkdownContainer"] p,[data-testid="stHeading"] {color:var(--wn-text);}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p {color:var(--wn-muted);font-size:12px;}
a {color:var(--wn-accent);} a:hover {color:var(--wn-text);}
[data-testid="stSidebar"] {background:var(--wn-sidebar);border-right:1px solid var(--wn-border);}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {background:var(--wn-sidebar);}
[data-testid="stSidebar"] h3 {border-top:1px solid var(--wn-border);padding-top:12px;}
[data-testid="stSidebar"] button[data-testid^="stBaseButton"] {width:100%;text-align:left;}
[data-testid="stSidebar"] a {display:block;padding:9px 12px;text-decoration:none;border-radius:8px;font-size:14px;}
[data-testid="stSidebar"] a:hover {background:var(--wn-hover);}
.wn-brand {display:flex;align-items:center;gap:12px;padding:8px 0 20px;}
.wn-brand svg {width:30px;height:36px;color:var(--wn-accent);flex-shrink:0;}
.wn-brand strong {font-size:23px;letter-spacing:-.04em;display:block;}
.wn-brand small {font-size:12px;color:var(--wn-muted);}
.st-key-screening_map,.st-key-top_five,.st-key-comparison_panel,.st-key-latest_answer,
.st-key-alerts_panel,.st-key-forecast_panel,.st-key-sensitivity_panel,
.st-key-weights_overview,.st-key-scenario_overview,.st-key-insights_overview,.st-key-landing_panel {
 border:1px solid var(--wn-border);border-radius:var(--wn-radius);padding:18px;
 background:linear-gradient(140deg,var(--wn-raised),var(--wn-surface));box-shadow:var(--wn-shadow);min-width:0;}
@supports(backdrop-filter:blur(8px)) {
 .st-key-latest_answer,.st-key-landing_panel {backdrop-filter:blur(8px);}}
.st-key-latest_answer {border-color:var(--wn-accent);}
[data-testid="stExpander"] details {border:1px solid var(--wn-border);border-radius:10px;background:var(--wn-surface);}
[data-testid="stExpander"] summary {background:var(--wn-surface)!important;color:var(--wn-text)!important;}
button,[data-baseweb="select"]>div,[data-baseweb="input"],[data-baseweb="textarea"],
[data-testid="stChatInput"] {background:var(--wn-raised)!important;color:var(--wn-text)!important;border-color:var(--wn-border)!important;}
button p,button svg {color:inherit!important;}
button:hover {border-color:var(--wn-accent)!important;background:var(--wn-hover)!important;}
button[kind="primary"],.st-key-default_weights button {background:var(--wn-accent)!important;color:var(--wn-bg)!important;border-color:var(--wn-accent)!important;font-weight:600;}
input,textarea,[data-baseweb="select"] span {color:var(--wn-text)!important;caret-color:var(--wn-accent);}
input,textarea {background:var(--wn-raised)!important;}
input::placeholder,textarea::placeholder {color:var(--wn-muted)!important;opacity:1;}
[data-baseweb="tag"] {background:var(--wn-hover)!important;color:var(--wn-text)!important;}
[data-baseweb="popover"],[data-baseweb="popover"] ul,[role="listbox"],[role="option"],
[data-testid="stTooltipContent"],[data-testid="stDialog"] [role="dialog"] {
 background:var(--wn-raised)!important;color:var(--wn-text)!important;border-color:var(--wn-border)!important;}
[role="option"]:hover {background:var(--wn-hover)!important;}
[data-testid="stAlert"] {background:var(--wn-raised);color:var(--wn-text);border:1px solid var(--wn-border);}
[data-testid="stDataFrame"] {border:1px solid var(--wn-border);border-radius:10px;overflow:auto;}
:where(button,a,input,textarea,[tabindex]):focus-visible {outline:2px solid var(--wn-accent)!important;outline-offset:3px;}
.st-key-theme_toggle {position:fixed;top:12px;right:62px;z-index:999999;width:34px!important;}
.st-key-theme_toggle button {width:34px!important;height:34px!important;min-height:34px;padding:4px!important;border-radius:10px;}
.st-key-theme_toggle button p {position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap;}
.st-key-workspace_header {padding-right:45px;}
.st-key-view_mode {margin-bottom:4px;}


.wn-kpi-grid {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;}
.wn-summary-card {height:210px;padding:20px;box-sizing:border-box;min-width:0;display:flex;flex-direction:column;
 border:1px solid var(--wn-border);border-radius:var(--wn-radius);background:linear-gradient(140deg,var(--wn-raised),var(--wn-surface));
 box-shadow:var(--wn-shadow);transition:background .2s,border-color .2s,transform .2s;}
.wn-summary-card:last-child:nth-child(5) {grid-column:1 / -1;height:auto;min-height:90px;display:grid;grid-template-columns:1fr 1fr 1.4fr;gap:16px;align-items:center;}
.wn-summary-card:hover,.wn-preview:hover {border-color:var(--wn-accent);background:var(--wn-hover);transform:translateY(-2px);}
.wn-summary-label {color:var(--wn-muted);font-size:13px;line-height:1.4;}
.wn-summary-label:before {content:'';display:block;width:28px;height:5px;border-radius:8px;background:var(--wn-accent);margin-bottom:18px;}
.wn-summary-value {font-size:clamp(20px,2vw,30px);font-weight:650;letter-spacing:-.035em;line-height:1.2;margin:12px 0;overflow-wrap:anywhere;}
.wn-summary-secondary {font-size:12px;color:var(--wn-muted);line-height:1.5;margin-top:auto;}
.wn-table-scroll {overflow-x:auto;width:100%;border:1px solid var(--wn-border);border-radius:10px;}
.wn-table {border-collapse:collapse;width:100%;min-width:530px;font-size:12px;}
.wn-table th,.wn-table td {padding:13px 10px;border-bottom:1px solid var(--wn-border);text-align:left;white-space:nowrap;}
.wn-table thead {color:var(--wn-muted);background:var(--wn-raised);font-weight:400;}
.wn-table tbody th {font-weight:600;}.wn-table tbody tr:hover,.wn-table tr[aria-current] {background:var(--wn-hover);}
.wn-score {background:var(--wn-hover);color:var(--wn-accent);padding:5px 12px;border-radius:30px;font-weight:700;font-variant-numeric:tabular-nums;}
.wn-badge {display:inline-block;border:1px solid var(--wn-border);border-radius:30px;padding:4px 8px;font-size:11px;color:var(--wn-muted);}
.st-key-ranking_evidence {margin-top:8px;}.st-key-ranking_evidence p {font-size:12px;}
.wn-eyebrow {font-size:10px;letter-spacing:.15em;color:var(--wn-accent);font-weight:700;}
.st-key-landing_experience {max-width:1280px;margin:45px auto;}
.st-key-landing_hero h1 {font-size:clamp(28px,3.6vw,48px)!important;max-width:560px;}
.st-key-landing_panel {margin:20px 0 14px;}
.st-key-landing_question textarea {border-radius:10px;padding:14px;font-size:15px;}
.st-key-suggested_question button {border-radius:30px;white-space:normal;text-align:left;height:auto;transition:background .18s;}
.wn-preview-grid {display:grid;grid-template-columns:1fr 1fr;gap:14px;padding-top:12px;}
.wn-preview {padding:22px;border:1px solid var(--wn-border);border-radius:14px;background:linear-gradient(140deg,var(--wn-raised),var(--wn-surface));transition:background .2s,border-color .2s,transform .2s;}
.wn-preview-map,.wn-preview-wide {grid-column:1/-1;}.wn-preview svg {color:var(--wn-accent);width:100%;height:auto;}
.wn-preview h3 {margin:14px 0 8px;font-size:18px!important;color:var(--wn-text);}
.wn-preview p {font-size:13px;line-height:1.6;color:var(--wn-muted);}
.st-key-landing_hero,.wn-preview-grid {animation:wn-appear .45s ease-out both;}
@keyframes wn-appear {from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@media(max-width:1100px) {
 .wn-kpi-grid {grid-template-columns:repeat(2,minmax(0,1fr));}
 .st-key-map_rankings>[data-testid="stHorizontalBlock"],.st-key-analysis_overview>[data-testid="stHorizontalBlock"],
 .st-key-landing_experience>[data-testid="stHorizontalBlock"] {flex-direction:column;}
 .st-key-map_rankings>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"],
 .st-key-analysis_overview>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"],
 .st-key-landing_experience>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"] {width:100%;flex:1 1 100%;}}
@media(max-width:650px) {
 [data-testid="stMainBlockContainer"] {padding:1rem .8rem 2rem;}
 .wn-kpi-grid {grid-template-columns:minmax(0,1fr);}
 .wn-summary-card:last-child:nth-child(5) {display:flex;min-height:160px;}
 .wn-summary-card {height:auto;min-height:160px;}
 .st-key-screening_map,.st-key-top_five,.st-key-comparison_panel,.st-key-latest_answer {padding:12px;}
 .st-key-landing_experience {margin:22px auto;}.wn-preview-grid {grid-template-columns:1fr;}
 .st-key-theme_toggle {right:58px;}}
@media(prefers-reduced-motion:reduce) {*,*::before,*::after {animation:none!important;transition:none!important;scroll-behavior:auto!important;}}
"""


# Native header is fixed at 60px. Keep the compact navigation below it without
# changing landing-page spacing or the existing responsive row behavior.
WORKSPACE_CLEARANCE = r"""
[data-testid="stMainBlockContainer"] {padding-top:3.5rem;}
.st-key-workspace_navigation {scroll-margin-top:4.5rem;}
"""


# Keep action navigation uniform without stretching native combobox/chip buttons.
CSS += r"""
[data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:has(> .st-key-sidebar_navigation) {position:sticky;top:0;z-index:20;background:var(--wn-sidebar);}
.st-key-sidebar_navigation {background:var(--wn-sidebar);padding-bottom:8px;}
.st-key-primary_navigation button {height:40px;min-height:40px;max-height:40px;padding:8px 12px;border-radius:10px;font-size:14px;justify-content:flex-start;}
.st-key-primary_navigation button p {font-size:14px;line-height:20px;}
.st-key-candidate_states [data-tag] {flex:0 0 auto;min-width:42px;border-radius:8px;}
.st-key-candidate_states [data-tag] button {width:auto;flex:0 0 auto;}
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {color:var(--wn-text)!important;}
[data-testid="stText"], [data-testid="stText"] pre {color:var(--wn-text)!important;}
"""
