"""Interaction regressions with mocked providers and unchanged main scoring."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from core import LABELS, PRESETS, load_data, score_counties
from analysis_intent import STATES
from question_state import initialize_question_state
from interaction_state import (initialize_interactions, apply_patch, accept_states,
    current_question, mark_manual_change, begin_request, finish_request, retry_refresh)
from test_question_flow import model, submit
from test_analysis_workflow import workflow, intent

ROOT = Path(__file__).resolve().parents[1]


def app(configured=True):
    value = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=60)
    value.secrets['OPENAI_API_KEY'] = 'mock-interaction-key' if configured else ''
    value.secrets['AI_PROVIDER'] = 'openai'
    return value.run()


def supplied(calls):
    return json.loads(calls[-1]['input'][0]['content'])


@pytest.mark.parametrize('selection', [['NJ'], ['PA', 'NJ'], STATES])
def test_manual_supported_scope_without_invented_ai_question(monkeypatch, selection):
    calls = model(monkeypatch)
    value = app().button(key='explore_dashboard').click().run()
    value.multiselect(key='candidate_states').set_value(selection).run()
    assert not value.exception and set(value.multiselect(key='candidate_states').value) == set(selection)
    assert not calls and not calls.intent_calls and not value.session_state['question_history']
    assert set(value.session_state['candidate_states']) <= set(STATES)
    assert len(value.slider) == 4 and sum(w.value for w in value.slider) == 100


@pytest.mark.parametrize('bad', [[], ['CA'], ['NJ', 'NJ'], ['PA', 'CA']])
def test_invalid_manual_scope_keeps_authoritative_selection(bad):
    state = {};initialize_question_state(state);initialize_interactions(state)
    data = load_data()[0]
    before = deepcopy(state)
    assert apply_patch(state, {'candidate_states': bad}, data) == {}
    assert state == before
    state['candidate_states'] = bad
    assert not accept_states(state, data)
    assert state['candidate_states'] == STATES and state['state_selection_notice']


def test_ai_scope_then_manual_scope_overrides_original_ordinal(monkeypatch):
    calls = workflow(monkeypatch, intent(candidate_states=['NJ']))
    value = submit(app(), 'Which is the second-best county in NJ?')
    assert value.multiselect(key='candidate_states').value == ['NJ'] and len(calls) == 2
    original = deepcopy(value.session_state['question_answer'])
    value.multiselect(key='candidate_states').set_value(['PA']).run()
    assert not value.exception and len(calls) == 2
    ranked = score_counties(load_data()[0], PRESETS['General merchandise'])
    ranked = ranked[ranked.complete & ranked.state.eq('PA')]
    assert value.session_state['highlighted_fips'] == ranked.iloc[1].fips
    assert value.session_state['question_answer'] == original
    assert value.session_state['question_history'] == [original]
    assert next(e for e in value.expander if e.key == 'latest_response_1').proto.expanded
    assert any('earlier analytical configuration' in n.value for n in value.info)
    assert set(value.multiselect(key='chosen_counties').value) <= set(ranked.fips)
    value.chat_input(key='followup_question').set_value('Which is the second-best county in PA now?').run()
    assert not value.exception and len(calls) == 4
    assert supplied(calls)['candidate_states'] == ['PA']
    assert value.session_state['question_history'][0] == original


def test_provider_derived_scope_uses_same_native_state(monkeypatch):
    calls = workflow(monkeypatch, intent(candidate_states=['NJ', 'PA']))
    value = submit(app(), 'Only compare New Jersey and Pennsylvania.')
    assert not value.exception and value.multiselect(key='candidate_states').value == ['NJ', 'PA']
    assert supplied(calls)['candidate_states'] == ['NJ', 'PA']
    value.multiselect(key='candidate_states').set_value(['NJ']).run()
    assert supplied(calls)['candidate_states'] == ['NJ', 'PA'] and len(calls)==2
    assert value.session_state['candidate_states'] == ['NJ']


def test_weight_previews_apply_once_and_ignore_identical_evidence(monkeypatch):
    calls = model(monkeypatch)
    value = submit(app(), 'Which county is best for a warehouse?')
    for weight in [45, 55, 65]:
        value.slider(key='priority_weight_0').set_value(weight).run()
        assert not value.exception and len(calls)==1 and len(calls.intent_calls)==1
        assert sum(value.slider(key=f'priority_weight_{i}').value for i in range(4))==100
    saved = deepcopy(value.session_state['question_answer'])
    assert next(e for e in value.expander if e.key == 'latest_response_1').proto.expanded
    value.button(key='apply_ai_weights').click().run()
    assert not value.exception and len(calls)==1 and len(calls.intent_calls)==1
    assert value.session_state['question_answer'] == saved
    assert value.button(key='apply_ai_weights').disabled
    value.run();value.button(key='toggle_theme').click().run()
    value.button(key='nav_overview').click().run();value.button(key='nav_ask').click().run()
    assert len(calls)==1 and len(calls.intent_calls)==1
    value.chat_input(key='followup_question').set_value('Explain the updated ranking.').run()
    assert len(calls)==2 and len(calls.intent_calls)==2
    assert supplied(calls)['priority_weights_pct']['Market reach']==65
    assert value.session_state['question_history'][0] == saved


def test_scenario_refresh_retains_history_and_presets(monkeypatch):
    calls = model(monkeypatch)
    value = submit(app(), 'Which county is best for a warehouse?')
    value.selectbox(key='scenario').select('Temperature-controlled').run()
    assert not value.exception and len(calls)==1 and len(calls.intent_calls)==1
    assert value.session_state['scenario']=='Temperature-controlled'
    assert [value.slider(key=f'priority_weight_{i}').value for i in range(4)]==PRESETS['Temperature-controlled']
    assert len(value.session_state['question_history'])==1
    assert value.session_state['question_history'][0]['evidence']['scenario']=='General merchandise'
    value.run();assert len(calls)==1


def test_empty_selection_is_rejected_without_request(monkeypatch):
    calls=model(monkeypatch)
    value=submit(app(), 'Which is the best county in NJ?')
    value.multiselect(key='candidate_states').set_value([]).run()
    assert not value.exception and value.multiselect(key='candidate_states').value==['NJ']
    assert len(calls)==1 and any('Select at least one' in w.value for w in value.warning)


def test_failed_refresh_is_not_retried_by_rerun_or_navigation(monkeypatch):
    calls = model(monkeypatch)
    value = submit(app(), 'Which county is best for a warehouse?')
    def fail(*args, **kwargs):
        return {'status':'unavailable','message':'AI answer unavailable.'}
    monkeypatch.setattr('interpretation.generate_answer', fail)
    value.multiselect(key='candidate_states').set_value(['NJ']).run()
    assert len(value.session_state['question_history'])==1
    value.chat_input(key='followup_question').set_value('Explain the new NJ rankings.').run()
    assert not value.exception and value.session_state['ai_refresh']['status']=='failed'
    assert len(value.session_state['question_history'])==2
    assert value.session_state['question_history'][0]['result']['status']=='ok'
    assert not next(e for e in value.expander if e.key == 'response_1').proto.expanded
    value.run();value.button(key='toggle_theme').click().run()
    assert len(value.session_state['question_history'])==2
    from interpretation import generate_answer
    # Restore the original main provider path, still backed by the mock HTTP responder.
    monkeypatch.undo()
    calls = model(monkeypatch)
    value.button(key='retry_analysis').click().run()
    assert not value.exception and value.session_state['ai_refresh']['status']=='succeeded'
    assert len(calls)==1 and not calls.intent_calls


def test_no_provider_keeps_live_dashboard_and_offers_retry(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    calls = model(monkeypatch)
    value = submit(app(False), 'Which county is best for a warehouse?')
    value.multiselect(key='candidate_states').set_value(['PA']).run()
    assert not value.exception and not calls and not calls.intent_calls
    assert value.session_state['ai_refresh']['status']=='failed'
    assert value.button(key='retry_analysis')
    value.button(key='nav_overview').click().run()
    assert value.get('plotly_chart') and value.get('dataframe')


def test_newer_request_and_manual_controls_protect_out_of_order_results():
    state={};initialize_question_state(state);initialize_interactions(state)
    old=begin_request(state,'Question','old-evidence')
    state['candidate_states']=['PA'];mark_manual_change(state,'states')
    assert not finish_request(state,old,{'status':'ok'})
    new=begin_request(state,'Question in PA','new-evidence')
    assert finish_request(state,new,{'status':'ok'})
    assert not finish_request(state,old,{'status':'ok'})
    assert state['ai_refresh']['status']=='succeeded'
    assert state['last_successful_context']==new['key']


def test_manual_scope_never_replaces_answer_even_when_returning_to_original(monkeypatch):
    calls=model(monkeypatch)
    value=submit(app(),'Which county is best for a warehouse?')
    value.multiselect(key='candidate_states').set_value(['NJ']).run()
    assert len(calls)==1
    saved=deepcopy(value.session_state['question_answer'])
    value.multiselect(key='candidate_states').set_value(STATES).run()
    assert not value.exception and len(calls)==1
    assert value.session_state['question_answer']==saved
    assert len(value.session_state['question_history'])==1


def test_newer_manual_scope_wins_over_inflight_intent(monkeypatch):
    import io
    import streamlit as st
    calls=[]
    def respond(request, timeout):
        body=json.loads(request.data);calls.append(body)
        parsing=body['text']['format']['name']=='analysis_intent'
        if parsing:
            st.session_state['candidate_states']=['PA']
            mark_manual_change(st.session_state,'states')
            result=intent(candidate_states=['NJ'])
        else:
            from answer_fixtures import structured_answer
            result=structured_answer('Updated evidence.')
        return io.BytesIO(json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(result)}]}]}).encode())
    monkeypatch.setattr('urllib.request.urlopen',respond)
    value=submit(app(),'Which is the second-best county in NJ?')
    assert not value.exception and value.multiselect(key='candidate_states').value==['PA']
    assert supplied(calls)['candidate_states']==['PA']
    assert 'Pennsylvania' in value.session_state['question_answer']['question']


def test_overall_interpretation_context_refreshes_without_invented_question(monkeypatch):
    from test_interpretation import mocked_model
    calls=mocked_model(monkeypatch)
    value=app().button(key='explore_dashboard').click().run()
    value.button(key='overall_summary').click().run()
    assert len(calls)==1 and value.session_state['location_interpretation']['result']['status']=='ok'
    before=deepcopy(value.session_state['location_interpretation'])
    value.multiselect(key='candidate_states').set_value(['NJ']).run()
    assert not value.exception and len(calls)==1
    assert not value.session_state['question_history']
    assert value.session_state['location_interpretation']==before
    assert any('Historical interpretation' in c.value for c in value.caption)
    value.button(key='overall_summary').click().run()
    assert value.session_state['location_interpretation_history'][0]==before
    value.run();value.button(key='toggle_theme').click().run()
    assert len(calls)==2


def test_reset_cannot_reuse_an_inflight_request_token():
    from interaction_state import reset_interactions
    state = {}
    initialize_question_state(state)
    initialize_interactions(state)
    old = begin_request(state, 'Explain', 'same')
    reset_interactions(state)
    new = begin_request(state, 'Explain', 'same')
    assert new['id'] > old['id'] and new['revision'] > old['revision']
    assert not finish_request(state, old, {'status': 'ok'})
    assert state['active_request'] == new and state['ai_refresh']['status'] == 'running'


def test_legacy_automatic_requests_are_discarded(monkeypatch):
    calls=model(monkeypatch)
    value=submit(app(), 'Which is the best county in NJ?')
    original=deepcopy(value.session_state['question_history'])
    value.session_state['manual_refresh_mode']='auto'
    value.session_state['pending_answer']={'question':'Old queued question', 'changes':{}, 'automatic':True}
    value.session_state['ai_refresh']={'status':'pending'}
    value.run()
    assert not value.exception and len(calls)==1 and len(calls.intent_calls)==1
    assert value.session_state['question_history']==original
    assert value.session_state['ai_refresh']['status']=='stale'


@pytest.mark.parametrize('theme', ['dark','light'])
def test_landing_has_no_sidebar_and_workspace_keeps_navigation(monkeypatch, theme):
    calls=model(monkeypatch)
    value=app()
    if theme=='light':value.button(key='toggle_theme').click().run()
    assert not value.sidebar.button and not value.sidebar.children
    value.button(key='explore_dashboard').click().run()
    assert {b.key for b in value.sidebar.button} >= {'nav_ask','nav_overview','start_new_question'}
    value.button(key='start_new_question').click().run()
    assert not value.sidebar.children and not calls


def test_explicit_overall_retry_preserves_question_history(monkeypatch):
    from test_interpretation import mocked_model
    calls=model(monkeypatch)
    value=submit(app(),'Which county is best for a warehouse?')
    original=deepcopy(value.session_state['question_history'])
    calls=mocked_model(monkeypatch, failure=TimeoutError('offline test'))
    value.button(key='nav_overview').click().run()
    value.button(key='overall_summary').click().run()
    assert len(calls)==1 and value.session_state['location_interpretation']['result']['status']!='ok'
    value.multiselect(key='candidate_states').set_value(['NJ']).run()
    assert len(calls)==1 and value.session_state['question_history']==original
    calls=mocked_model(monkeypatch)
    value.button(key='retry_overall_summary').click().run()
    assert not value.exception and len(calls)==1
    assert value.session_state['location_interpretation']['result']['status']=='ok'
    assert value.session_state['question_history']==original


def test_all_manual_evidence_controls_keep_answer_and_context(monkeypatch):
    calls=model(monkeypatch)
    value=submit(app(),'What are the top five counties?')
    original=deepcopy(value.session_state['question_history'])
    value.multiselect(key='chosen_counties').set_value(['34003']).run()
    value.number_input(key='annual_kwh').set_value(2000000.0).run()
    value.button(key='nav_overview').click().run()
    value.selectbox(key='sensitivity_factor').select(LABELS[-1]).run()
    value.selectbox(key='map_view').select('FEMA risk context').run()
    value.button(key='default_weights').click().run()
    assert not value.exception and len(calls)==1 and len(calls.intent_calls)==1
    assert value.session_state['question_history']==original
    assert value.session_state['question_answer']==original[0]
