import json
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from core import ROOT, METRICS, LABELS, PRESETS, load_data, score_counties, evidence_brief, annual_electricity_expense
from weather import get_alerts

st.set_page_config(page_title='Where Next | Warehouse location screening', layout='wide')
st.title('Where Next?')
st.caption('Warehouse location screening · PA / NJ / NY / OH / MD · Reproducible 2024 baseline')
st.info('Working starter: real public data and deterministic scoring. AI and FEMA hazard layers are extension steps, not implemented claims.')

@st.cache_data
def read_data():
    return load_data()

@st.cache_data(ttl=900)
def cached_weather(lat, lon):
    return get_alerts(lat, lon)

data, geometry = read_data()
with st.sidebar:
    st.header('Business priorities')
    preset = st.selectbox('Scenario', list(PRESETS))
    weights = [st.slider(label, 0, 100, int(default), key=f'{preset}_{i}') for i,(label,default) in enumerate(zip(LABELS,PRESETS[preset]))]
    if sum(weights) == 0:
        st.warning('Set at least one weight above zero.')
        st.stop()
    st.caption('Weights are normalized to 100%. Presets are illustrative, not industry standards.')
    states = st.multiselect('Candidate states', ['MD','NJ','NY','OH','PA'], default=['MD','NJ','NY','OH','PA'])
    national = st.checkbox('Show contiguous U.S. overview', value=False)
    st.caption('Outside the five-state scope: no score. National county outlines provide geographic context.')

all_scored = score_counties(data, weights)
view = all_scored[all_scored.state.isin(states)]
if view.empty:
    st.warning('Select at least one candidate state.')
    st.stop()
ranked = view[view.complete]
st.write(f'**{len(view)} counties shown · {len(ranked)} ranked · {len(view)-len(ranked)} incomplete**')
st.caption('Incomplete counties stay gray. Scores use the same complete five-state reference set before any state filter.')

fig = go.Figure()
fig.add_trace(go.Choroplethmap(geojson=geometry, locations=[f['id'] for f in geometry['features']], z=[0]*len(geometry['features']),
    colorscale=[[0,'#e6e8eb'],[1,'#e6e8eb']], showscale=False, marker_line_width=0.25, marker_line_color='#ffffff', hoverinfo='skip'))
if not ranked.empty:
    fig.add_trace(go.Choroplethmap(geojson=geometry, locations=ranked.fips, z=ranked.score,
        text=ranked.county+', '+ranked.state, colorscale='Teal', zmin=0, zmax=100,
        marker_line_width=0.5, marker_line_color='#ffffff', colorbar_title='Score',
        hovertemplate='%{text}<br>Screening score: %{z:.1f}/100<extra></extra>'))
fig.update_layout(map={'style':'white-bg','center':{'lon':-98 if national else -77.8,'lat':39 if national else 40.2},'zoom':2.6 if national else 4.3},
    height=490,margin={'l':0,'r':0,'t':0,'b':0},clickmode='event+select')
st.plotly_chart(fig, width='stretch', key='county_map')
st.caption('Map: U.S. Census 2024 boundaries. Gray = unranked, unavailable, or outside selected scope. No commercial map token required.')

st.subheader('Data coverage')
st.caption('2024 private-sector warehousing/storage (NAICS 493) labor records for the selected states, counted by labor status.')
coverage = view.groupby(['state', 'labor_status']).size().unstack(fill_value=0)
coverage = coverage.reindex(columns=['Available', 'Suppressed by BLS', 'No matching published BLS row'], fill_value=0)
coverage = coverage.rename(columns={'Suppressed by BLS': 'Suppressed', 'No matching published BLS row': 'Unpublished'})
coverage['Total counties'] = coverage.sum(axis=1)
coverage = coverage.rename_axis('State').reset_index()
st.dataframe(coverage, hide_index=True, width='stretch', key='data_coverage')
st.caption('Unpublished means no matching published BLS row. Suppressed and missing labor figures remain unavailable; incomplete counties remain gray and can be searched and selected below.')

st.subheader('Inspect and compare')
labels = dict(zip(view.fips,view.county+', '+view.state))
chosen = st.multiselect('Choose up to three counties', list(labels), default=list(ranked.head(3).fips), format_func=lambda x:labels[x],max_selections=3)
annual_kwh = st.number_input('Annual electricity consumption (kWh)', min_value=0.0, value=None, step=1000.0, key='annual_kwh')
if chosen:
    selected = all_scored.set_index('fips').loc[chosen].reset_index()
    table = selected[['county','state','score','reach_250mi','annual_pay','employment','electricity_cents_kwh','labor_status']].copy()
    st.dataframe(table,hide_index=True,width='stretch')
    st.write('**Illustrative annual electricity expense**')
    st.caption('Annual kWh × electricity price in cents/kWh ÷ 100. Uses the 2024 state commercial average, not an actual property tariff or site quote. This expense does not change screening scores.')
    if annual_kwh is None:
        st.caption('Enter annual electricity consumption to calculate an illustrative expense for each selected county.')
    else:
        expenses = selected[['county', 'state', 'electricity_cents_kwh']].copy()
        expenses['Annual consumption (kWh)'] = annual_kwh
        expenses['Illustrative annual expense (USD)'] = annual_electricity_expense(annual_kwh, expenses['electricity_cents_kwh']).round(2)
        expenses = expenses.rename(columns={'county': 'County', 'state': 'State', 'electricity_cents_kwh': '2024 state commercial average (cents/kWh)'})
        st.dataframe(expenses, hide_index=True, width='stretch')
    for _,row in selected.iterrows():
        st.write(evidence_brief(row))
    current = st.selectbox('Weather at county representative point',chosen,format_func=lambda x:labels[x])
    row = data.set_index('fips').loc[current]
    if st.button('Check NWS alerts'):
        result = cached_weather(float(row.lat),float(row.lon))
        if result['status']=='ok':
            st.caption('Checked UTC: '+result['checked_utc']+' · cached for up to 15 minutes')
            if result['alerts']:
                st.dataframe(result['alerts'],hide_index=True)
            else:
                st.success('NWS returned no active alerts for this point at the checked time.')
        else:
            st.warning('Weather unavailable. This does not mean there are no alerts.')
        st.markdown('[NWS source query]('+result['url']+')')
    st.caption('A point query does not cover every part of a county or a transport route. Weather does not change the investment score.')

st.subheader('Scenario sensitivity')
scenario_rows = []
for name, w in PRESETS.items():
    frame = score_counties(data,w)
    frame = frame[frame.state.isin(states)&frame.complete].head(3)
    for position,(_,r) in enumerate(frame.iterrows(),1):
        scenario_rows.append({'Scenario':name,'Rank':position,'County':r['county']+', '+r['state'],'Score':round(r['score'],1)})
st.dataframe(scenario_rows, hide_index=True, width='stretch')

with st.expander('Methodology, source dates, and limitations'):
    st.write('2024 Census population and representative points; 2024 private-sector QCEW NAICS 493 annual employment and average pay; 2024 EIA state commercial electricity prices.')
    st.write('Reach counts U.S. county populations whose representative points fall within 250 straight-line miles. It is a coarse proxy; no road routing or carrier delivery promise is inferred. Border-area population outside the U.S. is excluded.')
    st.write('Average industry annual pay is not an hourly job-offer wage. Employment is existing workforce depth, not available jobseekers. State commercial electricity averages are not property tariffs. No rent, building availability, tax incentives, freight quotes, or property flood assessment is included.')
    st.write('Each factor uses percentile rank among the fixed complete five-state candidate set. Lower costs get higher component scores. Incomplete candidates are not scored. Small employment bases can produce unstable comparisons; investigate the underlying records.')
    st.json(json.loads((ROOT/'data/sources.json').read_text()))
st.download_button('Download current county results',view.to_csv(index=False),file_name='where-next-results.csv',mime='text/csv')
