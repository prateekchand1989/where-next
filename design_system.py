"""Presentation-only theme and selection helpers; no scoring or AI behavior."""
from html import escape

THEMES = {
    'dark': dict(bg='#080F0D', surface='#101B17', raised='#14231D', sidebar='#061C15',
                 text='#F3F7F5', muted='#A0B3A9', accent='#24C77B', highlight='#5AE6A0',
                 border='#284137', hover='#183B2B', shadow='0 8px 28px #00000025', unavailable='#29342F'),
    'light': dict(bg='#F5F8F6', surface='#FFFFFF', raised='#F8FBF9', sidebar='#E9F2ED',
                  text='#172820', muted='#60746A', accent='#087A4C', highlight='#DDF4E6',
                  border='#D8E5DD', hover='#DDF4E6', shadow='0 8px 28px #173C2010', unavailable='#DFE5E1'),
}
PALETTE = ['#24C77B', '#087346', '#6FA88B', '#A4C7B4', '#7E9591']


def initialize_theme(state):
    state.setdefault('ui_theme', 'dark')


def toggle_theme(state):
    state['ui_theme'] = 'light' if state.get('ui_theme', 'dark') == 'dark' else 'dark'


def open_dashboard(state):
    state['experience_mode'] = 'analysis'
    state['view_mode'] = 'dashboard'


def select_county(state, fips, allowed):
    if fips not in allowed:
        return
    state['highlighted_fips'] = fips
    selected = state.get('chosen_counties', [])
    state['chosen_counties'] = [fips, *(value for value in selected if value != fips)][:3]
    state['comparison_manual'] = True


def theme_figure(fig, theme):
    tokens = THEMES[theme]
    fig.update_layout(paper_bgcolor=tokens['surface'], plot_bgcolor=tokens['surface'],
                      font=dict(color=tokens['text'], family='Arial, sans-serif', size=12),
                      colorway=PALETTE,
                      hoverlabel=dict(bgcolor=tokens['raised'], font_color=tokens['text'], bordercolor=tokens['border']))
    fig.update_xaxes(gridcolor=tokens['border'], zerolinecolor=tokens['border'])
    fig.update_yaxes(gridcolor=tokens['border'], zerolinecolor=tokens['border'])
    return fig


def ranking_table_html(rows, selected_fips):
    """Presentation of main's ranking and existing cost-model lease benchmarks."""
    body = []
    for position, row in enumerate(rows, 1):
        rent = row.get('display_rent')
        rent_text = f'${rent:.2f}' if rent is not None and rent == rent else 'Unavailable'
        employment = row['employment']
        employment_text = f'{employment:,.0f}' if employment is not None and employment == employment else 'Unavailable'
        selected = ' aria-current="true"' if row['fips'] == selected_fips else ''
        body.append(f'<tr{selected}><td>{position}</td><th scope="row">{escape(row["county"])}, {escape(row["state"])}</th>'
                    f'<td><span class="wn-score">{row["score"]:.1f}</span></td><td>{rent_text}</td>'
                    f'<td>{employment_text}</td></tr>')
    return ('<div class="wn-table-scroll" tabindex="0" role="region" aria-label="Current top five rankings">'
            '<table class="wn-table"><thead><tr><th scope="col">#</th><th scope="col">County</th>'
            '<th scope="col">Score / 100</th><th scope="col">Cost-model rent / sq ft / yr</th><th scope="col">Workforce</th>'
            '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>')


def landing_preview_html():
    return """<div class="wn-preview-grid" aria-label="Location intelligence capabilities preview">
    <article class="wn-preview wn-preview-map"><span class="wn-eyebrow">COUNTY INTELLIGENCE</span>
    <h3>A clearer view of your next move.</h3>
    <div class="wn-geospatial" role="img" aria-label="Abstract geospatial illustration; not a scored map"><span class="wn-region wn-region-one"></span><span class="wn-region wn-region-two"></span><span class="wn-region wn-region-three"></span><span class="wn-map-pin"></span></div>
    <p>Compare counties. Understand the trade-offs.</p><span class="wn-badge">Illustration · explore the live dashboard</span></article>
    <article class="wn-preview"><span class="wn-eyebrow">BUSINESS PRIORITIES</span><h3>Your priorities, reflected.</h3><p>Market reach, workforce, pay and electricity.</p></article>
    <article class="wn-preview"><span class="wn-eyebrow">OPERATING COSTS</span><h3>Make costs visible.</h3><p>Transparent facility assumptions and sourced rent benchmarks.</p></article>
    <article class="wn-preview wn-preview-wide"><span class="wn-eyebrow">ASK WHERE NEXT</span><h3>Evidence behind every answer.</h3><p>Explore supporting factors, operational context and data limitations. AI answers require a configured provider.</p></article></div>"""


def themed_dataframe(data, **kwargs):
    """Retain native sorting/export and numerical types, style cells per session."""
    import pandas as pd
    import streamlit as st
    tokens = THEMES[st.session_state.get('ui_theme', 'dark')]
    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    styled = frame.style.set_properties(**{'background-color': tokens['surface'], 'color': tokens['text']})
    return st.dataframe(styled, **kwargs)
