"""Native configuration and evidence-state regressions; no live model calls."""
import json
import tomllib
from pathlib import Path

import pytest
from streamlit import config
from streamlit.errors import StreamlitSecretNotFoundError
from streamlit.runtime.secrets import Secrets
from streamlit.testing.v1 import AppTest

from interpretation import configured_provider, generate_answer
from test_question_flow import model, submit
from ui_styles import application_styles

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('local_override,shared_present', [(False, True), (True, True), (True, False)])
def test_native_shared_config_and_local_precedence(tmp_path, monkeypatch, local_override, shared_present):
    paths = tomllib.loads((ROOT / '.streamlit/config.toml').read_text())['secrets']['files']
    shared = tmp_path / 'where-next/.streamlit/secrets.toml'
    local = tmp_path / 'where-next-design-main/.streamlit/secrets.toml'
    shared.parent.mkdir(parents=True)
    local.parent.mkdir(parents=True)
    if shared_present:
        shared.write_text('OPENAI_API_KEY = "mock-shared-key"\nOPENAI_MODEL = "mock-shared-model"\nAI_PROVIDER = "openai"\n')
    if local_override:
        local.write_text('OPENAI_API_KEY = "mock-local-key"\nOPENAI_MODEL = "mock-local-model"\nAI_PROVIDER = "openai"\n')
    monkeypatch.chdir(local.parent.parent)
    original = config.get_option
    monkeypatch.setattr(config, 'get_option', lambda name: paths if name == 'secrets.files' else original(name))
    monkeypatch.setattr(Secrets, '_maybe_install_file_watchers', lambda self: None)
    for name in ['OPENAI_API_KEY', 'OPENAI_MODEL', 'AI_PROVIDER']:
        monkeypatch.delenv(name, raising=False)
    calls = model(monkeypatch)
    secrets = Secrets()
    try:
        provider = configured_provider(secrets.to_dict())
        assert provider is not None
        assert provider.model == ('mock-local-model' if local_override else 'mock-shared-model')
        result = generate_answer({'schema_version': 2}, provider, 'Explain the leader')
        assert result['status'] == 'ok' and result['structured_answer']['sections']
        assert len(calls) == 1 and calls[0]['model'] == provider.model
        evidence = json.loads(calls[0]['input'][0]['content'])
        assert evidence == {'schema_version': 2}
        assert calls[0]['tools'] == [] and calls[0]['store'] is False
    finally:
        secrets._reset()


def test_missing_local_files_preserves_environment_provider(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'mock-env-key')
    monkeypatch.setenv('OPENAI_MODEL', 'mock-env-model')
    monkeypatch.setenv('AI_PROVIDER', 'openai')
    original = config.get_option
    monkeypatch.setattr(config, 'get_option', lambda name: [str(tmp_path / 'missing.toml')] if name == 'secrets.files' else original(name))
    with pytest.raises(StreamlitSecretNotFoundError):
        Secrets().to_dict()
    assert configured_provider({}).model == 'mock-env-model'


def test_header_clearance_is_only_for_workspace():
    assert 'padding-top:3.5rem' in application_styles(landing=False)
    assert 'padding-top:3.5rem' not in application_styles(landing=True)
    assert 'scroll-margin-top:4.5rem' in application_styles()


@pytest.mark.parametrize('configured', [True, False])
def test_evidence_warning_ignores_presentation_but_retains_real_changes(monkeypatch, configured):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    calls = model(monkeypatch)
    app = AppTest.from_file('../app.py', default_timeout=60)
    app.secrets['OPENAI_API_KEY'] = 'mock-question-key' if configured else ''
    app.secrets['AI_PROVIDER'] = 'openai'
    app = submit(app.run(), 'Why does the current leader rank first?')
    assert not app.exception
    warning = lambda: any('earlier analytical configuration' in item.value for item in app.info)
    assert not warning()
    before = list(app.session_state['question_history'])
    expected = int(configured)
    assert len(calls) == expected and len(calls.intent_calls) == expected
    if configured:
        assert app.session_state['question_answer']['result']['status'] == 'ok'
    else:
        assert app.session_state['question_answer']['result']['status'] == 'not_configured'
    app.button(key='toggle_theme').click().run()
    app.button(key='nav_overview').click().run()
    assert not warning() and not app.exception
    app.button(key='nav_ask').click().run()
    assert not warning() and app.session_state['question_history'] == before
    assert len(calls) == expected and len(calls.intent_calls) == expected
    app.slider(key='priority_weight_0').set_value(50).run()
    assert warning() and not app.exception
    assert len(calls) == expected and len(calls.intent_calls) == expected
