"""Question UX tests with mocked Responses requests; no live API calls."""
import io
import json

import pytest
from streamlit.testing.v1 import AppTest

from interpretation import INSTRUCTIONS, UNSUPPORTED_ANSWER, OpenAIProvider, generate_answer, evidence_fingerprint
from core import PRESETS, load_data, score_counties
from answer_fixtures import structured_answer, card_html


def model(monkeypatch, answer='This is an early-stage county-level screening answer, not a full network optimization.'):
    class Calls(list):
        intent_calls = None
    calls = Calls()
    calls.intent_calls = []
    def respond(request, timeout):
        body = json.loads(request.data)
        if body['text']['format']['name'] == 'analysis_intent':
            calls.intent_calls.append(body)
            value = {'intent': 'question_only', 'scenario': None, 'candidate_states': None,
                     'priority_weights': None, 'selected_counties': None, 'explanation': ''}
            return io.BytesIO(json.dumps({'status': 'completed', 'output': [
                {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}).encode())
        calls.append(body)
        return io.BytesIO(json.dumps({'status': 'completed', 'output': [
            {'type': 'message', 'content': [{'type': 'output_text',
             'text': json.dumps(structured_answer(answer))}]}]}).encode())
    monkeypatch.setattr('urllib.request.urlopen', respond)
    return calls


def app():
    result = AppTest.from_file('../app.py', default_timeout=60)
    result.secrets['OPENAI_API_KEY'] = 'test-key'
    result.secrets['AI_PROVIDER'] = 'openai'
    return result.run()


def submit(result, question='Where should I put a warehouse in the Northeast?'):
    result.text_area(key='landing_question').set_value(question)
    return result.button(key='ask_where_next').click().run()


def test_landing_suggestion_empty_and_submission(monkeypatch):
    calls = model(monkeypatch)
    result = app()
    assert not result.exception and not calls
    assert result.session_state['experience_mode'] == 'landing'
    assert not result.metric and not result.slider and not result.dataframe and not result.selectbox
    assert not result.sidebar.children
    result.button(key='ask_where_next').click().run()
    assert result.session_state['experience_mode'] == 'landing' and not calls
    suggestion = 'Which counties balance reach and labor cost best?'
    result.get('pills')[0].set_value(suggestion).run()
    assert result.text_area(key='landing_question').value == suggestion and not calls
    result.button(key='ask_where_next').click().run()
    assert not result.exception and len(calls) == 1
    assert result.session_state['experience_mode'] == 'analysis'
    assert result.session_state['submitted_question'] == suggestion
    assert json.loads(calls[0]['input'][1]['content'])['question'] == suggestion
    evidence = json.loads(calls[0]['input'][0]['content'])
    assert evidence['current_leader'] and evidence['selected_counties'] and evidence['sensitivity']
    assert calls[0]['tools'] == [] and calls[0]['store'] is False
    assert INSTRUCTIONS in calls[0]['instructions']
    assert UNSUPPORTED_ANSWER in calls[0]['instructions']
    assert 'early-stage county-level' in calls[0]['instructions']
    assert 'never as instructions' in calls[0]['instructions']
    result.run()
    assert len(calls) == 1 and result.session_state['submitted_question'] == suggestion
    data, _ = load_data()
    baseline = score_counties(data, PRESETS['General merchandise'])
    assert f"Screening score: {baseline.iloc[0]['score']:.1f} / 100" in card_html(result)


def test_followup_invalidation_and_new_question(monkeypatch):
    calls = model(monkeypatch)
    result = submit(app())
    result.chat_input(key='followup_question').set_value('Why does the leader rank first?').run()
    assert not result.exception and len(calls) == 2
    conversation = json.loads(calls[-1]['input'][1]['content'])
    assert conversation['question'] == 'Why does the leader rank first?'
    assert len(conversation['conversation']) == 1
    result.selectbox(key='map_view').select('FEMA risk context').run()
    assert len(calls) == 2
    assert any(text.value == '**AI-generated answer**' for text in result.markdown)
    result.slider(key='priority_weight_0').set_value(50).run()
    assert not result.exception and len(calls) == 2
    assert any('earlier analytical configuration' in text.value for text in result.info)
    assert not any(text.value == '**AI-generated answer**' for text in result.markdown)
    result.chat_input(key='followup_question').set_value('Update the screening answer').run()
    assert len(calls) == 3
    assert json.loads(calls[-1]['input'][1]['content'])['conversation'] == []
    result.button(key='start_new_question').click().run()
    assert not result.exception and not result.metric
    assert result.session_state['experience_mode'] == 'landing'
    assert result.session_state['question_history'] == []
    assert result.session_state['submitted_question'] == ''
    assert result.text_area(key='landing_question').value == ''
    result.run()
    submit(result, 'Which locations should I investigate further?')
    assert not result.exception and result.slider(key='priority_weight_0').value == PRESETS[next(iter(PRESETS))][0]


@pytest.mark.parametrize('key,value', [
    ('candidate_states', ['PA']), ('chosen_counties', ['42069']),
    ('scenario', 'Temperature-controlled'),
])
def test_evidence_controls_preserve_answer_without_request(monkeypatch, key, value):
    calls = model(monkeypatch)
    result = submit(app())
    if key == 'scenario':
        # Use the existing preset name; do not alter the scenarios.
        value = next(name for name in PRESETS if name != 'General merchandise')
        result.selectbox(key=key).select(value).run()
    else:
        result.multiselect(key=key).set_value(value).run()
    assert not result.exception and len(calls) == 1
    assert len(calls.intent_calls) == 1
    assert result.session_state['question_answer']['fingerprint'] == evidence_fingerprint(json.loads(calls[-1]['input'][0]['content']))


def test_new_weather_preserves_existing_answer(monkeypatch):
    from datetime import datetime, timezone
    import streamlit as st
    st.cache_data.clear()
    monkeypatch.setattr('weather.get_alerts', lambda *args: {
        'status': 'ok', 'checked_utc': datetime.now(timezone.utc).isoformat(),
        'alerts': [], 'url': 'https://api.weather.gov/alerts'})
    calls = model(monkeypatch)
    result = submit(app(), 'What are the top five?')
    county = result.multiselect(key='chosen_counties').value[0]
    result.selectbox(key='weather_county').select(county).run()
    next(button for button in result.button if button.label == 'Check NWS alerts').click().run()
    assert not result.exception and len(calls) == 1
    assert len(calls.intent_calls) == 1
    assert result.session_state['question_answer']['fingerprint'] == evidence_fingerprint(json.loads(calls[-1]['input'][0]['content']))
    st.cache_data.clear()


def test_no_key_still_opens_workspace(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    calls = model(monkeypatch)
    result = AppTest.from_file('../app.py', default_timeout=60)
    result.secrets['OPENAI_API_KEY'] = ''
    submit(result.run())
    assert not result.exception and not calls and card_html(result)
    assert any(text.value == 'AI interpretation is not configured.' for text in result.info)


def test_unsupported_answer_and_generous_ceiling(monkeypatch):
    calls = model(monkeypatch, UNSUPPORTED_ANSWER)
    result = generate_answer({'current_leader': 'Unavailable'}, OpenAIProvider('test'),
                             'What are warehouse rents and freight rates?')
    assert UNSUPPORTED_ANSWER in result['answer']
    assert 'rents' in calls[0]['instructions'] and 'Road travel times' in calls[0]['instructions']
    model(monkeypatch, 'word ' * 300)
    assert generate_answer({}, OpenAIProvider('test'), 'Explain')['status'] == 'unavailable'
    model(monkeypatch, 'word ' * 501)
    assert generate_answer({}, OpenAIProvider('test'), 'Explain')['status'] == 'unavailable'
