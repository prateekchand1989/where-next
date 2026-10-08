"""Explicit-question hazard/weather enrichment, freshness, targeting, and failures."""
import io
import json
from answer_fixtures import structured_answer, card_values
from datetime import datetime, timedelta, timezone

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from core import LABELS, PRESETS, load_data, score_counties
from fema import FIELDS, load_fema_context
from interpretation import INSTRUCTIONS
from question_weather import enrich_weather, weather_targets


def result(kind, now):
    common = {'status': 'ok', 'checked_utc': now.isoformat(), 'url': 'https://api.weather.gov/example'}
    if kind == 'alerts':
        return {**common, 'alerts': []}
    return {**common, 'updated': now.isoformat(), 'generated_at': now.isoformat(), 'periods': [
        {'name': 'Tonight', 'temperature': 40, 'temperatureUnit': 'F', 'shortForecast': 'Clear',
         'windSpeed': '5 mph', 'windDirection': 'NW'}]}


def test_fresh_session_weather_reused_and_stale_kinds_refreshed():
    now = datetime.now(timezone.utc)
    data, _ = load_data()
    session = {'34035': {'alerts': result('alerts', now),
                         'forecast': result('forecast', now - timedelta(minutes=16))}}
    calls = []
    def fetch(lat, lon):
        calls.append((lat, lon))
        return result('forecast', now)
    enrich_weather('What risks?', {'kind': 'current_leader', 'fips': ['34035']}, data, session,
                   lambda *args: pytest.fail('Fresh alerts must be reused'), fetch, now)
    assert len(calls) == 1
    enrich_weather('What risks?', {'kind': 'current_leader', 'fips': ['34035']}, data, session,
                   lambda *args: pytest.fail('Fresh alerts must be reused'),
                   lambda *args: pytest.fail('Fresh forecast must be reused'), now)


def test_stale_shared_cache_is_cleared_for_only_the_target():
    now = datetime.now(timezone.utc)
    calls, clears = [], []
    def fetch(lat, lon):
        calls.append((lat, lon))
        return result('alerts', now - timedelta(minutes=16) if len(calls) == 1 else now)
    fetch.clear = lambda *args: clears.append(args)
    session = {}
    enrich_weather('Risk?', {'kind': 'current_leader', 'fips': ['34035']}, load_data()[0], session,
                   fetch, lambda *args: result('forecast', now), now)
    assert len(calls) == 2 and clears == [calls[0]]
    assert session['34035']['alerts']['checked_utc'] == now.isoformat()


def test_weather_targets_are_conservative():
    context = {'kind': 'current_shortlist', 'fips': ['1', '2', '3', '4', '5']}
    assert weather_targets('What are the top five?', context) == []
    assert weather_targets('What weather risks affect the shortlist?', context) == context['fips']
    assert weather_targets('Compare these counties', {**context, 'kind': 'selected_comparison'}) == ['1','2','3']


def test_fresh_result_checked_after_fetch_is_not_mistaken_for_future_data():
    calls, clears = [], []
    def fetch(lat, lon):
        calls.append((lat, lon))
        return result('alerts', datetime.now(timezone.utc))
    fetch.clear = lambda *args: clears.append(args)
    enrich_weather('Risks?', {'kind':'current_leader', 'fips':['34035']}, load_data()[0], {},
                   fetch, lambda *args: result('forecast', datetime.now(timezone.utc)))
    assert len(calls) == 1 and not clears


@pytest.fixture
def mocked_weather(monkeypatch):
    st.cache_data.clear()
    calls = {'alerts': [], 'forecast': []}
    now = datetime.now(timezone.utc)
    for kind, name in [('alerts', 'get_alerts'), ('forecast', 'get_forecast')]:
        def fetch(lat, lon, kind=kind):
            calls[kind].append((lat, lon))
            return result(kind, now)
        monkeypatch.setattr('weather.' + name, fetch)
    yield calls
    st.cache_data.clear()


def model(monkeypatch, changes=None):
    calls = []
    def respond(request, timeout):
        body = json.loads(request.data); calls.append(body)
        if body['text']['format']['name'] == 'analysis_intent':
            value = {'intent': 'update_analysis' if changes else 'question_only',
                     'scenario': None, 'candidate_states': None, 'priority_weights': None,
                     'selected_counties': None, 'explanation': '', **(changes or {})}
        else:
            evidence = json.loads(body['input'][0]['content'])
            target = evidence['question_target_counties'][0]
            unavailable = any(target['nws'][kind]['status'] != 'ok' for kind in ('alerts','forecast'))
            value = structured_answer('**Long-term hazard context · FEMA**\n- ' + target['county'] +
                     ': overall risk ' + str(target['fema']['RISK_SCORE']) +
                     '\n\n**Current operational weather · NWS**\n- ' +
                     ('Current operational weather is temporarily unavailable.' if unavailable else
                      'No active alerts at the representative point; forecast is Clear.'))
        return io.BytesIO(json.dumps({'status':'completed','output':[{'type':'message','content':[
            {'type':'output_text','text':json.dumps(value)}]}]}).encode())
    monkeypatch.setattr('urllib.request.urlopen', respond)
    return calls


def workspace():
    app = AppTest.from_file('../app.py', default_timeout=60)
    app.secrets['OPENAI_API_KEY'] = 'test-key'; app.secrets['AI_PROVIDER'] = 'openai'
    app.session_state['experience_mode'] = 'analysis'
    app.session_state['candidate_states'] = ['NJ']
    app.session_state['chosen_counties'] = ['34023', '34003']
    return app.run()


@pytest.mark.parametrize('question,targets', [
    ('What risks should I investigate?', ['34035']),
    ('What risks should I investigate in Middlesex County?', ['34023']),
    ('Compare these counties.', ['34023', '34003']),
])
def test_updated_target_fema_and_nws_before_answer(monkeypatch, mocked_weather, question, targets):
    calls = model(monkeypatch)
    app = workspace()
    assert not app.exception and not calls and not any(mocked_weather.values())
    baseline = card_values(app)
    app.chat_input(key='followup_question').set_value(question).run()
    assert not app.exception and len(calls) == 2
    supplied = json.loads(calls[-1]['input'][0]['content'])
    data, _ = load_data(); points = data.set_index('fips')
    expected = [(float(points.loc[fips].lat), float(points.loc[fips].lon)) for fips in targets]
    assert mocked_weather == {'alerts': expected, 'forecast': expected}
    fema, metadata = load_fema_context(data)
    fema = fema.set_index('fips')
    assert supplied['fema_source']['version'] == metadata['version']
    for county in supplied['question_target_counties']:
        assert set(county['fema']) == set(FIELDS)
        assert county['fema']['RISK_SCORE'] == fema.loc[county['fips'], 'RISK_SCORE']
        assert county['nws']['alerts']['status'] == 'ok'
        assert county['nws']['forecast']['periods'][0]['temperature'] == 40
    for county in supplied['selected_counties']:
        if county['fips'] not in targets:
            assert county['nws']['forecast']['status'] == 'not_fetched_in_this_session'
    if supplied['question_context']['kind'] == 'explicit_counties':
        # Named-county questions now deliberately move the headline highlight;
        # weather enrichment still leaves deterministic scores/rankings unchanged.
        row = points.loc[targets[0]]
        assert app.session_state['highlighted_fips'] == targets[0]
        assert card_values(app)[1:4] == [
            f'{row.employment:,.0f}', f'${row.annual_pay:,.0f}',
            f'{row.electricity_cents_kwh:.2f} ¢/kWh']
    else:
        assert card_values(app) == baseline
    app.run(); app.selectbox(key='map_view').select('FEMA risk context').run()
    assert len(calls) == 2 and mocked_weather == {'alerts': expected, 'forecast': expected}
    app.chat_input(key='followup_question').set_value(question).run()
    assert len(calls) == 4 and mocked_weather == {'alerts': expected, 'forecast': expected}


def test_post_update_leader_fetched_and_slider_alone_never_fetches(monkeypatch, mocked_weather):
    calls = model(monkeypatch, {'priority_weights': dict(zip(LABELS, [0,0,100,0]))})
    app = workspace()
    app.slider(key='priority_weight_0').set_value(50).run()
    assert not any(mocked_weather.values()) and not calls
    app.chat_input(key='followup_question').set_value('Prioritize workforce depth and assess risks.').run()
    supplied = json.loads(calls[-1]['input'][0]['content'])
    assert supplied['current_leader']['fips'] == '34023'
    assert supplied['question_target_counties'][0]['fips'] == '34023'
    assert '34035' not in app.session_state['interpretation_weather']
    expected = score_counties(load_data()[0], [0,0,100,0]).query('state == "NJ" and complete')
    assert supplied['current_top_five'][0]['score'] == expected.iloc[0].score


def test_weather_failure_still_answers_safely(monkeypatch, mocked_weather):
    def fail(*args):
        raise TimeoutError('private-error')
    monkeypatch.setattr('weather.get_alerts', fail)
    monkeypatch.setattr('weather.get_forecast', fail)
    calls = model(monkeypatch)
    app = workspace()
    app.chat_input(key='followup_question').set_value('What risks should I investigate?').run()
    assert not app.exception and len(calls) == 2
    supplied = json.loads(calls[-1]['input'][0]['content'])
    target = supplied['question_target_counties'][0]
    assert target['nws']['alerts'] == {'status':'unavailable'}
    assert target['nws']['forecast'] == {'status':'unavailable'}
    assert 'private-error' not in json.dumps(supplied)
    assert any('temporarily unavailable' in text.value for text in app.markdown)
    assert 'labor quality' not in INSTRUCTIONS
    assert 'warehousing workforce depth' in INSTRUCTIONS
    assert 'failed' in INSTRUCTIONS and 'never equate' in INSTRUCTIONS


def test_plain_top_five_question_skips_weather(monkeypatch, mocked_weather):
    model(monkeypatch)
    app = workspace()
    app.chat_input(key='followup_question').set_value('What are the top five?').run()
    assert not app.exception and not any(mocked_weather.values())


def test_fresh_streamlit_cache_reused_across_browser_sessions(monkeypatch, mocked_weather):
    model(monkeypatch)
    first = workspace()
    first.chat_input(key='followup_question').set_value('What risks should I investigate?').run()
    counts = {kind: len(calls) for kind, calls in mocked_weather.items()}
    second = workspace()
    second.chat_input(key='followup_question').set_value('What risks should I investigate?').run()
    assert not second.exception
    assert {kind: len(calls) for kind, calls in mocked_weather.items()} == counts
    assert second.session_state['interpretation_weather']['34035']['forecast']['status'] == 'ok'
