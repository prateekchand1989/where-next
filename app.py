import json
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from core import ROOT, LABELS, PRESETS, load_data, score_counties, evidence_brief, annual_electricity_expense, weight_sensitivity
from weather import get_alerts, get_forecast
from fema import FIELDS as FEMA_FIELDS, NUMERIC_FIELDS as FEMA_NUMERIC_FIELDS, load_fema_context

st.set_page_config(page_title='Where Next | Warehouse Location Intelligence', layout='wide')
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


WEIGHT_KEYS = [f'priority_weight_{i}' for i in range(4)]


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
with st.sidebar:
    st.header('Business priorities')
    st.caption('Define the screening question, then explore the trade-offs.')
    st.subheader('Scenario')
    preset = st.selectbox('Scenario', list(PRESETS), label_visibility='collapsed')
    st.caption('Presets are illustrative, not industry standards.')
    st.subheader('Candidate states')
    states = st.multiselect('Candidate states', ['MD', 'NJ', 'NY', 'OH', 'PA'],
                            default=['MD', 'NJ', 'NY', 'OH', 'PA'], label_visibility='collapsed')
    st.subheader('Business priority weights')
    if st.session_state.get('weight_preset') != preset:
        st.session_state['weight_preset'] = preset
        for key, default in zip(WEIGHT_KEYS, PRESETS[preset]):
            st.session_state[key] = int(default)

    weights = [
        st.slider(
            label, 0, 100, key=WEIGHT_KEYS[i],
            on_change=rebalance_priority_weights, args=(i,)
        )
        for i, label in enumerate(LABELS)
    ]
    st.caption('Move any slider and the other three rebalance automatically so the total remains 100%.')
    st.caption(f"Current total: **{sum(weights)}%**")
    normalized_weights = np.asarray(weights, dtype=float)
    for label, weight in zip(LABELS, normalized_weights):
        st.caption(f'{label}: **{weight:.0f}%**')
    st.subheader('Map settings')
    national = st.checkbox('Show contiguous U.S. overview', value=False)
    st.caption('Outside the five-state scope: no score. National outlines provide geographic context.')

all_scored = score_counties(data, weights)
view = all_scored[all_scored.state.isin(states)]
if view.empty:
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
                                key='map_view')
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
chosen = st.multiselect('Choose up to three counties', list(labels), default=list(ranked.head(3).fips),
                        format_func=lambda x: labels[x], max_selections=3)
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
                                    value=None, step=1000.0, key='annual_kwh')
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
        current = st.selectbox('Weather at county representative point', chosen, format_func=lambda x: labels[x])
        row = data.set_index('fips').loc[current]
        if st.button('Check NWS alerts'):
            result = cached_weather(float(row.lat), float(row.lon))
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

st.subheader('Scenario sensitivity')
st.caption('See how a single priority changes the shortlist, starting from your current weights.')
factor = st.selectbox('Scoring factor to test', LABELS, key='sensitivity_factor')
scenarios = weight_sensitivity(data, weights, LABELS.index(factor), states)
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
    st.caption('AI interpretation is not implemented. FEMA hazard context is presented separately from screening scores.')
    st.json(json.loads((ROOT / 'data/sources.json').read_text()))
st.download_button('Download current county results', view.to_csv(index=False),
                   file_name='where-next-results.csv', mime='text/csv')
