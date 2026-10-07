"""Intent validation, synchronized views, response tiles, and trigger-only requests."""
import io
import json

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from analysis_intent import validated_changes, normalize_weights, tile_summary
from core import LABELS, PRESETS, load_data, score_counties


ANSWER = "**What the model now shows**\n- **Current leader** ? early-stage county screening.\n\n**Watch-outs**\n- Rents and freight rates are unavailable."


def intent(**changes):
    return {'intent': 'update_analysis' if changes else 'question_only',
            'scenario': None, 'candidate_states': None, 'priority_weights': None,
            'selected_counties': None, 'explanation': 'Preferences', **changes}


def workflow(monkeypatch, parsed=None, parser_failure=False, answer_failure=False):
    calls = []
    def respond(request, timeout):
        body = json.loads(request.data)
        calls.append(body)
        parsing = body['text']['format']['name'] == 'analysis_intent'
        if (parsing and parser_failure) or (not parsing and answer_failure):
            raise TimeoutError('private-secret')
        value = (parsed if parsed is not None else intent()) if parsing else {'answer': ANSWER}
        return io.BytesIO(json.dumps({'status': 'completed', 'output': [
            {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}).encode())
    monkeypatch.setattr('urllib.request.urlopen', respond)
    return calls


def make_app():
    app = AppTest.from_file('../app.py', default_timeout=60)
    app.secrets['OPENAI_API_KEY'] = 'test-key'
    app.secrets['AI_PROVIDER'] = 'openai'
    return app.run()


def first(app, question='Why is the current leader first?'):
    app.text_area(key='landing_question').set_value(question)
    return app.button(key='ask_where_next').click().run()


def current_controls():
    return {'scenario': 'General merchandise', 'candidate_states': ['MD', 'NJ', 'NY', 'OH', 'PA'],
            'priority_weights': [40, 30, 20, 10], 'selected_counties': ['42069']}


@pytest.mark.parametrize('heading', ['**What the model now shows**', '### What the model now shows'])
def test_tile_summary_uses_answer_content_not_heading(heading):
    summary = tile_summary({'answer': heading + '\n- **Lackawanna County** remains #1.'}, {})
    assert summary == 'Lackawanna County remains #1.'
    assert len(summary) < 120


@pytest.mark.parametrize('patch', [
    {'candidate_states': ['CA']}, {'candidate_states': []}, {'candidate_states': ['PA', 'CA']},
    {'scenario': 'Invented'}, {'selected_counties': ['99999']},
    {'selected_counties': ['42069', '42077', '42095', '42001']},
    {'selected_counties': ['42069', '42069']},
    {'candidate_states': ['NJ'], 'selected_counties': ['42069']},
    {'priority_weights': {label: 0 for label in LABELS}},
    {'priority_weights': {label: float('nan') for label in LABELS}},
    {'priority_weights': {label: 101 for label in LABELS}},
    {'priority_weights': {'Market reach': 40}},
])
def test_invalid_intent_is_atomic(patch):
    data, _ = load_data()
    assert validated_changes(intent(**patch), current_controls(), data) == {}


def test_counties_weights_and_question_only_validation():
    data, _ = load_data()
    patch = validated_changes(intent(selected_counties=['42069', '42077', '42095']), current_controls(), data)
    assert patch['selected_counties'] == ['42069', '42077', '42095']
    assert normalize_weights([15, 35, 15, 15]) == [19, 44, 19, 18]
    assert validated_changes(intent(intent='question_only', candidate_states=['PA']), current_controls(), data) == {}


@pytest.mark.parametrize('question,parsed,expected', [
    ('Only compare Pennsylvania and New Jersey.', intent(candidate_states=['PA', 'NJ']), {'candidate_states': ['NJ', 'PA']}),
    ('Switch to temperature-controlled.', intent(scenario='Temperature-controlled'), {'scenario': 'Temperature-controlled'}),
    ('Put much more emphasis on labor cost.', intent(priority_weights=dict(zip(LABELS, [20, 55, 15, 10]))),
     {'priority_weights': [20, 55, 15, 10]}),
    ('Compare Lackawanna, Lehigh and Northampton.', intent(selected_counties=['42069', '42077', '42095']),
     {'selected_counties': ['42069', '42077', '42095']}),
])
def test_updated_evidence_precedes_answer_and_dashboard(monkeypatch, question, parsed, expected):
    calls = workflow(monkeypatch, parsed)
    app = first(make_app(), question)
    assert not app.exception and len(calls) == 2
    assert [call['text']['format']['name'] for call in calls] == ['analysis_intent', 'location_interpretation']
    supplied = json.loads(calls[-1]['input'][0]['content'])
    metadata = json.loads(calls[-1]['input'][1]['content'])
    assert metadata['question'] == question and metadata['applied_changes']
    for key, value in expected.items():
        if key == 'priority_weights':
            assert list(supplied['priority_weights_pct'].values()) == value
            assert [app.slider(key=f'priority_weight_{i}').value for i in range(4)] == value
        elif key == 'selected_counties':
            assert [county['fips'] for county in supplied['selected_counties']] == value
        else:
            assert supplied[key] == value
    weights = list(supplied['priority_weights_pct'].values())
    assert sum(weights) == 100
    data, _ = load_data()
    scored = score_counties(data, weights)
    ranked = scored[scored.complete & scored.state.isin(supplied['candidate_states'])]
    assert supplied['current_leader']['fips'] == ranked.iloc[0].fips
    assert supplied['current_leader']['score'] == ranked.iloc[0].score
    assert app.metric[2].value == f"{ranked.iloc[0].score:.1f} / 100"
    assert any(caption.value == 'Analysis updated' for caption in app.caption)
    turn = app.session_state['question_history'][0]
    assert turn['analysis_changed'] and turn['applied_changes'] and len(turn['summary']) < 120
    app.button(key='open_dashboard').click().run()
    assert not app.exception and len(calls) == 2
    assert app.session_state['view_mode'] == 'dashboard'
    assert not any(header.value == 'Latest answer' for header in app.subheader)
    assert app.metric[2].value == f"{ranked.iloc[0].score:.1f} / 100"
    app.run()
    assert len(calls) == 2


def test_enter_tiles_history_and_view_switching(monkeypatch):
    calls = workflow(monkeypatch)
    app = first(make_app())
    assert app.session_state['view_mode'] == 'ask'
    assert len(calls) == 2
    latest = next(tile for tile in app.expander if tile.key == 'latest_response_1')
    assert latest.proto.expanded
    assert any(block.key == 'latest_answer' for block in app.get('flex_container'))
    assert any(markdown.value == ANSWER for markdown in app.markdown)
    assert not any(caption.value == 'Analysis updated' for caption in app.caption)
    app.chat_input(key='followup_question').set_value('What risks should I investigate?').run()
    assert not app.exception and len(calls) == 4
    assert len(app.session_state['question_history']) == 2
    older = next(tile for tile in app.expander if tile.key == 'response_1')
    assert not older.proto.expanded and 'Why is the current leader first?' in older.label
    latest = next(tile for tile in app.expander if tile.key == 'latest_response_2')
    assert latest.proto.expanded
    # AppTest cannot click native expander toggles; verify content is available
    # inside the collapsed tile. Browser validation covers opening/closing it.
    assert any(markdown.value == ANSWER for markdown in older.markdown)
    app.run()
    assert len(calls) == 4 and len(app.session_state['question_history']) == 2
    for turn in app.session_state['question_history']:
        assert 0 < len(turn['summary']) < 120 and not turn['analysis_changed']
    saved_history = list(app.session_state['question_history'])
    app.selectbox(key='weather_county').select(app.multiselect(key='chosen_counties').value[0]).run()
    app.session_state['interpretation_weather'] = {'42069': {'alerts': {'status': 'unavailable'}}}
    app.button(key='open_dashboard').click().run()
    assert app.session_state['view_mode'] == 'dashboard' and not app.chat_input
    assert app.session_state['question_history'] == saved_history
    app.slider(key='priority_weight_0').set_value(50).run()
    app.button(key='return_to_ask').click().run()
    assert not app.exception and app.session_state['view_mode'] == 'ask'
    assert app.slider(key='priority_weight_0').value == 50
    assert app.session_state['question_history'] == saved_history
    assert app.session_state['interpretation_weather']['42069']['alerts']['status'] == 'unavailable'
    assert any('Your analysis has changed' in text.value for text in app.info)
    assert len(calls) == 4
    app.chat_input(key='followup_question').set_value('   ').run()
    app.run()
    assert len(calls) == 4 and len(app.session_state['question_history']) == 2
    app.button(key='start_new_question').click().run()
    assert app.session_state['experience_mode'] == 'landing' and not app.metric


@pytest.mark.parametrize('failure', ['parser', 'answer', 'invalid'])
def test_failures_keep_dashboard_safe(monkeypatch, failure):
    calls = workflow(monkeypatch, intent(candidate_states=['CA']) if failure == 'invalid' else intent(candidate_states=['PA']),
                     parser_failure=failure == 'parser', answer_failure=failure == 'answer')
    app = first(make_app(), 'Only compare Pennsylvania.')
    assert not app.exception and len(calls) == 2 and app.metric
    assert app.multiselect(key='candidate_states').value == (['PA'] if failure == 'answer' else ['MD', 'NJ', 'NY', 'OH', 'PA'])
    assert not any('private-secret' in info.value for info in app.info)
    app.run()
    assert len(calls) == 2
