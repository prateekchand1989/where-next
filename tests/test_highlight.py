"""County presentation state follows existing scores and current scope."""
import json

import numpy as np
import pandas as pd
import pytest

from core import PRESETS, load_data, score_counties, county_hover_rows
from question_state import reset_for_new_question, sync_county_state
from question_targeting import question_targets
from test_targeting import mock_model
from test_analysis_workflow import first, make_app
from test_question_flow import model
from interpretation import ANSWER_STYLE, INSTRUCTIONS
from answer_fixtures import card_values, card_html, expected_answer


@pytest.fixture
def scored():
    return score_counties(load_data()[0], PRESETS[next(iter(PRESETS))])


def test_county_hover_rows_keep_existing_values_and_missing_flags():
    rows = pd.DataFrame([
        {'county': 'Montgomery', 'state': 'PA', 'employment': 12450, 'annual_pay': 52800, 'electricity_cents_kwh': 11.4, 'score': 84.2},
        {'county': 'Lehigh', 'state': 'PA', 'employment': 0, 'annual_pay': 0, 'electricity_cents_kwh': np.nan, 'score': 66.7},
        {'county': 'Allegheny', 'state': 'PA', 'employment': np.nan, 'annual_pay': 21000, 'electricity_cents_kwh': 8.1, 'score': np.nan},
    ])
    hover = county_hover_rows(rows)
    assert hover.iloc[0].to_dict() == {
        'county_label': 'Montgomery, PA',
        'employment': '12,450',
        'annual_pay': '$52,800',
        'electricity_cents_kwh': '11.40 ¢/kWh',
        'score': '84.2 / 100',
    }
    assert hover.iloc[1].to_dict() == {
        'county_label': 'Lehigh, PA',
        'employment': '0',
        'annual_pay': '$0',
        'electricity_cents_kwh': 'Data unavailable',
        'score': '66.7 / 100',
    }
    assert hover.iloc[2].to_dict() == {
        'county_label': 'Allegheny, PA',
        'employment': 'Data unavailable',
        'annual_pay': '$21,000',
        'electricity_cents_kwh': '8.10 ¢/kWh',
        'score': 'Data unavailable',
    }


@pytest.mark.parametrize('question,rank', [
    ('next best county', 2), ('second-best county', 2), ('number two', 2), ('#2', 2),
    ('third-best county', 3), ('number three', 3), ('#3', 3),
    ('fourth-best county', 4), ('fifth-best county', 5), ('What is the best county?', 1),
])
def test_ordinals_resolve_current_python_ranking(scored, question, rank):
    ranked = scored[scored.complete & scored.state.eq('PA')]
    before = scored.copy(deep=True)
    context = question_targets(question, scored, ranked, ranked.head(3), ['PA'])
    assert context['fips'] == [ranked.iloc[rank - 1].fips]
    assert scored.equals(before)
    state = {}
    sync_county_state(state, scored, ranked, ['PA'], question)
    assert state['highlighted_fips'] == ranked.iloc[rank - 1].fips
    assert state['highlighted_rank'] == rank


def test_auto_scope_manual_fill_neutral_highlight_and_reset(scored):
    pa = scored[scored.complete & scored.state.eq('PA')]
    nj = scored[scored.complete & scored.state.eq('NJ')]
    both = scored[scored.complete & scored.state.isin(['PA', 'NJ'])]
    state = {}
    sync_county_state(state, scored, pa, ['PA'])
    assert state['chosen_counties'] == list(pa.head(3).fips)
    sync_county_state(state, scored, nj, ['NJ'])
    assert state['chosen_counties'] == list(nj.head(3).fips)
    assert state['highlighted_fips'] == nj.iloc[0].fips and state['highlighted_rank'] == 1
    sync_county_state(state, scored, both, ['PA', 'NJ'])
    manual = ['34035', '34023', '42077']
    state.update(chosen_counties=manual, comparison_manual=True)
    sync_county_state(state, scored, nj, ['NJ'])
    expected = ['34035', '34023'] + [fips for fips in nj.fips if fips not in manual][:1]
    assert state['chosen_counties'] == expected
    sync_county_state(state, scored, nj, ['NJ'], 'Tell me about Northampton County')
    assert state['highlighted_fips'] == '42095' and state['highlighted_rank'] is None
    reset_for_new_question(state)
    assert 'highlighted_fips' not in state and 'comparison_manual' not in state
    full = scored[scored.complete]
    sync_county_state(state, scored, full, state['candidate_states'])
    assert state['highlighted_fips'] == full.iloc[0].fips
    small = nj.head(1)
    sync_county_state(state, scored, small, ['NJ'], '#3')
    assert state['highlighted_fips'] is None and state['highlighted_rank'] is None


def assert_cards(app, row, rank):
    assert app.session_state['highlighted_fips'] == row.fips
    assert app.session_state['highlighted_rank'] == rank
    assert card_values(app)[1:4] == [f'{row.employment:,.0f}', f'${row.annual_pay:,.0f}', f'{row.electricity_cents_kwh:.2f} ¢/kWh']
    assert f'Screening score: {row.score:.1f} / 100' in card_html(app)
    assert f'Current #{rank} county' in card_html(app)


def test_updated_scope_ordinal_cards_evidence_views_and_comparison(monkeypatch, scored):
    calls = mock_model(monkeypatch, {'candidate_states': ['PA']})
    app = first(make_app(), 'What is the next best county in Pennsylvania?')
    pa = scored[scored.complete & scored.state.eq('PA')]
    assert not app.exception
    assert_cards(app, pa.iloc[1], 2)
    supplied = json.loads(calls[-1]['input'][0]['content'])
    assert supplied['question_target_counties'][0]['fips'] == pa.iloc[1].fips
    assert supplied['question_context']['requested_rank'] == 2
    assert app.multiselect(key='chosen_counties').value == list(pa.head(3).fips)
    assert any('**What changed**' in item.value for item in app.markdown)
    app.button(key='nav_overview').click().run()
    assert_cards(app, pa.iloc[1], 2)
    app.button(key='nav_ask').click().run()
    assert len(calls) == 2
    calls = mock_model(monkeypatch)
    app.chat_input(key='followup_question').set_value('What is number three?').run()
    assert_cards(app, pa.iloc[2], 3)
    assert any(pa.iloc[2].county in item.value and '- ' in item.value for item in app.markdown)
    app.multiselect(key='candidate_states').set_value(['NJ']).run()
    nj = scored[scored.complete & scored.state.eq('NJ')]
    assert not app.exception and len(calls) == 2
    assert sum(c['text']['format']['name'] == 'analysis_intent' for c in calls) == 1
    assert_cards(app, nj.iloc[2], 3)
    assert app.multiselect(key='chosen_counties').value == list(nj.head(3).fips)
    app.multiselect(key='candidate_states').set_value(['NJ', 'PA']).run()
    app.multiselect(key='chosen_counties').set_value(['34035', '34023', '42077']).run()
    app.multiselect(key='candidate_states').set_value(['NJ']).run()
    assert app.multiselect(key='chosen_counties').value[:2] == ['34035', '34023']
    assert len(app.multiselect(key='chosen_counties').value) == 3
    assert all(fips.startswith('34') for fips in app.multiselect(key='chosen_counties').value)
    app.button(key='start_new_question').click().run()
    first(app, 'What is the best county?')
    assert_cards(app, scored[scored.complete].iloc[0], 1)


def test_named_incomplete_county_has_unavailable_cards(monkeypatch, scored):
    missing = scored[~scored.complete & scored.annual_pay.isna()].iloc[0]
    calls = mock_model(monkeypatch)
    app = first(make_app(), f'Tell me about {missing.county}, {missing.state}')
    assert not app.exception and app.session_state['highlighted_fips'] == missing.fips
    assert app.session_state['highlighted_rank'] is None
    assert card_values(app)[2] == 'Unavailable'
    assert 'Selected county' in card_html(app)
    assert 'Screening score: Unavailable' in card_html(app)
    assert json.loads(calls[-1]['input'][0]['content'])['question_context']['rank_by_fips'][missing.fips] == 'Unavailable'


def test_comparison_markdown_and_shared_format_instructions(monkeypatch):
    answer = '**Best fit**\n- **Somerset County** → market reach.\n\n**Key trade-offs**\n- **Middlesex County** → workforce depth.\n\n**What changes the decision**\n- Investigate property availability.'
    calls = model(monkeypatch, answer)
    app = first(make_app(), 'Compare these counties')
    assert not app.exception
    assert any(item.value == expected_answer(answer) for item in app.markdown)
    assert not any(item.value == expected_answer(answer) for item in app.text)
    app.chat_input(key='followup_question').set_value('Compare their risk trade-offs').run()
    assert len(calls) == 2
    assert all(ANSWER_STYLE in call['instructions'] for call in calls)
    assert all('100-200' in call['instructions'] and '120-220' in call['instructions'] for call in calls)
    assert 'Best fit' in ANSWER_STYLE and 'What changed' in ANSWER_STYLE
    assert '180-300' in INSTRUCTIONS and 'Markdown strings' in INSTRUCTIONS
    older = next(tile for tile in app.expander if tile.key == 'response_1')
    assert any(item.value == expected_answer(answer) for item in older.markdown)
