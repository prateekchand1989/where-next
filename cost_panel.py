"""Native, additive operating-cost controls and transparent comparison display."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from operating_costs import CostAssumptions, PAY_CONVERSION_HOURS, estimate_operating_cost, lease_benchmark, load_lease_data


def dollars(value):
    return 'Unavailable' if value is None else f'${value:,.2f}'


def render_cost_panel(ranked, scenario):
    with st.expander('Warehouse Operating Cost Model', expanded=False, key='operating_cost_panel'):
        st.caption('Illustrative inputs, shared across the Current Top Five. These costs do not change county rankings.')
        # Separate keys intentionally keep the existing electricity/AI workflow untouched.
        left, right = st.columns(2, wrap=True)
        with left:
            sqft = st.number_input('Facility size (sq ft)', min_value=1.0, value=100000.0,
                                   step=1000.0, key='cost_sqft', persist_state='session')
            hours = st.number_input('Expected annual paid labor hours', min_value=0.0, value=104000.0,
                                    step=2080.0, key='cost_labor_hours', persist_state='session',
                                    help='104,000 hours illustrates 50 employees × 2,080 paid hours/year.')
            burden = st.number_input('Labor burden (%)', min_value=0.0, value=25.0,
                                     step=1.0, key='cost_burden', persist_state='session')
        with right:
            kwh = st.number_input('Cost-model annual electricity (kWh)', min_value=0.0, value=1000000.0,
                                  step=1000.0, key='cost_kwh', persist_state='session')
            other = st.number_input('Other annual occupancy ($/sq ft)', min_value=0.0, value=3.0,
                                    step=0.25, key='cost_other_psf', persist_state='session',
                                    help='Include net-lease taxes, insurance, CAM and other occupancy charges; avoid double counting electricity.')
        assumptions = CostAssumptions(sqft, hours, burden, kwh, other)
        leader = ranked.iloc[0] if not ranked.empty else None
        benchmarks = [lease_benchmark(row.fips, scenario) for _, row in ranked.head(5).iterrows()]
        results = [estimate_operating_cost(row, benchmark, assumptions)
                   for (_, row), benchmark in zip(ranked.head(5).iterrows(), benchmarks)]
        current = results[0] if results else estimate_operating_cost(None, None, assumptions)
        st.markdown(f"**Current #1 county** → **{leader['county']}, {leader['state']}**" if leader is not None
                    else '**Current #1 county** → Unavailable')
        benchmark = benchmarks[0] if benchmarks else None
        if benchmark:
            st.markdown(f"**{scenario} rent benchmark** → **${benchmark['asking_rent_psf_year']:.2f} / sq ft / year**")
            st.caption(f"{benchmark['market']} · {benchmark['rent_basis']} · {benchmark['publication_period']} · "
                       f"County modeled estimate · {benchmark['county_confidence']} confidence")
            st.markdown(f"[Source: {benchmark['source_organization']} — page {benchmark['source_page']}]({benchmark['original_url']})")
            st.caption(benchmark['mapping_rule'])
        else:
            st.info(f'{scenario} rent benchmark unavailable for this county. No substitute rent or cold-storage markup is used.')
        st.markdown(f"**Estimated total annual operating cost** → **{dollars(current['total_annual'])}**")
        st.markdown(f"**Illustrative Annual Operating Cost / Sq Ft** → **{dollars(current['annual_psf'])}"
                    + (' / sq ft / year**' if current['annual_psf'] is not None else '**'))
        if current['missing']:
            st.caption('Complete estimate unavailable. Missing or invalid inputs/benchmarks: ' + ', '.join(current['missing']) + '.')
        if current['total_annual'] is not None:
            fig = go.Figure(go.Bar(x=list(current['components'].values()), y=list(current['components']),
                                  orientation='h', marker_color=['#103D35', '#147D69', '#6FA88B', '#A4C7B4'],
                                  hovertemplate='%{y}: $%{x:,.2f}<extra></extra>'))
            fig.update_layout(height=260, margin=dict(l=0, r=16, t=12, b=20),
                              paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                              xaxis_title='Annual USD', font_color='#20352F')
            st.plotly_chart(fig, key='operating_cost_breakdown', alt='Annual operating costs by rent, workforce, electricity, and other occupancy')
        # Even partial costs are shown as unavailable; never turn missing data into zero.
        st.dataframe(pd.DataFrame([
            {'Screening rank': i, 'Cost county': f'{row.county}, {row.state}',
             'Annual rent': dollars(result['components']['Facility rent']),
             'Annual workforce': dollars(result['components']['Workforce']),
             'Annual electricity': dollars(result['components']['Electricity']),
             'Other occupancy': dollars(result['components']['Other occupancy']),
             'Total annual cost': dollars(result['total_annual']),
             'Annual cost / sq ft': dollars(result['annual_psf']),
             'Rent market': bench['market'] if bench else 'Unavailable',
             'Status': 'Illustrative estimate' if not result['missing'] else 'Unavailable: ' + ', '.join(result['missing'])}
            for i, ((_, row), bench, result) in enumerate(zip(ranked.head(5).iterrows(), benchmarks, results), 1)
        ]), hide_index=True, alt='Operating costs for the Current Top Five, in screening rank order')
        with st.expander('Cost sources and assumptions', key='cost_sources'):
            st.markdown(f'- Hourly labor proxy → existing **2024 BLS annual pay ÷ {PAY_CONVERSION_HOURS:,} hours** '
                        '(40 hours/week × 52 weeks). This is not an observed hourly wage.\n'
                        '- Workforce → paid hours × hourly proxy × (1 + burden / 100).\n'
                        '- Rent → square footage × annual asking rent. Electricity → kWh × existing state cents/kWh ÷ 100.\n'
                        '- Other occupancy → square footage × your annual occupancy assumption.\n'
                        '- Defaults are illustrative inputs, not measured facility requirements. They stay constant across scenarios; '
                        'adjust electricity and staffing for refrigeration.\n'
                        '- Net asking benchmarks share a broad lease basis. Exact NNN obligations, concessions and included charges '
                        'are not verified; reconcile property quotes and occupancy expenses before making a decision. '
                        'Gross or modified-gross rents are not combined with these benchmarks.\n'
                        '- This is not complete landed distribution cost: transportation, handling, inventory carrying, '
                        'fit-out and refrigeration equipment may be excluded.')
            st.caption('Fixed Q2 2025 rent snapshot, retrieved 2026-10-07; no escalation or current-rent forecast. '
                       'Rent, labor and electricity observation periods differ. Unmapped counties remain unavailable.')
            source_data = load_lease_data()
            for key, source in source_data['sources'].items():
                st.markdown(f"[{source['source_organization']} — {key.upper()} — {source['publication_period']}]({source['original_url']})")
            st.caption(source_data['temperature_controlled']['reason'])
            st.markdown('[Reviewed cold-storage research: CBRE](https://www.cbre.com/insights/reports/midwest-cold-storage-trends-2025)')
            mapped = [{**bench, 'County': f'{row.county}, {row.state}'}
                      for (_, row), bench in zip(ranked.head(5).iterrows(), benchmarks) if bench]
            if mapped:
                st.dataframe(pd.DataFrame(mapped)[['County', 'market', 'warehouse_type', 'asking_rent_psf_year',
                    'rent_basis', 'observation_kind', 'county_value_kind', 'county_confidence', 'geographic_coverage',
                    'source_organization', 'original_url', 'publication_period', 'retrieval_date']].rename(columns={
                        'market': 'Market', 'warehouse_type': 'Warehouse type',
                        'asking_rent_psf_year': 'Annual asking rent ($/sq ft)', 'rent_basis': 'Lease basis',
                        'observation_kind': 'Source figure', 'county_value_kind': 'County figure',
                        'county_confidence': 'Mapping confidence', 'geographic_coverage': 'Geographic coverage',
                        'source_organization': 'Source organization', 'original_url': 'Original source URL',
                        'publication_period': 'Publication period', 'retrieval_date': 'Retrieval date'}),
                    hide_index=True, alt='Source provenance and geographic mapping for available rent benchmarks')
    return current
