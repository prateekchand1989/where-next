"""Green glass styling scoped to application keys and native Streamlit test IDs."""


def application_styles(landing=False):
    common = '''<style>
.st-key-screening_map,.st-key-top_five,.st-key-comparison_panel,.st-key-latest_answer,
.st-key-alerts_panel,.st-key-forecast_panel,.st-key-sensitivity_panel {
 border:1px solid rgba(84,132,110,.20);border-radius:20px;padding:20px;
 background:#f8fcf9;box-shadow:0 4px 10px rgba(16,61,53,.025),0 12px 32px rgba(16,61,53,.055);min-width:0;}
@supports ((backdrop-filter:blur(8px)) or (-webkit-backdrop-filter:blur(8px))) {
 .st-key-screening_map,.st-key-top_five,.st-key-comparison_panel,.st-key-latest_answer,
 .st-key-alerts_panel,.st-key-forecast_panel,.st-key-sensitivity_panel {
 background:rgba(255,255,255,.78);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);}}
.st-key-top_five h3,.st-key-screening_map h3 {color:#103d35;}
.st-key-latest_answer {border-color:rgba(20,125,105,.32);}
.st-key-overall_summary_panel details,.st-key-electricity_panel details,.st-key-methodology_panel details,
.st-key-fema_panel details,.st-key-weather_panel details,.st-key-evidence_panel details,.st-key-history_answers details,
.st-key-operating_cost_panel details,.st-key-cost_sources details {
 border-color:rgba(84,132,110,.22);border-radius:18px;background:rgba(255,255,255,.72);}
[data-testid="stSidebar"] {border-right:1px solid rgba(84,132,110,.15);}
[data-testid="stSidebar"] h3 {border-top:1px solid rgba(84,132,110,.16);padding-top:14px;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color:#536c60;}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p {color:#536c60;}
.st-key-default_weights button {width:100%;background:#103d35;color:white;border-color:#103d35;border-radius:12px;}
.st-key-default_weights button:hover {background:#147d69;border-color:#147d69;color:white;}
.st-key-default_weights button:focus-visible {outline:3px solid #147d69;outline-offset:3px;}
.st-key-view_mode {margin-bottom:8px;}
@media(max-width:1100px) {
 .st-key-map_rankings [data-testid="stHorizontalBlock"] {flex-direction:column;}
 .st-key-map_rankings [data-testid="stColumn"] {width:100%;flex:1 1 100%;}}
@media(max-width:650px) {
 .st-key-screening_map,.st-key-top_five,.st-key-comparison_panel,.st-key-latest_answer,
 .st-key-alerts_panel,.st-key-forecast_panel,.st-key-sensitivity_panel {padding:16px;}}
</style>'''
    if not landing:
        return common
    return common + '''<style>
[data-testid="stAppViewContainer"]:has(.st-key-landing_experience) {
 background:radial-gradient(ellipse at 18% 18%,rgba(123,197,163,.20),transparent 42%),
 radial-gradient(ellipse at 85% 70%,rgba(97,199,170,.18),transparent 44%),linear-gradient(135deg,#103d35 0%,#125e4f 55%,#147d69 100%);}
.stApp:has(.st-key-landing_experience) [data-testid="stHeader"] {background:transparent;}
.stApp:has(.st-key-landing_experience) [data-testid="stHeader"] button {color:white;}
.st-key-landing_experience h1 {color:white;font-size:clamp(3rem,6vw,5rem);letter-spacing:-.045em;line-height:1.1;}
.st-key-landing_experience>.stElementContainer,.st-key-landing_experience [data-testid="stMarkdownContainer"] {color:#e4f3eb;}
.st-key-landing_panel {border:1px solid rgba(230,255,242,.28);border-radius:24px;padding:24px;
 background:rgba(240,255,247,.10);box-shadow:0 12px 48px rgba(4,33,25,.18);}
@supports ((backdrop-filter:blur(10px)) or (-webkit-backdrop-filter:blur(10px))) {
 .st-key-landing_panel {backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);}}
.st-key-landing_question textarea {background:rgba(250,255,252,.96);color:#20352f;border-radius:14px;padding:16px;font-size:1.05rem;}
.st-key-landing_question textarea::placeholder {color:#526c60;opacity:1;}
.st-key-ask_where_next button {background:#dcece5;color:#103d35;border-color:#dcece5;border-radius:14px;min-height:48px;font-weight:650;}
.st-key-ask_where_next button [data-testid="stMarkdownContainer"],.st-key-ask_where_next button p {color:#103d35;}
.st-key-ask_where_next button:hover {background:#f1f8f4;color:#103d35;border-color:#f1f8f4;}
.st-key-suggested_question button {border-radius:999px;background:rgba(255,255,255,.10);border:1px solid rgba(220,236,229,.32);color:#f1f8f4;white-space:normal;text-align:left;height:auto;transition:background .16s ease,border-color .16s ease;}
.st-key-suggested_question button:hover {background:rgba(255,255,255,.20);border-color:#dcece5;}
.st-key-suggested_question button[aria-pressed="true"] {background:#dcece5;color:#103d35;}
.st-key-suggested_question [data-testid="stWidgetLabel"] p {color:#e4f3eb;}
.st-key-ask_where_next button:focus-visible,.st-key-suggested_question button:focus-visible {outline:3px solid #dcece5;outline-offset:3px;}
@media(max-width:650px) {.st-key-landing_panel {padding:18px;border-radius:20px;}}
@media(prefers-reduced-motion:reduce) {.st-key-suggested_question button {transition:none;}}
</style>'''
