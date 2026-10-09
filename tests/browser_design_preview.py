"""Isolated browser fixture for main's four-factor app. No live AI or weather calls.
Run this file with the shared Python environment; server listens on localhost:18653.
"""
import io
import os
import json
from pathlib import Path
import runpy
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import interpretation
    import weather
    output = ROOT / '.browser_validation'
    output.mkdir(exist_ok=True)
    weather.get_alerts = lambda *args: dict(status='ok', checked_utc=datetime.now(timezone.utc).isoformat(), alerts=[], url='https://api.weather.gov/alerts')
    weather.get_forecast = lambda *args: dict(status='ok', checked_utc=datetime.now(timezone.utc).isoformat(), periods=[], url='https://api.weather.gov/forecast')

    def respond(request, timeout):
        body = json.loads(request.data)
        evidence = json.loads(body['input'][0]['content'])
        parsing = body['text']['format']['name'] == 'analysis_intent'
        if parsing:
            value = dict(intent='question_only', scenario=None, candidate_states=None,
                         priority_weights=None, selected_counties=None, explanation='')
            log = {'kind': 'intent', 'question': evidence['question']}
        else:
            target = evidence['question_target_counties'][0]
            value = dict(headline=target['county'] + ', ' + target['state'], sections=[
                dict(heading='Screening evidence', bullets=[f"**Screening score**: {target['score']:.1f} / 100."]),
                dict(heading='Investigation', bullets=['Compare the public indicators and investigate property-level costs separately.'])])
            log = {'kind': 'answer', 'scenario': evidence['scenario'], 'target': target['fips'],
                   'score': target['score'], 'candidate_states': evidence['candidate_states'],
                   'weights': evidence['priority_weights_pct'], 'top_five': evidence['current_top_five'],
                   'target_context': evidence['question_context']}
        with (output / os.environ.get('WHERE_NEXT_MOCK_LOG', 'ai_calls.jsonl')).open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(log) + '\n')
        fail_marker = output / 'mock_fail_next_answer'
        if not parsing and fail_marker.exists():
            fail_marker.unlink()
            raise TimeoutError('Mocked provider outage')
        return io.BytesIO(json.dumps(dict(status='completed', output=[dict(type='message',
            content=[dict(type='output_text', text=json.dumps(value))])])).encode())

    urllib.request.urlopen = respond
    temporary = tempfile.TemporaryDirectory(prefix='where-next-mock-secrets-')
    mock_secrets = Path(temporary.name) / 'secrets.toml'
    mock_secrets.write_text('OPENAI_API_KEY = "mock-browser-only"\nAI_PROVIDER = "openai"\nOPENAI_MODEL = "gpt-4.1-mini"\n', encoding='utf-8')
    sys.argv = ['streamlit', 'run', str(ROOT / 'app.py'), '--server.port=' + os.environ.get('WHERE_NEXT_MOCK_PORT', '18653'),
                '--server.address=127.0.0.1', '--server.headless=true', '--browser.gatherUsageStats=false', '--secrets.files=' + str(mock_secrets)]
    try:
        runpy.run_module('streamlit', run_name='__main__')
    finally:
        temporary.cleanup()


if __name__ == '__main__':
    main()
