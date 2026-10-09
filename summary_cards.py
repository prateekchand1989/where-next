"""Scoped, escaped presentation markup for responsive county summary cards."""
from html import escape


def render_summary_card(label, value, secondary=None):
    return (f'<article class="wn-summary-card"><div class="wn-summary-label">{escape(str(label))}</div>'
            f'<div class="wn-summary-value">{escape(str(value))}</div>'
            f'<div class="wn-summary-secondary">{escape(str(secondary or ""))}</div></article>')


def summary_cards_html(cards, theme="dark"):
    from ui_styles import application_styles
    return application_styles(theme=theme) + '<div class="wn-summary-grid wn-kpi-grid">' + ''.join(render_summary_card(*card) for card in cards) + '</div>'
