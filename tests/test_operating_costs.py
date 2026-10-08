"""Cost arithmetic, research coverage, and separation from screening/AI."""
from dataclasses import replace
import json

import pandas as pd
import pytest

from core import PRESETS, load_data, score_counties
from operating_costs import CostAssumptions, estimate_operating_cost, lease_benchmark, load_lease_data
from answer_fixtures import card_values
from test_analysis_workflow import first, make_app
from test_targeting import mock_model


COUNTY = {'annual_pay': 41600.0, 'electricity_cents_kwh': 12.0}
ASSUMPTIONS = CostAssumptions(10000, 20800, 25, 100000, 2)
BENCHMARK = {'asking_rent_psf_year': 8, 'rent_basis': 'Net asking; NNN detail not specified'}


def test_annual_components_and_total():
    result = estimate_operating_cost(COUNTY, BENCHMARK, ASSUMPTIONS)
    assert result['hourly_labor'] == 20
    assert result['components'] == {'Facility rent': 80000, 'Workforce': 520000,
                                     'Electricity': 12000, 'Other occupancy': 20000}
    assert result['total_annual'] == 632000
    assert result['annual_psf'] == 63.2


@pytest.mark.parametrize('field,value', [('facility_sqft', None), ('facility_sqft', 0),
    ('labor_hours', None), ('labor_burden_pct', None), ('annual_kwh', None),
    ('other_occupancy_psf', None), ('annual_kwh', float('nan')), ('labor_hours', -1)])
def test_missing_invalid_assumptions_prevent_complete_estimate(field, value):
    result = estimate_operating_cost(COUNTY, BENCHMARK, replace(ASSUMPTIONS, **{field: value}))
    assert result['annual_psf'] is None and result['total_annual'] is None and result['missing']


@pytest.mark.parametrize('field', ['annual_pay', 'electricity_cents_kwh'])
@pytest.mark.parametrize('value', [None, float('nan'), 0])
def test_missing_benchmarks_not_zero(field, value):
    assert estimate_operating_cost({**COUNTY, field: value}, BENCHMARK, ASSUMPTIONS)['annual_psf'] is None


def test_explicit_zero_usage_is_valid_but_missing_rent_and_incompatible_basis_are_not():
    result = estimate_operating_cost(COUNTY, BENCHMARK, CostAssumptions(10000, 0, 0, 0, 0))
    assert result['annual_psf'] == 8 and result['total_annual'] == 80000
    for benchmark in [None, {**BENCHMARK, 'rent_basis': 'Gross'}, {**BENCHMARK, 'asking_rent_psf_year': None}]:
        result = estimate_operating_cost(COUNTY, benchmark, ASSUMPTIONS)
        assert result['components']['Facility rent'] is None and result['total_annual'] is None


def test_scenario_specific_researched_coverage_and_provenance():
    dataset = load_lease_data()
    county_data = load_data()[0]
    covered_states = set()
    for obs in dataset['observations']:
        for fips in obs['county_fips']:
            county = county_data[county_data.fips.eq(fips)].iloc[0]
            covered_states.add(county.state)
            benchmark = lease_benchmark(fips, 'General merchandise')
            assert benchmark['county_value_kind'] == 'modeled estimate'
            assert benchmark['observation_kind'] == 'observed benchmark'
            assert benchmark['asking_rent_psf_year'] > 0
            for key in ['market', 'warehouse_type', 'rent_basis', 'source_organization',
                        'original_url', 'publication_period', 'retrieval_date', 'geographic_coverage',
                        'county_confidence', 'mapping_rule']:
                assert benchmark[key]
            assert lease_benchmark(fips, 'Temperature-controlled') is None
    assert covered_states == {'PA', 'NJ', 'NY', 'OH', 'MD'}
    assert lease_benchmark('42069', 'General merchandise')['asking_rent_psf_year'] == 7.61
    assert lease_benchmark('42095', 'General merchandise')['asking_rent_psf_year'] == 11.67
    assert lease_benchmark('36061', 'General merchandise') is None  # No NY statewide fallback.
    assert lease_benchmark('42069', 'unknown') is None


def test_separate_types_accept_distinct_verified_rates_without_automatic_markup():
    dataset = {'sources': {'verified': {'rent_basis': BENCHMARK['rent_basis']}}, 'observations': [
        {'warehouse_type': scenario, 'county_fips': ['42069'], 'source_id': 'verified',
         'asking_rent_psf_year': rate, 'mapping_confidence': 'medium'}
        for scenario, rate in [('General merchandise', 8), ('Temperature-controlled', 15)]]}
    rates = [lease_benchmark('42069', scenario, dataset)['asking_rent_psf_year'] for scenario in PRESETS]
    assert rates == [8, 15]  # Synthetic fixtures, never published as research data.


def expected_leader_cost(app):
    weights = [app.slider(key=f'priority_weight_{i}').value for i in range(4)]
    scored = score_counties(load_data()[0], weights)
    ranked = scored[scored.complete & scored.state.isin(app.multiselect(key='candidate_states').value)]
    row = ranked.iloc[0]
    a = CostAssumptions(*(app.number_input(key=key).value for key in
                         ['cost_sqft', 'cost_labor_hours', 'cost_burden', 'cost_kwh', 'cost_other_psf']))
    result = estimate_operating_cost(row, lease_benchmark(row.fips, app.selectbox(key='scenario').value), a)
    expected = 'Unavailable' if result['annual_psf'] is None else f"${result['annual_psf']:,.2f} / sq ft / year"
    assert card_values(app)[4] == expected
    table = next(frame.value for frame in app.dataframe if 'Cost county' in frame.value)
    assert table['Cost county'].tolist() == [f'{r.county}, {r.state}' for _, r in ranked.head(5).iterrows()]
    if not table.empty:
        assert table.iloc[0]['Annual cost / sq ft'] == ('Unavailable' if result['annual_psf'] is None else f"${result['annual_psf']:,.2f}")
    assert not app.exception
    return ranked


def test_live_leader_assumptions_scenarios_defaults_and_no_ai(monkeypatch):
    calls = mock_model(monkeypatch)
    app = first(make_app(), 'Best county in PA')
    assert len(card_values(app)) == 5
    baseline_ranked = expected_leader_cost(app)
    baseline_answer = app.session_state['question_answer']
    initial_cards = card_values(app)[:4]
    for key, value in [('cost_sqft', 250000), ('cost_labor_hours', 208000),
                       ('cost_burden', 40), ('cost_kwh', 500000), ('cost_other_psf', 4)]:
        app.number_input(key=key).set_value(value).run()
        pd.testing.assert_frame_equal(expected_leader_cost(app), baseline_ranked)
        assert card_values(app)[:4] == initial_cards
        assert app.session_state['question_answer'] == baseline_answer
    app.button(key='open_dashboard').click().run()
    expected_leader_cost(app)
    app.slider(key='priority_weight_0').set_value(100).run()
    expected_leader_cost(app)
    app.multiselect(key='candidate_states').set_value(['NJ']).run()
    expected_leader_cost(app)
    for scenario in PRESETS:
        app.selectbox(key='scenario').select(scenario).run()
        expected_leader_cost(app)
        app.slider(key='priority_weight_3').set_value(82).run()
        app.button(key='default_weights').click().run()
        assert [app.slider(key=f'priority_weight_{i}').value for i in range(4)] == PRESETS[scenario]
        expected_leader_cost(app)
    assert card_values(app)[4] == 'Unavailable'  # Refrigerated rate intentionally absent.
    app.button(key='return_to_ask').click().run()
    assert app.number_input(key='cost_sqft').value == 250000
    assert len(calls) == 2  # Ordinary cost, slider, state, reset and navigation interactions make no calls.


def test_cost_follows_leader_even_when_ai_highlights_third_county(monkeypatch):
    mock_model(monkeypatch)
    app = first(make_app(), 'What is number three in PA?')
    assert app.session_state['highlighted_rank'] == 3
    ranked = expected_leader_cost(app)
    assert card_values(app)[0] == f'{ranked.iloc[2].county}, PA'
    assert any(f"Current #1 county** → **{ranked.iloc[0].county}" in item.value for item in app.markdown)
