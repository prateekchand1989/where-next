import json
from copy import deepcopy
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from core import ROOT, LABELS, PRESETS, load_data, score_counties, evidence_brief, annual_electricity_expense, weight_sensitivity
from weather import get_alerts, get_forecast
from fema import FIELDS as FEMA_FIELDS, NUMERIC_FIELDS as FEMA_NUMERIC_FIELDS, load_fema_context
from interpretation import (SECTIONS, build_evidence, evidence_fingerprint,
                            configured_provider, generate_interpretation, generate_answer, render_answer_markdown)
from streamlit.errors import StreamlitSecretNotFoundError
from analysis_intent import STATES, parse_changes, change_lines, tile_summary
from question_weather import enrich_weather
from summary_cards import summary_cards_html
from ui_styles import application_styles
from design_system import (THEMES, PALETTE, initialize_theme, toggle_theme, open_dashboard,
                           select_county, theme_figure, ranking_table_html, landing_preview_html,
                           themed_dataframe)
from interaction_state import (initialize_interactions, reset_interactions, apply_patch,
    accept_states, mark_manual_change, apply_refresh, retry_refresh, current_question,
    control_signature, begin_request, finish_request)
from operating_costs import lease_benchmark
from cost_panel import render_cost_panel, dollars
from question_state import DEFAULT_SCENARIO, WEIGHT_KEYS, initialize_question_state, reset_for_new_question, sync_county_state

initialize_question_state(st.session_state)
initialize_theme(st.session_state)
initialize_interactions(st.session_state)
ui_theme = st.session_state["ui_theme"]
tokens = THEMES[ui_theme]


def submit_question(input_key):
    question = st.session_state.get(input_key, '').strip()
    if question:
        st.session_state['interaction_revision'] += 1
        st.session_state['last_user_question'] = question
        st.session_state['active_question'] = question
        st.session_state.pop('manual_refresh_mode', None)
        st.session_state.pop('manual_scope_override', None)
        st.session_state['submitted_question'] = question
        st.session_state['pending_question'] = question
        st.session_state['experience_mode'] = 'analysis'
        st.session_state['view_mode'] = 'ask'


def use_suggestion():
    if st.session_state.get('suggested_question'):
        st.session_state['landing_question'] = st.session_state['suggested_question']


def start_new_question():
    reset_for_new_question(st.session_state)
    reset_interactions(st.session_state)
    st.session_state.pop('location_interpretation_history', None)


def switch_view(mode):
    st.session_state['experience_mode'] = 'analysis'
    st.session_state['view_mode'] = mode


st.set_page_config(page_title='Where Next | Warehouse Location Intelligence',
                   layout='wide')
st.html(application_styles(landing=st.session_state['experience_mode'] == 'landing', theme=ui_theme))
with st.container(key='theme_toggle'):
    next_theme = 'light' if ui_theme == 'dark' else 'dark'
    st.button(f'Switch to {next_theme} mode', key='toggle_theme',
              icon=':material/light_mode:' if ui_theme == 'dark' else ':material/dark_mode:',
              help=f'Switch to {next_theme} mode', on_click=toggle_theme, args=(st.session_state,))

BRAND = '<div class="wn-brand"><span class="wn-location-mark" aria-hidden="true"></span><div><strong>Where Next</strong><small>Location Intelligence</small></div></div>'

if st.session_state['experience_mode'] != 'landing':
    with st.sidebar:
        with st.container(key='sidebar_navigation'):
            st.html(BRAND)
            with st.container(key='primary_navigation'):
                st.button('Ask Where Next', key='nav_ask', icon=':material/chat:', width='stretch',
                          type='primary' if st.session_state['view_mode'] == 'ask' and st.session_state['experience_mode'] != 'landing' else 'secondary',
                          on_click=switch_view, args=('ask',))
                st.button('Dashboard', key='nav_overview', icon=':material/dashboard:', width='stretch',
                          type='primary' if st.session_state['view_mode'] == 'dashboard' and st.session_state['experience_mode'] != 'landing' else 'secondary',
                          on_click=switch_view, args=('dashboard',))
                st.button('Start a new question', key='start_new_question', icon=':material/add:', width='stretch',
                          on_click=start_new_question)


if st.session_state['experience_mode'] == 'landing':
    with st.container(key='landing_experience'):
        main, preview = st.columns([1.1, 1], gap='large')
        with main:
            with st.container(key='landing_hero'):
                st.html(BRAND)
                st.html('<span class="wn-eyebrow">A BETTER PLACE TO BEGIN</span>')
                st.title("Find the right location for what's next.")
                st.markdown('AI-powered warehouse location intelligence using public data.')
                with st.container(key='landing_panel'):
                    st.text_area('Your warehouse question', key='landing_question', height=150,
                                 placeholder='Ask where your next warehouse should be...', label_visibility='collapsed')
                    st.button('Ask Where Next', key='ask_where_next', type='primary', width='stretch',
                              icon=':material/arrow_forward:', on_click=submit_question, args=('landing_question',))
                st.pills('Try a question', [
                    'Where should I put a warehouse in the Northeast?',
                    'Which counties balance reach and labor cost best?',
                    'What are the strongest locations for a temperature-controlled facility?',
                    'Which locations have the lowest long-term risk?',
                    'Why does the current leader rank first?',
                    'Which locations should I investigate further?',
                ], key='suggested_question', on_change=use_suggestion)
                st.caption('Public data · transparent assumptions · county-level screening')
                st.button('Explore the dashboard', key='explore_dashboard', icon=':material/dashboard:',
                          on_click=open_dashboard, args=(st.session_state,))
                st.caption('Explore rankings without an API key. AI answers require a configured provider.')
        with preview:
            st.html(landing_preview_html())
    st.stop()

# A stable view boundary prevents old keyed dashboard children being retained
# when native Streamlit reconciles a differently ordered conversation layout.
with st.container(key='workspace_' + st.session_state['view_mode']):
    answer_slot = st.container()
    if st.session_state['view_mode'] == 'ask':
        st.subheader('Your question')
        if st.session_state['submitted_question']:
            st.text(current_question(st.session_state))
        # Reserve answer above the input while computing current evidence later in the run.
        answer_slot = st.container()
        with st.container():
            st.chat_input('Ask a follow-up', key='followup_question',
                          on_submit=submit_question, args=('followup_question',))
    history_slot = st.container(key='history_answers')
    with st.container(key='workspace_header'):
        st.html('<div id="overview"></div>')
        st.title("Find the right location for what's next.")
        st.write('County analysis for warehouse location decisions, grounded in public data.')
    st.caption('Public-data screening · PA / NJ / NY / OH / MD · 2024 baseline. Indicators support early comparisons; they are not property quotes or validated investment recommendations.')


    @st.cache_data
    def read_data():
        return load_data()


    @st.cache_data(ttl=900)
    def cached_weather(lat, lon):
        return get_alerts(lat, lon)


    @st.cache_data(ttl=900)
    def cached_forecast(lat, lon):
        return get_forecast(lat, lon)


    def formatted_number(value, pattern):
        """Presentation only: keep unavailable figures explicit."""
        return format(value, pattern) if np.isfinite(value) else 'Unavailable'


    def rebalance_priority_weights(changed_index):
        """Keep the changed slider fixed and proportionally rebalance the rest to total 100."""
        changed_value = int(st.session_state[WEIGHT_KEYS[changed_index]])
        remainder = 100 - changed_value
        other_indices = [i for i in range(4) if i != changed_index]
        other_values = np.array([st.session_state[WEIGHT_KEYS[i]] for i in other_indices], dtype=float)
        other_total = other_values.sum()

        if other_total > 0:
            exact = other_values / other_total * remainder
        else:
            exact = np.full(3, remainder / 3)

        floored = np.floor(exact).astype(int)
        leftover = remainder - int(floored.sum())
        order = np.argsort(-(exact - floored), kind='stable')
        for position in order[:leftover]:
            floored[position] += 1

        for index, value in zip(other_indices, floored):
            st.session_state[WEIGHT_KEYS[index]] = int(value)
        st.session_state['weight_preset'] = st.session_state['scenario']
        apply_patch(st.session_state, {'priority_weights': [st.session_state[k] for k in WEIGHT_KEYS]}, data)
        mark_manual_change(st.session_state, 'weights')


    def apply_scenario_preset():
        preset = st.session_state['scenario']
        for key, value in zip(WEIGHT_KEYS, PRESETS[preset]):
            st.session_state[key] = int(value)
        st.session_state['weight_preset'] = preset


    def scenario_changed():
        apply_patch(st.session_state, {'scenario': st.session_state['scenario']}, data)
        mark_manual_change(st.session_state, 'scenario')


    def manual_states_changed():
        accept_states(st.session_state, data)


    def default_weights_changed():
        apply_scenario_preset()
        mark_manual_change(st.session_state, 'weights')


    data, geometry = read_data()
    fema_context, fema_metadata = load_fema_context(data)
    # Consume the user trigger BEFORE rendering control widgets. Mutating their session
    # values here makes the normal deterministic run use the updated controls immediately.
    pending_question = st.session_state.pop('pending_question', None)
    if pending_question:
        try:
            ai_settings = {name: st.secrets.get(name) for name in
                           ('AI_PROVIDER', 'OPENAI_API_KEY', 'OPENAI_MODEL') if name in st.secrets}
        except StreamlitSecretNotFoundError:
            ai_settings = {}
        preset_before = st.session_state.get('scenario', DEFAULT_SCENARIO)
        weights_before = [st.session_state.get(key, default)
                          for key, default in zip(WEIGHT_KEYS, PRESETS[preset_before])]
        states_before = st.session_state.get('candidate_states', list(STATES))
        controls = {'scenario': preset_before, 'priority_weights': weights_before,
                    'candidate_states': states_before,
                    'selected_counties': st.session_state.get('chosen_counties', [])}
        intent_revision = st.session_state['interaction_revision']
        intent_controls = control_signature(st.session_state)
        with st.spinner('Reading your analysis preferences...'):
            changes = parse_changes(configured_provider(ai_settings), pending_question, controls, data)
        if (intent_revision == st.session_state['interaction_revision']
                and intent_controls == control_signature(st.session_state)):
            changes = apply_patch(st.session_state, changes, data)
        else:
            # A newer native control event wins over an older provider response.
            changes = {}
            st.session_state['manual_scope_override'] = True
            pending_question = current_question(st.session_state)
        st.session_state['pending_answer'] = {'question': pending_question, 'changes': changes, 'automatic': False}
    with st.sidebar:
        st.markdown('[County Rankings](#rankings)\n\n[Map Explorer](#map-explorer)\n\n[Scenario Analysis](#scenario-analysis)\n\n[AI Insights](#ai-insights)\n\n[Data & Exports](#data-exports)\n\n[Factor Weights](#factor-weights)')
        st.header('Business priorities')
        st.caption('Define the screening question, then explore the trade-offs.')
        st.subheader('Scenario')
        preset = st.selectbox('Scenario', list(PRESETS), label_visibility='collapsed', key='scenario', persist_state='session', on_change=scenario_changed)
        st.caption('Presets are illustrative, not industry standards.')
        st.subheader('Candidate states')
        states = st.multiselect('Candidate states', STATES,
                                default=None if 'candidate_states' in st.session_state else list(STATES), label_visibility='collapsed',
                                key='candidate_states', persist_state='session', on_change=manual_states_changed)
        if st.session_state.get('state_selection_notice'):
            st.warning(st.session_state['state_selection_notice'])
        st.html('<div id="factor-weights"></div>')
        st.subheader('Business priority weights')
        if st.session_state.get('weight_preset') != preset:
            apply_scenario_preset()

        weights = [
            st.slider(
                label, 0, 100, key=WEIGHT_KEYS[i],
                on_change=rebalance_priority_weights, args=(i,), persist_state='session'
            )
            for i, label in enumerate(LABELS)
        ]
        st.button('Default Weights', key='default_weights', on_click=default_weights_changed, width='stretch')
        apply_ai_slot = st.container()
        st.caption('Rankings update immediately. Ask a question to request a new AI interpretation.')
        st.caption('Move any slider and the other three rebalance automatically so the total remains 100%.')
        st.caption(f"Current total: **{sum(weights)}%**")
        normalized_weights = np.asarray(weights, dtype=float)
        for label, weight in zip(LABELS, normalized_weights):
            st.caption(f'{label}: **{weight:.0f}%**')
        st.subheader('Map settings')
        national = st.checkbox('Show contiguous U.S. overview', value=False, key='national_map', persist_state='session')
        st.caption('Outside the five-state scope: no score. National outlines provide geographic context.')

    all_scored = score_counties(data, weights)
    view = all_scored[all_scored.state.isin(states)]
    ranked = view[view.complete]
    # All live displays and evidence share this score-first, filter-second result.
    target_question = pending_question
    if (not target_question and st.session_state.get('manual_refresh_mode') == 'manual'
            and st.session_state.get('manual_refresh_kind') in ('states', 'scenario', 'weights')):
        target_question = current_question(st.session_state) or None
    sync_county_state(st.session_state, all_scored, ranked, states, target_question,
                      weights=weights, scenario=preset)
    if view.empty:
        if st.session_state.get('question_answer'):
            answer_slot.info('Your analysis has changed. Ask again for an updated answer.')
        if st.session_state.pop('pending_answer', None):
            answer_slot.info('Select at least one candidate state, then submit your question again.')
        st.warning('Select at least one candidate state.')
        st.stop()
    leader = ranked.iloc[0] if not ranked.empty else None
    if ranked.empty:
        st.warning('No counties with complete scoring data are available in the selected states. Rankings are unavailable.')
    highlight_fips = st.session_state.get('highlighted_fips')
    highlight_rank = st.session_state.get('highlighted_rank')
    highlighted = all_scored.set_index('fips', drop=False).loc[highlight_fips] if highlight_fips else None
    def highlighted_value(field, pattern, prefix='', suffix=''):
        if highlighted is None or not np.isfinite(highlighted[field]):
            return 'Unavailable'
        return prefix + formatted_number(highlighted[field], pattern) + suffix

    summary_slot = st.container(key='highlighted_county')
    operating_cost = render_cost_panel(ranked, preset)
    with summary_slot:
        st.html(summary_cards_html([
            (f'Current #{highlight_rank} county' if highlight_rank else 'Selected county',
             f"{highlighted['county']}, {highlighted['state']}" if highlighted is not None else 'Unavailable',
             'Screening score: ' + highlighted_value('score', '.1f', suffix=' / 100')),
            ('Warehousing employment', highlighted_value('employment', ',.0f'), 'Existing warehousing workforce depth'),
            ('Average annual pay', highlighted_value('annual_pay', ',.0f', prefix='$'), '2024 industry labor benchmark'),
            ('Electricity benchmark', highlighted_value('electricity_cents_kwh', '.2f', suffix=' ¢/kWh'),
             '2024 state commercial electricity benchmark'),
            ('Estimated Annual Cost / Sq Ft',
             dollars(operating_cost['annual_psf']) + (' / sq ft / year' if operating_cost['annual_psf'] is not None else ''),
             'Illustrative warehouse operating cost based on selected facility assumptions.'),
        ], theme=ui_theme))
    st.caption(f'{len(view)} counties evaluated · {len(ranked)} with complete scoring data.')
    st.caption(f'{len(view) - len(ranked)} incomplete counties in the current selection remain unranked and searchable. Scores use the fixed complete five-state reference set before state filtering.')

    county_labels = dict(zip(all_scored.fips, all_scored.county + ', ' + all_scored.state))
    with st.container(key='map_rankings'):
        map_column, summary_column = st.columns([1.15, 1], gap='medium', wrap=True)
        with map_column:
            with st.container(key='screening_map'):
                st.html('<div id="map-explorer"></div>')
                st.subheader('County screening map')
                map_view = st.selectbox('Map view', ['Warehouse screening score', 'FEMA risk context'],
                                        key='map_view', persist_state='session')
                fig = go.Figure()
                fig.add_trace(go.Choroplethmap(
                    geojson=geometry, locations=[f['id'] for f in geometry['features']], z=[0] * len(geometry['features']),
                    colorscale=[[0, tokens['unavailable']], [1, tokens['unavailable']]], showscale=False,
                    marker_line_width=0.25, marker_line_color=tokens['border'], hoverinfo='skip'))
                if map_view == 'Warehouse screening score' and not ranked.empty:
                    fig.add_trace(go.Choroplethmap(
                        geojson=geometry, locations=ranked.fips, z=ranked.score,
                        text=ranked.county + ', ' + ranked.state, colorscale=[[0, '#123D2B'], [.35, '#087346'], [.7, '#24C77B'], [1, '#A3F3B7']], zmin=0, zmax=100,
                        customdata=ranked[['reach_250mi', 'employment', 'annual_pay', 'electricity_cents_kwh']].to_numpy(),
                        marker_line_width=0.5, marker_line_color=tokens['border'], colorbar_title='Score',
                        hovertemplate=(
                            '<b>%{text}</b><br>Screening score: %{z:.1f}/100'
                            '<br>Population within 250 miles: %{customdata[0]:,.0f}'
                            '<br>Warehousing employment: %{customdata[1]:,.0f}'
                            '<br>Average annual pay: $%{customdata[2]:,.0f}'
                            '<br>Electricity benchmark: %{customdata[3]:.2f} cents/kWh<extra></extra>')))
                elif map_view == 'FEMA risk context':
                    if fema_metadata['status'] == 'ok':
                        hazard_map = view[['fips', 'county', 'state']].merge(
                            fema_context[['fips', 'RISK_SCORE', 'RISK_RATNG']],
                            on='fips', how='left', validate='one_to_one')
                        hazard_map = hazard_map[hazard_map.RISK_SCORE.notna()]
                        fig.add_trace(go.Choroplethmap(
                            geojson=geometry, locations=hazard_map.fips, z=hazard_map.RISK_SCORE,
                            text=hazard_map.county + ', ' + hazard_map.state,
                            customdata=hazard_map[['RISK_RATNG']].fillna('Unavailable').to_numpy(),
                            colorscale='YlOrRd', zmin=0, zmax=100,
                            marker_line_width=0.5, marker_line_color=tokens['border'],
                            colorbar_title='FEMA risk',
                            hovertemplate=('<b>%{text}</b><br>FEMA risk score: %{z:.1f}/100'
                                           '<br>FEMA rating: %{customdata[0]}<extra></extra>')))
                        st.caption('FEMA community risk context · Higher means higher relative risk. Gray = unavailable or outside selected scope. Warehouse rankings remain unchanged.')
                    else:
                        st.info('FEMA risk context unavailable. Warehouse screening remains available.')
                if highlighted is not None:
                    fig.add_trace(go.Scattermap(lon=[highlighted['lon']], lat=[highlighted['lat']],
                                               mode='markers', marker={'size': 14, 'color': tokens['accent'], 'opacity': 0.75},
                                               name='Highlighted county', showlegend=False,
                                               text=[f"{highlighted['county']}, {highlighted['state']}"],
                                               hovertemplate='<b>%{text}</b><extra>Highlighted county</extra>'))
                fig.update_layout(
                    map={'style': {'version': 8, 'sources': {}, 'layers': [{'id': 'background', 'type': 'background', 'paint': {'background-color': tokens['surface']}}]}, 'center': {'lon': -98 if national else -77.8, 'lat': 39 if national else 40.2},
                         'zoom': 2.6 if national else 4.3},
                    height=420, margin={'l': 0, 'r': 0, 't': 0, 'b': 0}, clickmode='event+select')
                theme_figure(fig, ui_theme)
                st.plotly_chart(fig, width='stretch', key='county_map', theme=None,
                                alt=('County screening scores with unranked counties in gray'
                                     if map_view == 'Warehouse screening score'
                                     else 'FEMA long-term county risk context with missing counties in gray'))
                def choose_map_county():
                    if st.session_state.get('map_county_selection') in set(view.fips):
                        select_county(st.session_state, st.session_state['map_county_selection'], set(view.fips))
                        mark_manual_change(st.session_state, 'comparison')
                st.selectbox('Inspect a county on the map', view.fips.tolist(), index=None,
                             format_func=county_labels.get,
                             key='map_county_selection', on_change=choose_map_county,
                             placeholder='Search counties, including unavailable data')
                if map_view == 'Warehouse screening score':
                    st.caption('Census 2024 boundaries · Gray = unranked, unavailable, or outside selected scope. No commercial map token required.')
                else:
                    st.caption('FEMA county context uses the existing Census 2024 map boundaries; this is not a property-level hazard map.')
        with summary_column:
            with st.container(key='top_five'):
                st.html('<div id="rankings"></div>')
                st.subheader('Current top five')
                st.caption('Highest screening scores in your selected states.')
                if ranked.empty:
                    st.caption('No complete counties are available in this selection.')
                else:
                    ranking_rows = ranked.head(5).to_dict('records')
                    for row in ranking_rows:
                        benchmark = lease_benchmark(row['fips'], preset)
                        row['display_rent'] = benchmark['asking_rent_psf_year'] if benchmark else None
                    st.html(ranking_table_html(ranking_rows, highlight_fips))
                    st.caption('Rent is the existing cost-model benchmark; it does not affect rankings.')
                    def choose_ranked_county():
                        if st.session_state.get('ranking_selection') in set(view.fips):
                            select_county(st.session_state, st.session_state['ranking_selection'], set(view.fips))
                            mark_manual_change(st.session_state, 'comparison')
                    st.selectbox('Inspect a ranked county', ranked.head(5).fips.tolist(), index=None,
                                 format_func=county_labels.get, key='ranking_selection',
                                 on_change=choose_ranked_county, placeholder='Choose a county to compare')
                    with st.expander('Ranking evidence', key='ranking_evidence'):
                        for position, (_, row) in enumerate(ranked.head(5).iterrows(), 1):
                            st.markdown(f"**{position}. {row['county']}, {row['state']}**  \nScreening score · **{row['score']:.1f} / 100**")
                if highlighted is not None:
                    st.markdown(f"**Selected county** · {highlighted['county']}, {highlighted['state']}")
                    st.caption('Score: ' + highlighted_value('score', '.1f', suffix=' / 100'))
                with st.expander('Screening priorities', key='ranking_priorities'):
                    st.markdown('**Current priorities**')
                    st.write(preset)
                    for label, weight in zip(LABELS, normalized_weights):
                        st.caption(f'{label} · **{weight:.2f}%**')
                st.caption('A shortlist for further investigation. Higher scores reflect the selected priorities.')

    with st.container(key='analysis_overview'):
        weights_col, scenario_col, insights_col = st.columns([1, 1.15, 1.1], gap='medium')
        with weights_col:
            with st.container(key='weights_overview'):
                st.subheader('Factor weightings')
                donut = go.Figure(go.Pie(labels=LABELS, values=weights, hole=.72,
                                       marker_colors=PALETTE, textinfo='none', sort=False,
                                       hovertemplate='%{label}: %{value}%<extra></extra>'))
                donut.update_layout(height=190, margin=dict(l=0,r=0,t=0,b=0), showlegend=False,
                                    annotations=[dict(text=f'{sum(weights)}%<br>Total', x=.5, y=.5, showarrow=False)])
                st.plotly_chart(theme_figure(donut, ui_theme), theme=None, key='weight_ring',
                                config={'displayModeBar': False}, alt='Current business priority weight percentages')
                for label, weight in zip(LABELS, weights):
                    st.caption(f'{label} · **{weight}%**')
                st.markdown('[Adjust factor weights ?](#factor-weights)')
        with scenario_col:
            scenario_overview_slot = st.container(key='scenario_overview')
        with insights_col:
            insights_overview_slot = st.container(key='insights_overview')

    st.subheader('County comparison')
    st.caption('Search any county in the selected states, including counties with incomplete labor data.')
    labels = dict(zip(view.fips, view.county + ', ' + view.state))
    def mark_manual_comparison():
        st.session_state['comparison_manual'] = True
        mark_manual_change(st.session_state, 'comparison')

    chosen = st.multiselect('Choose up to three counties', list(labels),
                            default=None if 'chosen_counties' in st.session_state else list(ranked.head(3).fips),
                            format_func=lambda x: labels[x], max_selections=3, key='chosen_counties', persist_state='session', on_change=mark_manual_comparison)
    if chosen:
        selected = all_scored.set_index('fips').loc[chosen].reset_index()
        with st.container(key='comparison_panel'):
            comparison = selected[['county', 'state', 'score', 'reach_250mi', 'employment',
                                   'annual_pay', 'electricity_cents_kwh', 'labor_status']].copy()
            comparison['county'] = comparison['county'] + ', ' + comparison['state']
            for column in ['reach_250mi', 'employment']:
                comparison[column] = comparison[column].map(lambda value: formatted_number(value, ',.0f'))
            comparison['annual_pay'] = comparison['annual_pay'].map(
                lambda value: '$' + formatted_number(value, ',.0f') if np.isfinite(value) else 'Unavailable')
            comparison['electricity_cents_kwh'] = comparison['electricity_cents_kwh'].map(
                lambda value: formatted_number(value, '.2f') + ' cents/kWh' if np.isfinite(value) else 'Unavailable')
            comparison = comparison.drop(columns='state').rename(columns={
                'county': 'County', 'score': 'Score', 'reach_250mi': 'Population within 250 miles',
                'employment': 'Warehousing employment', 'annual_pay': 'Average annual pay',
                'electricity_cents_kwh': 'Electricity benchmark', 'labor_status': 'Labor data status'})
            themed_dataframe(comparison, hide_index=True, width='stretch', key='county_comparison',
                         column_config={'Score': st.column_config.NumberColumn(format='%.1f')})
            st.caption('Unavailable figures stay missing. Annual industry pay is not an hourly offer; electricity is a state average.')

        with st.expander('Illustrative annual electricity expense', expanded=True, key='electricity_panel'):
            annual_kwh = st.number_input('Annual electricity consumption (kWh)', min_value=0.0,
                                        value=None, step=1000.0, key='annual_kwh', persist_state='session',
                                        on_change=mark_manual_change, args=(st.session_state,))
            st.caption('Annual kWh × cents/kWh ÷ 100. Uses the 2024 state commercial average, not an actual property tariff or site quote. This expense does not change screening scores.')
            if annual_kwh is None:
                st.caption('Enter consumption to compare illustrative annual expenses.')
            else:
                expenses = selected[['county', 'state', 'electricity_cents_kwh']].copy()
                expenses['county'] = expenses['county'] + ', ' + expenses['state']
                expenses['Annual consumption (kWh)'] = annual_kwh
                expenses['Illustrative annual expense (USD)'] = annual_electricity_expense(
                    annual_kwh, expenses['electricity_cents_kwh']).round(2)
                expenses['Illustrative annual expense (USD)'] = expenses['Illustrative annual expense (USD)'].map(
                    lambda value: '$' + formatted_number(value, ',.2f') if np.isfinite(value) else 'Unavailable')
                expenses = expenses.drop(columns='state').rename(columns={
                    'county': 'County', 'electricity_cents_kwh': '2024 state commercial average (cents/kWh)'})
                themed_dataframe(expenses, hide_index=True, width='stretch',
                             column_config={'2024 state commercial average (cents/kWh)': st.column_config.NumberColumn(format='%.2f'),
                                            'Annual consumption (kWh)': st.column_config.NumberColumn(format='localized')})
        with st.expander('County evidence summaries', key='evidence_panel'):
            for _, row in selected.iterrows():
                st.write(evidence_brief(row))
        with st.expander('Long-term hazard context', expanded=True, key='fema_panel'):
            st.caption('Long-term hazard and resilience context. NWS = current / near-term operational weather. FEMA NRI = historical/modelled long-term hazard context. Neither alters the warehouse screening score.')
            st.caption('FEMA community risk is not the probability that a specific warehouse will be damaged. County flood scores are not a property-level flood assessment; investigate site flood maps and engineering separately.')
            if fema_metadata['status'] != 'ok':
                st.info('FEMA hazard data unavailable. Warehouse screening remains available.')
            else:
                hazard_table = selected[['fips', 'county', 'state']].merge(
                    fema_context, on='fips', how='left', validate='one_to_one')
                hazard_table['County'] = hazard_table.county + ', ' + hazard_table.state
                for field in FEMA_NUMERIC_FIELDS:
                    hazard_table[field] = hazard_table[field].map(
                        lambda value, field=field: 'Unavailable' if not np.isfinite(value)
                        else f'${value:,.0f}' if field == 'EAL_VALT' else f'{value:.1f} / 100')
                hazard_table = hazard_table[['County', *FEMA_FIELDS]].rename(columns=FEMA_FIELDS)
                themed_dataframe(hazard_table.fillna('Unavailable'), hide_index=True, width='stretch',
                             alt='FEMA overall risk, annual loss, flood, winter weather, and hurricane context for selected counties')
                st.caption(f"FEMA NRI · {fema_metadata['version']} · retrieved {fema_metadata['retrieved_utc']} · source data updated {fema_metadata['source_data_updated_utc']}")
                st.caption(f"FIPS coverage: {fema_metadata['matched']} matched; {fema_metadata['unmatched']} unmatched; {len(fema_metadata['duplicate_fips'])} duplicate FIPS. Missing values remain unavailable; FEMA applicability ratings are preserved.")
                st.caption('Expected annual loss is a county aggregate including buildings, agriculture, and monetized population losses; it is not a warehouse loss estimate. Scores are relative indices, not damage probabilities.')
                st.markdown('[FEMA National Risk Index county source](' + fema_metadata['source_url'] + ')')
        with st.expander('Operational context · NWS alerts', expanded=True, key='weather_panel'):
            if st.session_state.get('weather_county') not in chosen:
                st.session_state['weather_county'] = None
            current = st.selectbox('Weather at county representative point', chosen,
                                   format_func=lambda x: labels[x], index=None,
                                   placeholder='Select a county for weather', key='weather_county', persist_state='session')
            if current is None:
                st.caption('Select a county for weather, then click an NWS button to check conditions.')
            else:
                row = data.set_index('fips').loc[current]
                if st.button('Check NWS alerts'):
                    result = cached_weather(float(row.lat), float(row.lon))
                    st.session_state.setdefault('interpretation_weather', {}).setdefault(current, {})['alerts'] = result
                    mark_manual_change(st.session_state, 'weather')
                    if result['status'] == 'ok':
                        st.caption('Checked UTC: ' + result['checked_utc'] + ' · cached for up to 15 minutes')
                        if result['alerts']:
                            themed_dataframe(result['alerts'], hide_index=True)
                        else:
                            st.success('NWS returned no active alerts for this point at the checked time.')
                    else:
                        st.warning('Weather unavailable. This does not mean there are no alerts.')
                    st.markdown('[NWS source query](' + result['url'] + ')')
                with st.container(key='forecast_panel'):
                    st.markdown(f"**Point forecast · {labels[current]}**")
                    st.caption('A point forecast is not county-wide or route-wide weather coverage. Weather is separate from the warehouse screening score.')
                    if st.button('Check NWS forecast'):
                        forecast = cached_forecast(float(row.lat), float(row.lon))
                        st.session_state.setdefault('interpretation_weather', {}).setdefault(current, {})['forecast'] = forecast
                        if forecast['status'] == 'ok':
                            st.caption('Checked UTC: ' + forecast['checked_utc'] + ' · cached for up to 15 minutes')
                            if forecast['updated']:
                                st.caption('NWS updated: ' + forecast['updated'])
                            if forecast['generated_at']:
                                st.caption('NWS issued/generated: ' + forecast['generated_at'])
                            themed_dataframe([
                                {'Period': period['name'],
                                 'Temperature': f"{period['temperature']} °{period['temperatureUnit']}",
                                 'Forecast': period['shortForecast'],
                                 'Wind': f"{period['windSpeed']} {period['windDirection']}"}
                                for period in forecast['periods'][:4]
                            ], hide_index=True, width='stretch',
                               alt='Next four NWS forecast periods at the selected county representative point')
                        else:
                            st.warning('Point forecast unavailable. Try again later.')
                        st.markdown('[NWS forecast source](' + forecast['url'] + ')')
            st.caption('A point query does not cover every part of a county or a transport route. Weather does not change the investment score.')
    else:
        st.caption('Select a county to inspect its indicators, electricity expense, and weather context.')

    factor = st.session_state.get('sensitivity_factor', LABELS[0])
    if st.session_state['view_mode'] == 'dashboard':
        st.subheader('How stable is this recommendation?')
        st.caption('This tests whether the shortlist changes when one business priority is moved up or down by 10 percentage points.')
        factor = st.selectbox('Business priority to test', LABELS, key='sensitivity_factor', persist_state='session',
                              on_change=mark_manual_change, args=(st.session_state,))
    scenarios = weight_sensitivity(data, weights, LABELS.index(factor), states, current_scored=all_scored)
    with scenario_overview_slot:
        st.html('<div id="scenario-analysis"></div>')
        st.subheader('Scenario analysis')
        st.caption(f'{factor} sensitivity · existing four-factor screening')
        scenario_chart = go.Figure()
        for scenario, color, short_name in zip(scenarios, PALETTE, ['Current', 'Minus 10 pp', 'Plus 10 pp']):
            top = scenario['top_five']
            scenario_chart.add_trace(go.Bar(name=short_name, x=top.county.str.replace(' County', '', regex=False) + ', ' + top.state,
                                            y=top.score, marker_color=color))
        scenario_chart.update_layout(height=270, margin=dict(l=0,r=0,t=5,b=20), barmode='group',
                                     yaxis=dict(title=None, range=[0,100]), xaxis=dict(tickangle=-35),
                                     legend=dict(orientation='h', y=-.4, font_size=10))
        st.plotly_chart(theme_figure(scenario_chart, ui_theme), theme=None, key='scenario_preview',
                        config={'displayModeBar': False}, alt='Top five scores in current and adjusted priority scenarios')
        st.caption('Current and adjusted priority mixes. Detailed sensitivity results appear below.')

    if st.session_state['view_mode'] == 'dashboard':
        with st.container(key='sensitivity_panel'):
            winners = [s['top_five'].iloc[0] for s in scenarios if not s['top_five'].empty]
            if not winners:
                st.info('No complete counties are available in the selected states for sensitivity analysis.')
            elif len({row.fips for row in winners}) == 1:
                st.caption(f"**{winners[0]['county']}, {winners[0]['state']} remains first in all three scenarios.**")
            else:
                st.caption('**The first-ranked county changes across these scenarios.**')
            for tab, scenario in zip(st.tabs(['Current', '−10 pp', '+10 pp']), scenarios):
                with tab:
                    st.markdown('**' + scenario['name'] + '**')
                    st.caption(' · '.join(f'{label}: {weight:.2f}%' for label, weight in zip(LABELS, scenario['display_weights'])))
                    top = scenario['top_five'][['rank', 'county', 'state', 'score']].copy()
                    top['county'] = top['county'] + ', ' + top['state']
                    top = top.drop(columns='state').rename(columns={'rank': 'Rank', 'county': 'County / state', 'score': 'Score'})
                    themed_dataframe(top, hide_index=True, width='stretch',
                                 column_config={'Score': st.column_config.NumberColumn(format='%.1f')})
                    st.markdown('**Top-three membership vs current weights**')
                    for _, row in scenario['top_three_changes'].iterrows():
                        with st.container(horizontal=True):
                            status_color = {'Remains top three': 'gray', 'Drops out of top three': 'orange', 'Enters top three': 'green'}[row['change']]
                            st.badge(row['change'], color=status_color)
                            st.write(f"{row['county']}, {row['state']} · rank {row['rank']}")
            with st.expander('How to read sensitivity results'):
                st.write('The selected factor moves by up to 10 percentage points, capped at 0–100%. Other factors retain their relative proportions. If all other weights are zero, released weight is split equally among them.')
                st.write('Weights are displayed to two decimals with rounding remainders allocated so each mix totals 100%. Scores use unrounded weights. Rankings use the complete five-state universe before filtering to your selected states.')

    # Fill the reserved top-of-page answer only after all current evidence is available.
    question_selected = all_scored.set_index('fips').loc[chosen].reset_index()
    def evidence_for_question(question):
        return build_evidence(
            question_selected, leader, weights, preset, states,
            st.session_state.get('annual_kwh') if chosen else None,
            fema_context, fema_metadata, st.session_state.get('interpretation_weather', {}),
            factor, scenarios, scored=all_scored, ranked=ranked, question=question,
            highlighted_fips=st.session_state.get('highlighted_fips'))


    # Only a submitted question or an explicit Retry button can request AI.
    retry_requested = st.session_state.pop('retry_requested', False)
    summary_refresh_requested = (retry_requested and st.session_state.pop('retry_target', 'answer') == 'summary')
    pending_answer = st.session_state.pop('pending_answer', None)
    if pending_answer and pending_answer.get('automatic'):
        pending_answer = None  # Discard requests queued by older automatic refresh code.
    if st.session_state.get('manual_refresh_mode') == 'auto':
        st.session_state['manual_refresh_mode'] = 'manual'
        st.session_state['ai_refresh'] = {'status': 'stale'}
    if retry_requested and not summary_refresh_requested and not pending_answer and current_question(st.session_state):
        pending_answer = {'question': current_question(st.session_state), 'changes': {}, 'automatic': False}
    if not pending_answer and not summary_refresh_requested and st.session_state['ai_refresh'].get('status') in ('pending', 'running', 'pending_apply'):
        st.session_state['ai_refresh'] = {'status': 'stale'}
    if pending_answer:
        # Rank first, resolve the updated target, enrich weather, then rebuild evidence.
        target_evidence = evidence_for_question(pending_answer['question'])
        with answer_slot:
            with st.spinner('Checking operational weather for your question...'):
                enrich_weather(pending_answer['question'], target_evidence['question_context'], data,
                               st.session_state.setdefault('interpretation_weather', {}),
                               cached_weather, cached_forecast)
    question_evidence = evidence_for_question(pending_answer['question'] if pending_answer else current_question(st.session_state))
    question_fingerprint = evidence_fingerprint(question_evidence)
    analysis_fingerprint = evidence_fingerprint(evidence_for_question(''))


    def turn_is_stale(turn):
        # Compare each historical question with its own freshly rebuilt target context.
        return turn['fingerprint'] != evidence_fingerprint(evidence_for_question(turn['question']))


    if pending_answer:
        question = pending_answer['question']
        try:
            ai_settings = {name: st.secrets.get(name) for name in
                           ('AI_PROVIDER', 'OPENAI_API_KEY', 'OPENAI_MODEL') if name in st.secrets}
        except StreamlitSecretNotFoundError:
            ai_settings = {}
        current_history = [
            {'question': turn['question'], 'answer': turn['result'].get('answer', '')}
            for turn in st.session_state['question_history']
            if turn.get('analysis_fingerprint') == analysis_fingerprint and not turn_is_stale(turn)
            and turn['result']['status'] == 'ok']
        token = begin_request(st.session_state, question, question_fingerprint)
        with answer_slot:
            with st.spinner('Answering from updated supplied evidence...'):
                answer = generate_answer(
                    question_evidence, configured_provider(ai_settings), question,
                    current_history, pending_answer['changes'])
        if finish_request(st.session_state, token, answer):
            turn = {'question': question, 'original_question': st.session_state.get('last_user_question', question),
                    'fingerprint': question_fingerprint, 'result': answer,
                    'analysis_fingerprint': analysis_fingerprint,
                    'analysis_changed': bool(pending_answer['changes']),
                    'applied_changes': pending_answer['changes'],
                    'summary': tile_summary(answer, pending_answer['changes']),
                    'order': len(st.session_state['question_history']) + 1,
                    'evidence': deepcopy(question_evidence), 'automatic': False,
                    'reused': False}
            st.session_state['question_answer'] = turn
            st.session_state['question_history'].append(turn)
            st.session_state['active_question'] = question


    with apply_ai_slot:
        st.button('Apply changes', key='apply_ai_weights', width='stretch',
                  disabled=st.session_state.get('manual_refresh_mode') != 'apply',
                  on_click=apply_refresh, args=(st.session_state,))

    def render_turn(turn):
        if turn.get('analysis_changed'):
            st.caption('Analysis updated')
            st.markdown('**What changed**\n' + '\n'.join('- ' + line for line in change_lines(turn['applied_changes'])))
        if turn_is_stale(turn):
            st.caption('Historical answer based on earlier analytical settings.')
            st.caption('Saved answer from earlier evidence')
            context = turn.get('evidence', {})
            if context:
                st.caption(context['scenario'] + ' · ' + ', '.join(context['candidate_states']))
                st.caption('Saved weights: ' + ', '.join(f'{name}: {weight}%' for name, weight in context.get('priority_weights_pct', {}).items()))
        elif turn['result']['status'] == 'ok':
            st.markdown('**AI-generated answer**')
        if turn['result']['status'] == 'ok':
            try:
                st.markdown(render_answer_markdown(turn['result'].get('structured_answer')))
            except ValueError:
                st.info('Saved answer format is unavailable. Ask again for an updated answer.')
        else:
            st.info(turn['result']['message'])


    saved_answer = st.session_state.get('question_answer')
    latest_is_stale = bool(saved_answer and turn_is_stale(saved_answer))
    refresh_status = st.session_state.get('ai_refresh', {}).get('status', 'idle')
    def refresh_notice():
        if refresh_status == 'failed':
            st.info('AI analysis could not be updated. Your analytical dashboard remains available.')
        if latest_is_stale:
            st.info('This answer reflects an earlier analytical configuration. Submit a question for an updated interpretation.')
    with insights_overview_slot:
        st.html('<div id="ai-insights"></div>')
        st.subheader('AI insights')
        if saved_answer and not latest_is_stale:
            structured = saved_answer['result'].get('structured_answer')
            if saved_answer['result']['status'] == 'ok' and structured:
                try:
                    # Use the existing validator before presenting individual sections.
                    render_answer_markdown(structured)
                except ValueError:
                    st.info('Saved answer format is unavailable. Ask again for an updated answer.')
                else:
                    st.markdown(structured['headline'])
                    for index, section in enumerate(structured['sections']):
                        with st.expander(section['heading'], expanded=index == 0, key=f'insight_section_{index}'):
                            st.markdown('\n'.join('- ' + bullet for bullet in section['bullets']))
                    st.caption('AI-generated answer · review against the supplied evidence.')
            else:
                render_turn(saved_answer)
        elif saved_answer:
            refresh_notice()
            st.caption('Prior answers remain in conversation history.')
        else:
            st.caption('No AI answer has been generated for this session.')
            st.write('Ask about a county, its strengths, or the trade-offs behind your shortlist.')
        if refresh_status == 'failed' and st.session_state['view_mode'] == 'dashboard':
            st.button('Retry analysis', key='retry_insights', on_click=retry_refresh, args=(st.session_state,))
        st.button('Ask a follow-up', key='insights_ask', icon=':material/arrow_forward:',
                  on_click=switch_view, args=('ask',))

    if st.session_state['view_mode'] == 'ask':
        with answer_slot:
            if saved_answer:
                with st.container(key='latest_answer'):
                    st.subheader('Latest answer')
                    if latest_is_stale:
                        refresh_notice()
                    with st.expander(saved_answer['question'], expanded=True, key=f"latest_response_{saved_answer.get('order', 0)}"):
                        render_turn(saved_answer)
                    if refresh_status == 'failed':
                        st.button('Retry analysis', key='retry_analysis', on_click=retry_refresh, args=(st.session_state,))
        with history_slot:
            for turn in reversed(st.session_state['question_history'][:-1]):
                stale = turn_is_stale(turn)
                summary = turn.get('summary') or tile_summary(turn['result'], turn.get('applied_changes', {}))
                indicator = ' • Analysis updated' if turn.get('analysis_changed') else ''
                if stale:
                    indicator += ' • Analysis changed since answer'
                label = 'Historical · ' + turn['question'] + ' — ' + summary + indicator
                with st.expander(label, expanded=False, key=f"response_{turn.get('order', st.session_state['question_history'].index(turn))}"):
                    context = turn.get('evidence', {})
                    if context:
                        st.caption(context['scenario'] + ' · ' + ', '.join(context['candidate_states']))
                    render_turn(turn)

    if st.session_state['view_mode'] == 'dashboard':
        with st.expander('Overall summary', expanded=False, key='overall_summary_panel'):
            evidence = evidence_for_question('')
            fingerprint = evidence_fingerprint(evidence)
            saved_interpretation = st.session_state.get('location_interpretation')
            explicit_summary = st.button('Generate overall summary', key='overall_summary')
            needs_summary = bool(summary_refresh_requested and saved_interpretation)
            if explicit_summary or needs_summary:
                try:
                    ai_settings = {name: st.secrets.get(name) for name in
                                   ('AI_PROVIDER', 'OPENAI_API_KEY', 'OPENAI_MODEL') if name in st.secrets}
                except StreamlitSecretNotFoundError:
                    ai_settings = {}
                token = begin_request(st.session_state, '__overall_summary__', fingerprint)
                prior = st.session_state.setdefault('location_interpretation_history', [])
                with st.spinner('Updating analysis for your selected settings...' if needs_summary else 'Interpreting supplied evidence...'):
                    interpretation = generate_interpretation(evidence, configured_provider(ai_settings))
                if finish_request(st.session_state, token, interpretation):
                    if saved_interpretation:
                        prior.append(deepcopy(saved_interpretation))
                    st.session_state['location_interpretation'] = {
                        'fingerprint': fingerprint, 'result': interpretation, 'evidence': deepcopy(evidence)}
            elif summary_refresh_requested:
                st.session_state.pop('manual_refresh_mode', None)
            saved_interpretation = st.session_state.get('location_interpretation')
            if saved_interpretation:
                if saved_interpretation['fingerprint'] != fingerprint:
                    st.caption('Historical interpretation based on earlier analytical settings. Generate overall summary to update it.')
                interpretation = saved_interpretation['result']
                if interpretation['status'] == 'ok':
                    st.markdown('**AI-generated interpretation**')
                    for key, heading in SECTIONS.items():
                        st.markdown('**' + heading + '**')
                        st.markdown(interpretation['sections'][key])
                    st.caption('Review against the supplied evidence; this is an illustrative screening interpretation.')
                else:
                    st.info(interpretation['message'])
                    st.button('Retry interpretation', key='retry_overall_summary',
                              on_click=retry_refresh, args=(st.session_state, 'summary'))
            for position, earlier in reversed(list(enumerate(st.session_state.get('location_interpretation_history', [])))):
                with st.expander('Historical interpretation ' + str(position + 1), expanded=False,
                                 key=f'overall_history_{position}'):
                    old_context = earlier.get('evidence', {})
                    if old_context:
                        st.caption(old_context['scenario'] + ' · ' + ', '.join(old_context['candidate_states']))
                    old_result = earlier['result']
                    if old_result['status'] == 'ok':
                        for key, heading in SECTIONS.items():
                            st.markdown('**' + heading + '**')
                            st.markdown(old_result['sections'][key])
                    else:
                        st.info(old_result['message'])

    with st.expander('Data coverage & methodology', key='methodology_panel'):
        st.subheader('Data coverage')
        st.caption(f'{len(ranked)} of {len(view)} counties in the current selection have complete scoring data; {len(view) - len(ranked)} remain unranked.')
        st.caption('2024 private-sector warehousing/storage (NAICS 493) labor records, counted by labor_status.')
        coverage = view.groupby(['state', 'labor_status']).size().unstack(fill_value=0)
        coverage = coverage.reindex(columns=['Available', 'Suppressed by BLS', 'No matching published BLS row'], fill_value=0)
        coverage = coverage.rename(columns={'Suppressed by BLS': 'Suppressed', 'No matching published BLS row': 'Unpublished'})
        coverage['Total counties'] = coverage.sum(axis=1)
        coverage = coverage.rename_axis('State').reset_index()
        themed_dataframe(coverage, hide_index=True, width='stretch', key='data_coverage')
        st.caption('Unpublished means no matching published BLS row. Suppressed and missing labor figures remain unavailable; incomplete counties remain gray and searchable.')
        st.subheader('Sources and limitations')
        st.write('2024 Census population and representative points; 2024 private-sector QCEW NAICS 493 annual employment and average pay; 2024 EIA state commercial electricity prices.')
        st.write('Reach counts U.S. county populations whose representative points fall within 250 straight-line miles. It is a coarse proxy; no road routing or carrier delivery promise is inferred. Border-area population outside the U.S. is excluded.')
        st.write('Average industry annual pay is not an hourly job-offer wage. Employment is existing workforce depth, not available jobseekers. State commercial electricity averages are not property tariffs. No rent, building availability, tax incentives, freight quotes, or property flood assessment is included.')
        st.write('Each factor uses percentile rank among the fixed complete five-state candidate set. Lower costs get higher component scores. Incomplete candidates are not scored. Small employment bases can produce unstable comparisons; investigate the underlying records.')
        st.caption('Ask Where Next explains supplied evidence. FEMA hazard context remains separate from screening scores.')
        st.json(json.loads((ROOT / 'data/sources.json').read_text()))
    st.html('<div id="data-exports"></div>')
    st.download_button('Download current county results', view.to_csv(index=False),
                       file_name='where-next-results.csv', mime='text/csv')
