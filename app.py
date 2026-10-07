import json
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from core import ROOT, LABELS, PRESETS, load_data, score_counties, evidence_brief, annual_electricity_expense, weight_sensitivity
from weather import get_alerts, get_forecast
from fema import FIELDS as FEMA_FIELDS, NUMERIC_FIELDS as FEMA_NUMERIC_FIELDS, load_fema_context
from interpretation import (SECTIONS, build_evidence, evidence_fingerprint,
                            configured_provider, generate_interpretation, generate_answer)
from streamlit.errors import StreamlitSecretNotFoundError
from analysis_intent import STATES, parse_changes, change_lines, tile_summary
from question_weather import enrich_weather
from question_state import DEFAULT_SCENARIO, WEIGHT_KEYS, initialize_question_state, reset_for_new_question

initialize_question_state(st.session_state)


def submit_question(input_key):
    question = st.session_state.get(input_key, '').strip()
    if question:
        st.session_state['submitted_question'] = question
        st.session_state['pending_question'] = question
        st.session_state['experience_mode'] = 'analysis'
        st.session_state['view_mode'] = 'ask'


def use_suggestion():
    if st.session_state.get('suggested_question'):
        st.session_state['landing_question'] = st.session_state['suggested_question']


def start_new_question():
    reset_for_new_question(st.session_state)


st.set_page_config(page_title='Where Next | Warehouse Location Intelligence',
                   layout='centered' if st.session_state['experience_mode'] == 'landing' else 'wide')
if st.session_state['experience_mode'] == 'landing':
    st.space('large')
    st.title('Where Next?', text_alignment='center')
    st.markdown('Warehouse location intelligence using public data', text_alignment='center')
    st.space('medium')
    st.text_area('Your warehouse question', key='landing_question', height=150,
                 placeholder='Ask where your next warehouse should be...', label_visibility='collapsed')
    st.button('Ask Where Next', key='ask_where_next', type='primary', width='stretch',
              on_click=submit_question, args=('landing_question',))
    st.pills('Try a question', [
        'Where should I put a warehouse in the Northeast?',
        'Which counties balance reach and labor cost best?',
        'What are the strongest locations for a temperature-controlled facility?',
        'Which locations have the lowest long-term risk?',
        'Why does the current leader rank first?',
        'Which locations should I investigate further?',
    ], key='suggested_question', on_change=use_suggestion)
    st.stop()

def switch_view(mode):
    st.session_state['view_mode'] = mode


st.segmented_control('View', ['ask', 'dashboard'], key='view_mode',
                     format_func=lambda mode: 'Ask Where Next' if mode == 'ask' else 'Dashboard',
                     selection_mode='single', required=True, label_visibility='collapsed',
                     persist_state='session')
if st.session_state['view_mode'] == 'dashboard':
    st.button('← Ask Where Next', key='return_to_ask', on_click=switch_view, args=('ask',))
st.button('Start a new question', key='start_new_question', on_click=start_new_question)
answer_slot = st.container()
if st.session_state['view_mode'] == 'ask':
    st.subheader('Your question')
    if st.session_state['submitted_question']:
        st.text(st.session_state['submitted_question'])
    # Reserve answer above the input while computing current evidence later in the run.
    answer_slot = st.container()
    with st.container():
        st.chat_input('Ask a follow-up', key='followup_question',
                      on_submit=submit_question, args=('followup_question',))
history_slot = st.container()
st.title('Where Next?')
st.markdown('### Warehouse Location Intelligence')
st.write('Compare potential distribution locations using market reach, labor, workforce depth, electricity cost and operational context.')
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
    default_selection = score_counties(data, weights_before)
    default_selection = default_selection[default_selection.complete & default_selection.state.isin(states_before)]
    controls = {'scenario': preset_before, 'priority_weights': weights_before,
                'candidate_states': states_before,
                'selected_counties': st.session_state.get('chosen_counties', list(default_selection.head(3).fips))}
    with st.spinner('Reading your analysis preferences...'):
        changes = parse_changes(configured_provider(ai_settings), pending_question, controls, data)
    if 'scenario' in changes:
        st.session_state['scenario'] = changes['scenario']
    if 'priority_weights' in changes:
        for key, value in zip(WEIGHT_KEYS, changes['priority_weights']):
            st.session_state[key] = value
        st.session_state['weight_preset'] = changes.get('scenario', preset_before)
    for field, widget_key in [('candidate_states', 'candidate_states'), ('selected_counties', 'chosen_counties')]:
        if field in changes:
            st.session_state[widget_key] = changes[field]
    st.session_state['pending_answer'] = {'question': pending_question, 'changes': changes}
with st.sidebar:
    st.header('Business priorities')
    st.caption('Define the screening question, then explore the trade-offs.')
    st.subheader('Scenario')
    preset = st.selectbox('Scenario', list(PRESETS), label_visibility='collapsed', key='scenario', persist_state='session')
    st.caption('Presets are illustrative, not industry standards.')
    st.subheader('Candidate states')
    states = st.multiselect('Candidate states', STATES,
                            default=None if 'candidate_states' in st.session_state else list(STATES), label_visibility='collapsed',
                            key='candidate_states', persist_state='session')
    st.subheader('Business priority weights')
    if st.session_state.get('weight_preset') != preset:
        st.session_state['weight_preset'] = preset
        for key, default in zip(WEIGHT_KEYS, PRESETS[preset]):
            st.session_state[key] = int(default)

    weights = [
        st.slider(
            label, 0, 100, key=WEIGHT_KEYS[i],
            on_change=rebalance_priority_weights, args=(i,), persist_state='session'
        )
        for i, label in enumerate(LABELS)
    ]
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
if view.empty:
    if st.session_state.get('question_answer'):
        answer_slot.info('Your analysis has changed. Ask again for an updated answer.')
    if st.session_state.pop('pending_answer', None):
        answer_slot.info('Select at least one candidate state, then submit your question again.')
    st.warning('Select at least one candidate state.')
    st.stop()
ranked = view[view.complete]
leader = ranked.iloc[0] if not ranked.empty else None
metrics = st.columns(4, gap='medium', wrap=True)
metrics[0].metric('Counties evaluated', len(view), border=True)
metrics[1].metric('Complete scoring data', len(ranked), border=True)
with metrics[2].container(border=True):
    st.caption('Current #1 county')
    st.markdown(f"**{leader['county']}, {leader['state']}**" if leader is not None else '**Unavailable**')
metrics[3].metric('Current #1 screening score', f"{leader['score']:.1f} / 100" if leader is not None else 'Unavailable', border=True)
st.caption(f'{len(view) - len(ranked)} incomplete counties in the current selection remain unranked and searchable. Scores use the fixed complete five-state reference set before state filtering.')

map_column, summary_column = st.columns([3, 1.35], gap='large', wrap=True)
with map_column:
    with st.container(border=True):
        st.subheader('County screening map')
        map_view = st.selectbox('Map view', ['Warehouse screening score', 'FEMA risk context'],
                                key='map_view', persist_state='session')
        fig = go.Figure()
        fig.add_trace(go.Choroplethmap(
            geojson=geometry, locations=[f['id'] for f in geometry['features']], z=[0] * len(geometry['features']),
            colorscale=[[0, '#e6e8eb'], [1, '#e6e8eb']], showscale=False,
            marker_line_width=0.25, marker_line_color='#ffffff', hoverinfo='skip'))
        if map_view == 'Warehouse screening score' and not ranked.empty:
            fig.add_trace(go.Choroplethmap(
                geojson=geometry, locations=ranked.fips, z=ranked.score,
                text=ranked.county + ', ' + ranked.state, colorscale='Teal', zmin=0, zmax=100,
                customdata=ranked[['reach_250mi', 'employment', 'annual_pay', 'electricity_cents_kwh']].to_numpy(),
                marker_line_width=0.5, marker_line_color='#ffffff', colorbar_title='Score',
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
                    marker_line_width=0.5, marker_line_color='#ffffff',
                    colorbar_title='FEMA risk',
                    hovertemplate=('<b>%{text}</b><br>FEMA risk score: %{z:.1f}/100'
                                   '<br>FEMA rating: %{customdata[0]}<extra></extra>')))
                st.caption('FEMA community risk context · Higher means higher relative risk. Gray = unavailable or outside selected scope. Warehouse rankings remain unchanged.')
            else:
                st.info('FEMA risk context unavailable. Warehouse screening remains available.')
        fig.update_layout(
            map={'style': 'white-bg', 'center': {'lon': -98 if national else -77.8, 'lat': 39 if national else 40.2},
                 'zoom': 2.6 if national else 4.3},
            height=540, margin={'l': 0, 'r': 0, 't': 0, 'b': 0}, clickmode='event+select')
        st.plotly_chart(fig, width='stretch', key='county_map',
                        alt=('County screening scores with unranked counties in gray'
                             if map_view == 'Warehouse screening score'
                             else 'FEMA long-term county risk context with missing counties in gray'))
        if map_view == 'Warehouse screening score':
            st.caption('Census 2024 boundaries · Gray = unranked, unavailable, or outside selected scope. No commercial map token required.')
        else:
            st.caption('FEMA county context uses the existing Census 2024 map boundaries; this is not a property-level hazard map.')
with summary_column:
    with st.container(border=True):
        st.subheader('Current top five')
        st.caption('Highest screening scores in your selected states.')
        if ranked.empty:
            st.caption('No complete counties are available in this selection.')
        else:
            for position, (_, row) in enumerate(ranked.head(5).iterrows(), 1):
                st.markdown(f"**{position}. {row['county']}, {row['state']}**  \nScreening score · **{row['score']:.1f} / 100**")
        st.markdown('**Current priorities**')
        st.write(preset)
        for label, weight in zip(LABELS, normalized_weights):
            st.caption(f'{label} · **{weight:.2f}%**')
        st.caption('A shortlist for further investigation. Higher scores reflect the selected priorities.')

st.subheader('County comparison')
st.caption('Search any county in the selected states, including counties with incomplete labor data.')
labels = dict(zip(view.fips, view.county + ', ' + view.state))
chosen = st.multiselect('Choose up to three counties', list(labels),
                        default=None if 'chosen_counties' in st.session_state else list(ranked.head(3).fips),
                        format_func=lambda x: labels[x], max_selections=3, key='chosen_counties', persist_state='session')
if chosen:
    selected = all_scored.set_index('fips').loc[chosen].reset_index()
    with st.container(border=True):
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
        st.dataframe(comparison, hide_index=True, width='stretch', key='county_comparison',
                     column_config={'Score': st.column_config.NumberColumn(format='%.1f')})
        st.caption('Unavailable figures stay missing. Annual industry pay is not an hourly offer; electricity is a state average.')

    with st.expander('Illustrative annual electricity expense', expanded=True):
        annual_kwh = st.number_input('Annual electricity consumption (kWh)', min_value=0.0,
                                    value=None, step=1000.0, key='annual_kwh', persist_state='session')
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
            st.dataframe(expenses, hide_index=True, width='stretch',
                         column_config={'2024 state commercial average (cents/kWh)': st.column_config.NumberColumn(format='%.2f'),
                                        'Annual consumption (kWh)': st.column_config.NumberColumn(format='localized')})
    with st.expander('County evidence summaries'):
        for _, row in selected.iterrows():
            st.write(evidence_brief(row))
    with st.expander('Long-term hazard context', expanded=True):
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
            st.dataframe(hazard_table.fillna('Unavailable'), hide_index=True, width='stretch',
                         alt='FEMA overall risk, annual loss, flood, winter weather, and hurricane context for selected counties')
            st.caption(f"FEMA NRI · {fema_metadata['version']} · retrieved {fema_metadata['retrieved_utc']} · source data updated {fema_metadata['source_data_updated_utc']}")
            st.caption(f"FIPS coverage: {fema_metadata['matched']} matched; {fema_metadata['unmatched']} unmatched; {len(fema_metadata['duplicate_fips'])} duplicate FIPS. Missing values remain unavailable; FEMA applicability ratings are preserved.")
            st.caption('Expected annual loss is a county aggregate including buildings, agriculture, and monetized population losses; it is not a warehouse loss estimate. Scores are relative indices, not damage probabilities.')
            st.markdown('[FEMA National Risk Index county source](' + fema_metadata['source_url'] + ')')
    with st.expander('Operational context · NWS alerts', expanded=True):
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
                if result['status'] == 'ok':
                    st.caption('Checked UTC: ' + result['checked_utc'] + ' · cached for up to 15 minutes')
                    if result['alerts']:
                        st.dataframe(result['alerts'], hide_index=True)
                    else:
                        st.success('NWS returned no active alerts for this point at the checked time.')
                else:
                    st.warning('Weather unavailable. This does not mean there are no alerts.')
                st.markdown('[NWS source query](' + result['url'] + ')')
            with st.container(border=True):
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
                        st.dataframe([
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
    factor = st.selectbox('Business priority to test', LABELS, key='sensitivity_factor', persist_state='session')
scenarios = weight_sensitivity(data, weights, LABELS.index(factor), states)
if st.session_state['view_mode'] == 'dashboard':
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
            st.dataframe(top, hide_index=True, width='stretch',
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
        factor, scenarios, scored=all_scored, ranked=ranked, question=question)


pending_answer = st.session_state.pop('pending_answer', None)
if pending_answer:
    # Rank first, resolve the updated target, enrich weather, then rebuild evidence.
    target_evidence = evidence_for_question(pending_answer['question'])
    with answer_slot:
        with st.spinner('Checking operational weather for your question...'):
            enrich_weather(pending_answer['question'], target_evidence['question_context'], data,
                           st.session_state.setdefault('interpretation_weather', {}),
                           cached_weather, cached_forecast)
question_evidence = evidence_for_question(st.session_state['submitted_question'])
question_fingerprint = evidence_fingerprint(question_evidence)
analysis_fingerprint = evidence_fingerprint(evidence_for_question(''))


def turn_is_stale(turn):
    # Compare each historical question with its own freshly rebuilt target context.
    return turn['fingerprint'] != evidence_fingerprint(evidence_for_question(turn['question']))


if pending_answer:
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
    with answer_slot:
        with st.spinner('Answering from updated supplied evidence...'):
            answer = generate_answer(question_evidence, configured_provider(ai_settings),
                                     pending_answer['question'], current_history, pending_answer['changes'])
    turn = {'question': pending_answer['question'], 'fingerprint': question_fingerprint,
            'result': answer, 'analysis_fingerprint': analysis_fingerprint,
            'analysis_changed': bool(pending_answer['changes']),
            'applied_changes': pending_answer['changes'],
            'summary': tile_summary(answer, pending_answer['changes']),
            'order': len(st.session_state['question_history']) + 1}
    st.session_state['question_answer'] = turn
    st.session_state['question_history'].append(turn)


def render_turn(turn):
    if turn.get('analysis_changed'):
        st.caption('Analysis updated')
        st.markdown('**What changed**\n' + '\n'.join('- ' + line for line in change_lines(turn['applied_changes'])))
    if turn_is_stale(turn):
        st.info('Your analysis has changed. Ask again for an updated answer.')
        st.caption('Saved answer from earlier evidence')
    elif turn['result']['status'] == 'ok':
        st.markdown('**AI-generated answer**')
    if turn['result']['status'] == 'ok':
        st.markdown(turn['result']['answer'])
    else:
        st.info(turn['result']['message'])


saved_answer = st.session_state.get('question_answer')
if st.session_state['view_mode'] == 'ask':
    with answer_slot:
        if saved_answer:
            with st.container(border=True, key='latest_answer'):
                st.subheader('Latest answer')
                with st.expander(saved_answer['question'], expanded=True, key=f"latest_response_{saved_answer.get('order', 0)}"):
                    render_turn(saved_answer)
                st.button('Open full dashboard →', key='open_dashboard', on_click=switch_view, args=('dashboard',))
    with history_slot:
        for turn in reversed(st.session_state['question_history'][:-1]):
            stale = turn_is_stale(turn)
            summary = turn.get('summary') or tile_summary(turn['result'], turn.get('applied_changes', {}))
            indicator = ' • Analysis updated' if turn.get('analysis_changed') else ''
            if stale:
                indicator += ' • Analysis changed since answer'
            label = turn['question'] + ' — ' + summary + indicator
            with st.expander(label, expanded=False, key=f"response_{turn.get('order', st.session_state['question_history'].index(turn))}"):
                render_turn(turn)

if st.session_state['view_mode'] == 'dashboard':
    with st.expander('Overall summary', expanded=False):
        evidence = evidence_for_question('')
        fingerprint = evidence_fingerprint(evidence)
        if st.button('Generate overall summary', key='overall_summary'):
            try:
                ai_settings = {name: st.secrets.get(name) for name in
                               ('AI_PROVIDER', 'OPENAI_API_KEY', 'OPENAI_MODEL') if name in st.secrets}
            except StreamlitSecretNotFoundError:
                ai_settings = {}
            with st.spinner('Interpreting supplied evidence…'):
                interpretation = generate_interpretation(evidence, configured_provider(ai_settings))
            st.session_state['location_interpretation'] = {
                'fingerprint': fingerprint, 'result': interpretation}
        saved_interpretation = st.session_state.get('location_interpretation')
        if saved_interpretation:
            if saved_interpretation['fingerprint'] != fingerprint:
                st.caption('Evidence changed. Click Generate overall summary for an updated interpretation.')
            else:
                interpretation = saved_interpretation['result']
                if interpretation['status'] == 'ok':
                    st.markdown('**AI-generated interpretation**')
                    for key, heading in SECTIONS.items():
                        st.markdown('**' + heading + '**')
                        st.markdown(interpretation['sections'][key])
                    st.caption('Review against the supplied evidence; this is an illustrative screening interpretation.')
                else:
                    st.info(interpretation['message'])

with st.expander('Data coverage & methodology'):
    st.subheader('Data coverage')
    st.caption(f'{len(ranked)} of {len(view)} counties in the current selection have complete scoring data; {len(view) - len(ranked)} remain unranked.')
    st.caption('2024 private-sector warehousing/storage (NAICS 493) labor records, counted by labor_status.')
    coverage = view.groupby(['state', 'labor_status']).size().unstack(fill_value=0)
    coverage = coverage.reindex(columns=['Available', 'Suppressed by BLS', 'No matching published BLS row'], fill_value=0)
    coverage = coverage.rename(columns={'Suppressed by BLS': 'Suppressed', 'No matching published BLS row': 'Unpublished'})
    coverage['Total counties'] = coverage.sum(axis=1)
    coverage = coverage.rename_axis('State').reset_index()
    st.dataframe(coverage, hide_index=True, width='stretch', key='data_coverage')
    st.caption('Unpublished means no matching published BLS row. Suppressed and missing labor figures remain unavailable; incomplete counties remain gray and searchable.')
    st.subheader('Sources and limitations')
    st.write('2024 Census population and representative points; 2024 private-sector QCEW NAICS 493 annual employment and average pay; 2024 EIA state commercial electricity prices.')
    st.write('Reach counts U.S. county populations whose representative points fall within 250 straight-line miles. It is a coarse proxy; no road routing or carrier delivery promise is inferred. Border-area population outside the U.S. is excluded.')
    st.write('Average industry annual pay is not an hourly job-offer wage. Employment is existing workforce depth, not available jobseekers. State commercial electricity averages are not property tariffs. No rent, building availability, tax incentives, freight quotes, or property flood assessment is included.')
    st.write('Each factor uses percentile rank among the fixed complete five-state candidate set. Lower costs get higher component scores. Incomplete candidates are not scored. Small employment bases can produce unstable comparisons; investigate the underlying records.')
    st.caption('Ask Where Next explains supplied evidence. FEMA hazard context remains separate from screening scores.')
    st.json(json.loads((ROOT / 'data/sources.json').read_text()))
st.download_button('Download current county results', view.to_csv(index=False),
                   file_name='where-next-results.csv', mime='text/csv')
