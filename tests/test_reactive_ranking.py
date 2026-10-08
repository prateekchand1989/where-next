"""Live controls share one current ranking without model requests or stale headlines."""
import json

import pandas as pd
import pytest

import core
from analysis_intent import STATES
from answer_fixtures import card_html, card_values
from core import LABELS, PRESETS, load_data, score_counties, weight_sensitivity
from test_analysis_workflow import first, make_app
from test_targeting import mock_model


def assert_current_panels(app):
    assert not app.exception
    weights = [app.slider(key=f'priority_weight_{i}').value for i in range(4)]
    states = app.multiselect(key='candidate_states').value
    assert sum(weights) == 100
    scored = score_counties(load_data()[0], weights)
    ranked = scored[scored.complete & scored.state.isin(states)]
    leader = ranked.iloc[0]
    assert app.session_state['highlighted_fips'] == leader.fips
    assert app.session_state['highlighted_rank'] == 1
    assert 'Current #1 county' in card_html(app)
    assert card_values(app) == [f'{leader.county}, {leader.state}', f'{leader.employment:,.0f}',
                               f'${leader.annual_pay:,.0f}', f'{leader.electricity_cents_kwh:.2f} ¢/kWh']
    top_five = [item.value for item in app.markdown if item.value.startswith('**1. ') or
                any(item.value.startswith(f'**{rank}. ') for rank in range(2, 6))]
    assert top_five == [f"**{rank}. {row.county}, {row.state}**  \nScreening score · **{row.score:.1f} / 100**"
                        for rank, (_, row) in enumerate(ranked.head(5).iterrows(), 1)]
    chart = next(item for item in app.get('plotly_chart') if item.key == 'county_map')
    traces = json.loads(chart.proto.spec)['data']
    screening = next(trace for trace in traces if trace.get('colorbar', {}).get('title', {}).get('text') == 'Score')
    assert screening['locations'] == list(ranked.fips)
    marker = traces[-1]
    assert marker['text'] == [f'{leader.county}, {leader.state}']
    comparison = app.multiselect(key='chosen_counties').value
    assert comparison == list(ranked.head(3).fips)
    frame = next(item.value for item in app.dataframe if 'County' in item.value and 'Score' in item.value)
    # Comparisons format the exact same scored rows, without independent rescoring.
    assert frame['Score'].tolist() == list(ranked.head(3).score)
    return ranked


def test_live_weights_states_presets_and_no_ai_calls(monkeypatch):
    calls = mock_model(monkeypatch)
    app = first(make_app(), 'What is number three?')
    assert app.session_state['highlighted_rank'] == 3 and len(calls) == 2
    app.slider(key='priority_weight_3').set_value(82).run()
    assert app.slider(key='priority_weight_3').value == 82
    assert_current_panels(app)
    app.slider(key='priority_weight_0').set_value(100).run()
    assert [app.slider(key=f'priority_weight_{i}').value for i in range(4)] == [100, 0, 0, 0]
    assert_current_panels(app)
    app.multiselect(key='candidate_states').set_value([state for state in STATES if state != 'OH']).run()
    assert 'OH' not in set(assert_current_panels(app).head(5).state)
    app.multiselect(key='candidate_states').set_value(['PA', 'MD']).run()
    assert set(assert_current_panels(app).state) <= {'PA', 'MD'}
    app.multiselect(key='candidate_states').set_value(STATES).run()
    assert_current_panels(app)
    for preset in reversed(list(PRESETS)):
        app.selectbox(key='scenario').select(preset).run()
        assert [app.slider(key=f'priority_weight_{i}').value for i in range(4)] == PRESETS[preset]
        assert_current_panels(app)
        app.slider(key='priority_weight_1').set_value(73).run()
        assert_current_panels(app)
        adjusted = [app.slider(key=f'priority_weight_{i}').value for i in range(4)]
        app.run()
        assert [app.slider(key=f'priority_weight_{i}').value for i in range(4)] == adjusted
        assert_current_panels(app)
    assert len(calls) == 2
    # Only an explicit question requests AI; its evidence uses the live controls.
    app.chat_input(key='followup_question').set_value('What is the best county?').run()
    ranked = assert_current_panels(app)
    supplied = json.loads(calls[-1]['input'][0]['content'])
    assert supplied['current_leader']['fips'] == ranked.iloc[0].fips
    assert [county['fips'] for county in supplied['current_top_five']] == list(ranked.head(5).fips)
    assert supplied['current_top_five'][0]['score'] == ranked.iloc[0].score


def test_one_current_score_pass_plus_two_sensitivity_alternatives(monkeypatch):
    actual_score = core.score_counties
    scoring_calls = []
    def counted(data, weights):
        scoring_calls.append(list(weights))
        return actual_score(data, weights)
    monkeypatch.setattr(core, 'score_counties', counted)
    calls = mock_model(monkeypatch)
    app = first(make_app())
    assert not app.exception and len(scoring_calls) == 3
    scoring_calls.clear()
    app.slider(key='priority_weight_3').set_value(82).run()
    assert not app.exception and len(scoring_calls) == 3
    assert scoring_calls[0] == [app.slider(key=f'priority_weight_{i}').value for i in range(4)]
    assert len(calls) == 2


def test_no_complete_counties_clears_stale_highlight(monkeypatch):
    data, geometry = load_data()
    # Offline test double only; bundled datasets are untouched.
    data.loc[data.state.eq('MD'), 'annual_pay'] = float('nan')
    monkeypatch.setattr(core, 'load_data', lambda: (data, geometry))
    import streamlit as st
    st.cache_data.clear()
    calls = mock_model(monkeypatch)
    app = first(make_app())
    app.multiselect(key='candidate_states').set_value(['MD']).run()
    assert not app.exception and len(calls) == 2
    assert app.session_state['highlighted_fips'] is None
    assert app.session_state['highlighted_rank'] is None
    assert card_values(app) == ['Unavailable'] * 4
    assert any('No counties with complete scoring data' in item.value for item in app.warning)
    assert any('No complete counties' in item.value for item in app.caption)
    chart = next(item for item in app.get('plotly_chart') if item.key == 'county_map')
    assert not any(trace.get('name') == 'Highlighted county' for trace in json.loads(chart.proto.spec)['data'])
    app.multiselect(key='candidate_states').set_value([]).run()
    assert app.session_state['highlighted_fips'] is None
    assert any('Select at least one candidate state' in item.value for item in app.warning)
    st.cache_data.clear()


def test_reused_sensitivity_baseline_matches_original():
    data, _ = load_data()
    weights = [8, 6, 4, 82]
    scored = score_counties(data, weights)
    before = scored.copy(deep=True)
    original = weight_sensitivity(data, weights, 3, ['PA', 'MD'])
    reused = weight_sensitivity(data, weights, 3, ['PA', 'MD'], current_scored=scored)
    for left, right in zip(original, reused):
        assert left['weights'] == right['weights']
        pd.testing.assert_frame_equal(left['top_five'], right['top_five'])
        pd.testing.assert_frame_equal(left['top_three_changes'], right['top_three_changes'])
    pd.testing.assert_frame_equal(scored, before)
