"""Scoped, escaped presentation markup for responsive county summary cards."""
from html import escape


def render_summary_card(label, value, secondary=None):
    return (f'<article class="wn-summary-card"><div class="wn-summary-label">{escape(str(label))}</div>'
            f'<div class="wn-summary-value">{escape(str(value))}</div>'
            f'<div class="wn-summary-secondary">{escape(str(secondary or ""))}</div></article>')


def summary_cards_html(cards):
    return '''<style>
.wn-summary-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr));gap:16px;width:100%;}
.wn-summary-grid .wn-summary-card {box-sizing:border-box;min-width:0;height:210px;padding:20px;
 display:flex;flex-direction:column;border:1px solid rgba(120,140,160,.20);border-radius:16px;
 background:#f8fcf9;box-shadow:0 4px 10px rgba(16,61,53,.025),0 12px 28px rgba(16,61,53,.06);color:#103d35;}
@supports ((backdrop-filter:blur(10px)) or (-webkit-backdrop-filter:blur(10px))) {
 .wn-summary-grid .wn-summary-card {background:rgba(255,255,255,.76);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);}}
.wn-summary-grid .wn-summary-card:first-child {border-color:rgba(20,125,105,.35);background:linear-gradient(135deg,rgba(220,236,229,.90),rgba(248,252,249,.90));}
.wn-summary-grid .wn-summary-label {font-size:.9rem;line-height:1.3;min-height:2.6em;color:#536c60;}
.wn-summary-grid .wn-summary-value {font-size:clamp(1.1rem,1.5vw,1.5rem);font-weight:650;line-height:1.25;
 margin-top:12px;overflow-wrap:anywhere;white-space:normal;text-overflow:clip;}
.wn-summary-grid .wn-summary-secondary {font-size:.78rem;line-height:1.3;margin-top:auto;min-height:2.6em;color:#536c60;}
@media(max-width:1100px) {.wn-summary-grid {grid-template-columns:repeat(2,minmax(0,1fr));}}
@media(max-width:650px) {.wn-summary-grid {grid-template-columns:minmax(0,1fr);}}
</style><div class="wn-summary-grid">''' + ''.join(render_summary_card(*card) for card in cards) + '</div>'
