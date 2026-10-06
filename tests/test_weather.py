import copy
import io
import json
from urllib.error import HTTPError, URLError

import pytest

from weather import get_forecast


FORECAST_URL = 'https://api.weather.gov/gridpoints/PHI/50,75/forecast'
POINTS = {'type': 'Feature', 'properties': {'forecast': FORECAST_URL}}
FORECAST = {
    'type': 'Feature',
    'properties': {
        'updated': '2026-10-05T12:00:00+00:00',
        'generatedAt': '2026-10-05T12:05:00Z',
        'periods': [{'name': 'Today', 'temperature': 72, 'temperatureUnit': 'F',
                     'shortForecast': 'Sunny', 'windSpeed': '5 to 10 mph',
                     'windDirection': 'NW'}],
    },
}


def mock_responses(monkeypatch, *payloads):
    calls = []
    responses = iter(payloads)

    def open_response(request, timeout):
        calls.append((request, timeout))
        payload = next(responses)
        if isinstance(payload, Exception):
            raise payload
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr('urllib.request.urlopen', open_response)
    return calls


def test_successful_forecast(monkeypatch):
    calls = mock_responses(monkeypatch, POINTS, FORECAST)
    result = get_forecast(40, -75, timeout=3)
    assert result['status'] == 'ok'
    assert result['periods'] == FORECAST['properties']['periods']
    assert result['updated'] == FORECAST['properties']['updated']
    assert result['generated_at'] == FORECAST['properties']['generatedAt']
    assert result['checked_utc']
    assert [request.full_url for request, _ in calls] == [
        'https://api.weather.gov/points/40.0000,-75.0000', FORECAST_URL]
    for request, timeout in calls:
        assert timeout == 3
        assert request.get_header('User-agent') == 'WhereNext/0.1 (public portfolio demo)'
        assert request.get_header('Accept') == 'application/geo+json'


@pytest.mark.parametrize('payload', [None, [], {}, {'type': 'Feature', 'properties': None},
    {'type': 'Feature', 'properties': {}},
    {'type': 'Feature', 'properties': {'forecast': 123}},
    {'type': 'Feature', 'properties': {'forecast': 'https://example.com/forecast'}}])
def test_malformed_points(monkeypatch, payload):
    calls = mock_responses(monkeypatch, payload)
    result = get_forecast(40, -75)
    assert result['status'] == 'unavailable'
    assert 'periods' not in result
    assert len(calls) == 1


@pytest.mark.parametrize('payload', [None, [], {},
    {'type': 'Feature', 'properties': {}},
    {'type': 'Feature', 'properties': {'periods': []}},
    {'type': 'Feature', 'properties': {'periods': [None]}},
    {'type': 'Feature', 'properties': {'periods': [{'name': 'Today'}]}}])
def test_malformed_forecast(monkeypatch, payload):
    mock_responses(monkeypatch, POINTS, payload)
    result = get_forecast(40, -75)
    assert result['status'] == 'unavailable'
    assert 'periods' not in result


@pytest.mark.parametrize('field,value', [('temperature', True), ('temperature', '72'),
    ('windSpeed', None), ('shortForecast', ''), ('temperature', float('nan'))])
def test_malformed_period(monkeypatch, field, value):
    payload = copy.deepcopy(FORECAST)
    payload['properties']['periods'][0][field] = value
    mock_responses(monkeypatch, POINTS, payload)
    assert get_forecast(40, -75)['status'] == 'unavailable'


@pytest.mark.parametrize('stage', [0, 1])
@pytest.mark.parametrize('error', [TimeoutError(), URLError('unavailable'),
    HTTPError(FORECAST_URL, 503, 'Unavailable', {}, None),
    json.JSONDecodeError('Invalid JSON', '<html>', 0)])
def test_timeout_or_unavailable(monkeypatch, stage, error):
    mock_responses(monkeypatch, *([POINTS, error] if stage else [error]))
    result = get_forecast(40, -75)
    assert result['status'] == 'unavailable'
    assert result['error'] == type(error).__name__
    assert result['stage'] == ('forecast' if stage else 'points')
    assert result['url'] == (FORECAST_URL if stage else 'https://api.weather.gov/points/40.0000,-75.0000')
    assert result['http_status'] == (503 if isinstance(error, HTTPError) else None)
    assert result['message']
    assert 'periods' not in result


def test_diagnostics_do_not_echo_sensitive_exception_text(monkeypatch):
    mock_responses(monkeypatch, URLError('https://user:password@proxy.invalid?api_key=secret'))
    result = get_forecast(40, -75)
    assert result['message'] == 'Network connection unavailable'
    assert 'password' not in json.dumps(result) and 'secret' not in json.dumps(result)


def test_forecast_failure_diagnostics_in_panel(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    st.cache_data.clear()
    mock_responses(monkeypatch, POINTS, HTTPError(FORECAST_URL, 503, 'Unavailable', {}, None))
    app = AppTest.from_file('../app.py', default_timeout=60).run()
    next(button for button in app.button if button.label == 'Check NWS forecast').click().run()
    assert not app.exception
    diagnostics = next(json.loads(element.value) for element in app.json
                       if 'exception_type' in element.value)
    assert diagnostics == {'stage': 'forecast', 'exception_type': 'HTTPError',
                           'http_status': 503, 'requested_url': FORECAST_URL,
                           'message': 'HTTP 503: Service Unavailable'}
    assert any('Point forecast unavailable' in warning.value for warning in app.warning)
    st.cache_data.clear()


def test_forecast_without_optional_timestamps(monkeypatch):
    payload = copy.deepcopy(FORECAST)
    del payload['properties']['updated']
    del payload['properties']['generatedAt']
    mock_responses(monkeypatch, POINTS, payload)
    result = get_forecast(40, -75)
    assert result['status'] == 'ok'
    assert result['updated'] is None and result['generated_at'] is None


def test_forecast_panel_and_cache(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    st.cache_data.clear()
    calls = mock_responses(monkeypatch, POINTS, FORECAST)
    app = AppTest.from_file('../app.py', default_timeout=60).run()
    assert not app.exception
    forecast_button = next(button for button in app.button
                           if button.label == 'Check NWS forecast')
    forecast_button.click().run()
    assert not app.exception
    panel = next(frame.value for frame in app.dataframe if 'Forecast' in frame.value.columns)
    assert panel.iloc[0].to_dict() == {
        'Period': 'Today', 'Temperature': '72 °F', 'Forecast': 'Sunny', 'Wind': '5 to 10 mph NW'}
    assert any('NWS updated: 2026-10-05' in caption.value for caption in app.caption)
    assert any('not county-wide or route-wide' in caption.value for caption in app.caption)
    next(button for button in app.button if button.label == 'Check NWS forecast').click().run()
    assert not app.exception
    assert len(calls) == 2  # Both NWS requests are reused for this point.
    st.cache_data.clear()
