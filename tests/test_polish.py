"""Deterministic state overrides, strict answer structure, and scoped card styling."""
import json

import pytest

from analysis_intent import parse_changes
from core import LABELS, PRESETS, load_data, score_counties
from interpretation import generate_answer, render_answer_markdown
from question_targeting import explicit_screening_states, question_targets
from summary_cards import render_summary_card, summary_cards_html
from answer_fixtures import card_html, card_values
from test_targeting import mock_model
from test_analysis_workflow import first, make_app


@pytest.mark.parametrize('phrase,state,rank', [
    ('third best county in MD', 'MD', 3), ('third best county in Maryland', 'MD', 3),
    ('second best county in NJ', 'NJ', 2), ('second best county in New Jersey', 'NJ', 2),
    ('best county in Ohio', 'OH', 1), ('best county in OH', 'OH', 1),
    ('next best county in PA', 'PA', 2), ('next best county in Pennsylvania', 'PA', 2),
    ('third best county in NY', 'NY', 3), ('third best county in New York', 'NY', 3),
    ('best county in NY', 'NY', 1), ('best county in New York', 'NY', 1),
])
def test_explicit_scope_precedes_ordinal_even_without_model(phrase, state, rank):
    data, _ = load_data()
    controls = dict(scenario='General merchandise', candidate_states=['PA'],
                    priority_weights=PRESETS['General merchandise'], selected_counties=[])
    assert explicit_screening_states(phrase) == [state]
    patch = parse_changes(None, phrase, controls, data)
    states = patch.get('candidate_states', controls['candidate_states'])
    scored = score_counties(data, controls['priority_weights'])
    ranked = scored[scored.complete & scored.state.isin(states)]
    context = question_targets(phrase, scored, ranked, ranked.head(3), states)
    assert context['fips'] == [ranked.iloc[rank - 1].fips]
    assert ranked.iloc[rank - 1].state == state
    assert explicit_screening_states('What is number three?') is None
    assert explicit_screening_states('What risks affect Middlesex County, NJ?') is None


def test_pa_to_md_cards_map_answer_followup_and_comparison(monkeypatch):
    # Intentionally stale model intent cannot override the explicit state constraint.
    calls = mock_model(monkeypatch, {'candidate_states': ['PA']})
    app = first(make_app(), 'Best county in PA')
    app.chat_input(key='followup_question').set_value('Which is the third best county in MD?').run()
    assert not app.exception and app.session_state['candidate_states'] == ['MD']
    scored = score_counties(load_data()[0], PRESETS['General merchandise'])
    ranked = scored[scored.complete & scored.state.eq('MD')]
    target = ranked.iloc[2]
    assert app.session_state['highlighted_fips'] == target.fips
    assert 'Current #3 county' in card_html(app)
    assert card_values(app)[0] == f'{target.county}, MD'
    supplied = json.loads(calls[-1]['input'][0]['content'])
    assert supplied['question_target_counties'][0]['fips'] == target.fips
    assert any(target.county in item.value and '- ' in item.value for item in app.markdown)
    chart = next(item for item in app.get('plotly_chart') if item.key == 'county_map')
    marker = json.loads(chart.proto.spec)['data'][-1]
    assert marker['type'] == 'scattermap' and marker['lat'] == [target.lat] and marker['lon'] == [target.lon]
    calls = mock_model(monkeypatch)
    app.chat_input(key='followup_question').set_value('Why is it number three?').run()
    assert app.session_state['candidate_states'] == ['MD']
    assert app.session_state['highlighted_fips'] == target.fips
    app.chat_input(key='followup_question').set_value('What are the trade-offs compared with number one?').run()
    assert app.session_state['highlighted_fips'] == target.fips
    context = json.loads(calls[-1]['input'][0]['content'])['question_context']
    assert context['fips'] == [target.fips, ranked.iloc[0].fips]
    latest = app.session_state['question_answer']['result']
    assert latest['structured_answer']['sections']
    assert '- ' in latest['answer'] and '**' in latest['answer']
    older = next(tile for tile in app.expander if tile.key == 'response_2')
    assert any(target.county in item.value and '- ' in item.value for item in older.markdown)


VALID = {'headline': '**Maryland county** → current #3', 'sections': [
    {'heading': 'Why it ranks here', 'bullets': ['**Employment** → workforce depth.']},
    {'heading': 'Trade-offs', 'bullets': ['Investigate property availability.']}]}


@pytest.mark.parametrize('invalid', [
    {'answer': 'One long paragraph.'}, {'headline': 'Title', 'sections': []},
    {'headline': 'Title', 'sections': [{'heading': 'Why', 'bullets': ['Fact']}]},
    {**VALID, 'extra': 'unexpected'},
    {**VALID, 'sections': [VALID['sections'][0], {'heading': 'Why', 'bullets': ['word ' * 61]}]},
    {**VALID, 'sections': [VALID['sections'][0], {'heading': 'Why', 'bullets': ['One. Two. Three.']}]},
    {**VALID, 'sections': [VALID['sections'][0], {'heading': 'Why', 'bullets': ['First\nSecond']}]},
])
def test_malformed_or_prose_output_fails_safely(invalid):
    class Provider:
        model = 'mock'
        def explain(self, *args, **kwargs): return invalid
    result = generate_answer({}, Provider(), 'Why?')
    assert result['status'] == 'unavailable' and 'answer' not in result


def test_markdown_renderer_and_reusable_cards():
    assert render_answer_markdown(VALID) == (
        '**Maryland county → current #3**\n\n**Why it ranks here**\n- **Employment** → workforce depth.'
        '\n\n**Trade-offs**\n- Investigate property availability.')
    cards = [('Current #3 county', 'County, MD', 'Screening score: 80.0 / 100'),
             ('Warehousing employment', '6,346', None), ('Average annual pay', 'Unavailable', None),
             ('Electricity benchmark', '11.03 ¢/kWh', '2024 state commercial electricity benchmark')]
    markup = summary_cards_html(cards)
    assert markup.count('<article class="wn-summary-card">') == 4
    assert all(render_summary_card(*card) in markup for card in cards)
    assert '11.03 ¢/kWh' in markup and '...' not in markup and 'ellipsis' not in markup
    assert 'height:210px' in markup and 'padding:20px' in markup and '@media' in markup
    assert 'backdrop-filter' in markup and '@supports' in markup
    assert '&lt;script&gt;' in render_summary_card('<script>', 'x')
