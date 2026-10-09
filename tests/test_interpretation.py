"""Mocked AI tests: no keys or live model requests needed."""
from answer_fixtures import card_values
import io
import json
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError

import pandas as pd
import pytest

from core import LABELS, METRICS, PRESETS, load_data, score_counties, weight_sensitivity
from fema import FIELDS, load_fema_context
from interpretation import (COUNTY_FIELDS, INSTRUCTIONS, SECTIONS, OpenAIProvider,
                            build_evidence, configured_provider, generate_interpretation)

MOCK_SECTIONS = {
    'leader': 'The current leader ranks first under the supplied priorities and Python-calculated percentile components. Its screening score summarizes the selected business priorities. This supports early comparison only and is not a validated site recommendation. The component evidence explains the balance of reach, workforce depth, and benchmark costs.',
    'trade_offs': 'Compare the selected counties using their supplied population reach, existing warehousing employment, annual industry pay, and state electricity benchmarks. Greater workforce depth does not establish hiring availability. Lower benchmark costs do not establish a property tariff or negotiated wage. Annual electricity expense is unavailable unless consumption was entered.',
    'risk_resilience': 'FEMA supplies historical and modelled community hazard context rather than warehouse damage probability or property-level flood risk. Missing hazard fields remain unavailable. NWS evidence is unavailable when not fetched in this session. Any supplied point forecast covers the representative point, not the whole county or a transport route.',
    'missing_data': 'A real site decision still needs property availability, rents, freight rates, tax incentives, local hiring evidence, property flood assessment, and verified delivery requirements. No savings estimates or delivery guarantees can be inferred. Review the supplied sensitivity scenarios as priority trade-offs and confirm property details before making an investment decision.',
}


def response_payload(sections=None, status='completed'):
    return {'status': status, 'output': [{'type': 'message', 'content': [
        {'type': 'output_text', 'text': json.dumps(sections or MOCK_SECTIONS)}]}]}


def mocked_model(monkeypatch, payload=None, failure=None):
    calls = []

    def respond(request, timeout):
        calls.append((request, timeout))
        if failure:
            raise failure
        return io.BytesIO(json.dumps(payload or response_payload()).encode())

    monkeypatch.setattr('urllib.request.urlopen', respond)
    return calls


@pytest.fixture
def evidence():
    data, _ = load_data()
    scored = score_counties(data, PRESETS['General merchandise'])
    fema, metadata = load_fema_context(data)
    return build_evidence(scored.head(3), scored.iloc[0], [40, 30, 20, 10],
                          'General merchandise', ['PA', 'NJ', 'NY', 'OH', 'MD'],
                          None, fema, metadata, {}, LABELS[0],
                          weight_sensitivity(data, [40, 30, 20, 10], 0, ['PA']))


def test_structured_evidence_allowlist_and_missing_values(evidence):
    assert set(evidence) == {'schema_version', 'baseline_year', 'scenario', 'candidate_states',
        'priority_weights_pct', 'current_leader', 'current_top_five', 'selected_counties',
        'question_target_counties', 'question_context',
        'annual_electricity_consumption_kwh', 'fema_source', 'sensitivity'}
    county = evidence['selected_counties'][0]
    assert set(county) == {*COUNTY_FIELDS, 'percentile_components',
        'illustrative_annual_electricity_expense_usd', 'fema', 'nws'}
    assert set(county['percentile_components']) == set(LABELS)
    assert set(county['fema']) == set(FIELDS)
    assert set(county['nws']) == {'representative_point', 'alerts', 'forecast'}
    assert county['nws']['alerts'] == {'status': 'not_fetched_in_this_session'}
    assert county['nws']['forecast'] == {'status': 'not_fetched_in_this_session'}
    assert county['illustrative_annual_electricity_expense_usd'] == 'Unavailable'
    assert evidence['annual_electricity_consumption_kwh'] == 'Unavailable'
    json.dumps(evidence, allow_nan=False)


def test_missing_metrics_and_extra_fields_are_not_sent():
    data, _ = load_data()
    scored = score_counties(data, [40, 30, 20, 10])
    selected = scored[~scored.complete].head(1).copy()
    selected['rent'] = 'PRIVATE_UNINTENDED_FIELD'
    selected['application_code'] = 'PRIVATE_UNINTENDED_FIELD'
    result = build_evidence(selected, None, [40, 30, 20, 10], 'General merchandise', ['PA'],
                            1000, pd.DataFrame(), {'status': 'unavailable',
                            'error': 'PRIVATE_UNINTENDED_FIELD'}, {}, LABELS[0], [])
    county = result['selected_counties'][0]
    assert county['score'] == 'Unavailable'
    assert county['annual_pay'] == 'Unavailable' or county['employment'] == 'Unavailable'
    assert all(value == 'Unavailable' for value in county['fema'].values())
    assert county['illustrative_annual_electricity_expense_usd'] == pytest.approx(
        selected.iloc[0].electricity_cents_kwh * 10)
    assert 'PRIVATE_UNINTENDED_FIELD' not in json.dumps(result, allow_nan=False)


def test_weather_only_from_selected_county_session_and_when_fresh():
    now = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    data, _ = load_data()
    scored = score_counties(data, [40, 30, 20, 10])
    selected = scored[scored.fips.eq('42069')]
    weather = {'42069': {
        'alerts': {'status': 'ok', 'checked_utc': now.isoformat(),
                   'url': 'https://api.weather.gov/alerts/active?point=41.4366,-75.6088',
                   'alerts': [], 'error': 'PRIVATE_UNINTENDED_FIELD'},
        'forecast': {'status': 'ok', 'checked_utc': (now - timedelta(minutes=16)).isoformat(),
                     'periods': [{'name': 'PRIVATE_UNINTENDED_FIELD'}]}},
        '24001': {'alerts': {'status': 'ok', 'alerts': ['PRIVATE_UNINTENDED_FIELD']}}}
    result = build_evidence(selected, scored.iloc[0], [40, 30, 20, 10], 'General merchandise',
                            ['PA'], None, pd.DataFrame(), {'status': 'unavailable'}, weather,
                            LABELS[0], [], now=now)
    nws = result['selected_counties'][0]['nws']
    assert nws['alerts']['status'] == 'ok' and nws['alerts']['alerts'] == []
    assert nws['forecast']['status'] == 'stale' and 'periods' not in nws['forecast']
    assert 'PRIVATE_UNINTENDED_FIELD' not in json.dumps(result)


def test_provider_sends_only_evidence_and_grounding_instructions(monkeypatch, evidence):
    calls = mocked_model(monkeypatch)
    result = generate_interpretation(evidence, OpenAIProvider('test-key'))
    assert result['status'] == 'ok' and result['sections'] == MOCK_SECTIONS
    request, timeout = calls[0]
    assert request.full_url == 'https://api.openai.com/v1/responses' and timeout == 30
    body = json.loads(request.data)
    assert json.loads(body['input'][0]['content']) == evidence
    assert body['tools'] == [] and body['store'] is False
    assert body['model'] == 'gpt-4.1-mini'
    assert body['text']['format']['schema']['required'] == list(SECTIONS)
    assert body['instructions'] == INSTRUCTIONS
    for requirement in ('Use only', 'Never invent', 'Do not recalculate',
                        'property-level', 'county-wide', 'rents', 'savings estimates'):
        assert requirement in body['instructions']
    assert 'test-key' not in request.data.decode()
    assert sum(len((SECTIONS[key] + ' ' + text).split())
               for key, text in result['sections'].items()) <= 250


def test_no_key_configuration_and_explicit_disable(monkeypatch, evidence):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('AI_PROVIDER', raising=False)
    assert configured_provider({}) is None
    assert generate_interpretation(evidence, None) == {
        'status': 'not_configured', 'message': 'AI interpretation is not configured.'}
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    assert configured_provider({'AI_PROVIDER': 'none'}) is None
    assert configured_provider({}).model == 'gpt-4.1-mini'
    assert configured_provider({'OPENAI_MODEL': 'configured-model'}).model == 'configured-model'


@pytest.mark.parametrize('failure', [TimeoutError('secret'),
    HTTPError('https://api.openai.com/v1/responses', 401, 'secret', {}, None)])
def test_api_failure_is_safe(monkeypatch, evidence, failure):
    mocked_model(monkeypatch, failure=failure)
    result = generate_interpretation(evidence, OpenAIProvider('secret'))
    assert result['status'] == 'unavailable'
    assert 'secret' not in json.dumps(result)


@pytest.mark.parametrize('payload', [response_payload(status='incomplete'),
    response_payload({'leader': 'Missing sections'}),
    response_payload({key: 'word ' * 150 for key in SECTIONS}),
    {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]}])
def test_invalid_or_overlong_output_falls_back(monkeypatch, evidence, payload):
    mocked_model(monkeypatch, payload=payload)
    assert generate_interpretation(evidence, OpenAIProvider('test-key'))['status'] == 'unavailable'


def make_app():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file('../app.py', default_timeout=60)
    app.secrets['OPENAI_API_KEY'] = 'test-key'
    app.secrets['AI_PROVIDER'] = 'openai'
    app.secrets['OPENAI_MODEL'] = 'gpt-4.1-mini'
    app.session_state['experience_mode'] = 'analysis'
    app.session_state['view_mode'] = 'dashboard'
    return app.run()


def test_app_without_key(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    calls = mocked_model(monkeypatch)
    app = AppTest.from_file('../app.py', default_timeout=60)
    app.secrets['OPENAI_API_KEY'] = ''
    app.secrets['AI_PROVIDER'] = 'openai'
    app.session_state['experience_mode'] = 'analysis'
    app.session_state['view_mode'] = 'dashboard'
    app.run()
    assert not app.exception
    app.button(key='overall_summary').click().run()
    assert not app.exception and not calls
    assert any(info.value == 'AI interpretation is not configured.' for info in app.info)


def test_app_button_only_labeled_output_and_invalidated_evidence(monkeypatch):
    calls = mocked_model(monkeypatch)
    app = make_app()
    assert not app.exception and not calls
    baseline_metrics = card_values(app)
    app.button(key='overall_summary').click().run()
    assert not app.exception and len(calls) == 1
    assert any(markdown.value == '**AI-generated interpretation**' for markdown in app.markdown)
    assert [text.value for text in app.markdown if text.value in MOCK_SECTIONS.values()] == list(MOCK_SECTIONS.values())
    assert card_values(app) == baseline_metrics
    assert any(expander.label == 'County evidence summaries' for expander in app.expander)
    app.selectbox(key='map_view').select('FEMA risk context').run()
    assert not app.exception and len(calls) == 1
    assert any(markdown.value == '**AI-generated interpretation**' for markdown in app.markdown)
    app.slider(key='priority_weight_0').set_value(50).run()
    assert not app.exception and len(calls) == 1
    assert any(markdown.value == '**AI-generated interpretation**' for markdown in app.markdown)
    assert [text.value for text in app.markdown if text.value in MOCK_SECTIONS.values()] == list(MOCK_SECTIONS.values())
    assert any('Historical interpretation' in item.value for item in app.caption)


def test_app_api_failure_falls_back(monkeypatch):
    calls = mocked_model(monkeypatch, failure=TimeoutError('private-key'))
    app = make_app()
    app.button(key='overall_summary').click().run()
    assert not app.exception and len(calls) == 1
    assert any('AI interpretation unavailable' in info.value for info in app.info)
    assert not any('private-key' in info.value for info in app.info)


def test_app_uses_session_forecast_without_fetching_weather_for_ai(monkeypatch):
    import streamlit as st

    st.cache_data.clear()
    weather_calls = []

    def forecast(lat, lon):
        weather_calls.append((lat, lon))
        return {'status': 'ok', 'url': 'https://api.weather.gov/gridpoints/BGM/81,28/forecast',
                'checked_utc': datetime.now(timezone.utc).isoformat(),
                'updated': None, 'generated_at': None,
                'periods': [{'name': 'Tonight', 'temperature': 39, 'temperatureUnit': 'F',
                             'shortForecast': 'Mostly Clear', 'windSpeed': '7 mph',
                             'windDirection': 'NW'}]}

    monkeypatch.setattr('weather.get_forecast', forecast)
    calls = mocked_model(monkeypatch)
    app = make_app()
    next(widget for widget in app.multiselect if widget.label == 'Choose up to three counties').set_value(['42069']).run()
    assert not app.exception and not calls and not weather_calls
    app.selectbox(key='weather_county').select('42069').run()
    next(button for button in app.button if button.label == 'Check NWS forecast').click().run()
    assert not app.exception and len(weather_calls) == 1 and not calls
    app.button(key='overall_summary').click().run()
    assert not app.exception and len(weather_calls) == 1 and len(calls) == 1
    body = json.loads(calls[0][0].data)
    supplied = json.loads(body['input'][0]['content'])['selected_counties'][0]['nws']
    assert supplied['forecast']['periods'][0]['temperature'] == 39
    assert supplied['alerts']['status'] == 'not_fetched_in_this_session'
    st.cache_data.clear()
