"""Fresh screening boundaries and a common Markdown pipeline, without live calls."""
import json

from analysis_intent import STATES
from core import PRESETS, load_data, score_counties
from interpretation import ANSWER_STYLE
from question_state import (DEFAULT_SCENARIO, WEIGHT_KEYS, initialize_question_state,
                            reset_for_new_question)
from test_analysis_workflow import ANSWER, first, intent, make_app, workflow


def evidence(calls):
    return json.loads(calls[-1]['input'][0]['content'])


def test_reset_clears_transient_state_preserves_weather_config_and_data():
    weather, data = {'36061': {'alerts': {'status': 'ok'}}}, object()
    state = dict(candidate_states=['NY'], scenario='Temperature-controlled',
                 chosen_counties=['36061'], question_target=['36061'],
                 question_context={'fips': ['36061']}, question_intent='NY only',
                 pending_intent=True, pending_question='Old question', pending_answer={},
                 question_answer={}, question_fingerprint='old', analysis_fingerprint='old',
                 location_interpretation={}, interpretation_weather=weather,
                 loaded_data=data, OPENAI_MODEL='configured', annual_kwh=123,
                 weather_county='36061', sensitivity_factor='Workforce depth')
    reset_for_new_question(state)
    assert state['candidate_states'] == STATES
    assert state['scenario'] == state['weight_preset'] == DEFAULT_SCENARIO
    assert [state[key] for key in WEIGHT_KEYS] == PRESETS[DEFAULT_SCENARIO]
    assert state['experience_mode'] == 'landing' and state['view_mode'] == 'ask'
    assert state['question_history'] == [] and state['submitted_question'] == ''
    for key in ('chosen_counties', 'question_target', 'question_context', 'question_intent',
                'pending_intent', 'pending_question', 'pending_answer', 'question_answer',
                'question_fingerprint', 'analysis_fingerprint', 'location_interpretation',
                'weather_county', 'annual_kwh', 'sensitivity_factor'):
        assert key not in state
    assert state['interpretation_weather'] is weather and state['loaded_data'] is data
    assert state['OPENAI_MODEL'] == 'configured'
    fresh = {}
    initialize_question_state(fresh)
    assert all(state[key] == value for key, value in fresh.items())


def test_ny_followup_navigation_then_fresh_broad_and_pa(monkeypatch):
    calls = workflow(monkeypatch)
    app = first(make_app(), 'Where should I put a warehouse?')
    assert evidence(calls)['candidate_states'] == STATES
    app.multiselect(key='candidate_states').set_value(['NY']).run()
    app.multiselect(key='chosen_counties').set_value(['36061']).run()
    app.selectbox(key='scenario').select('Temperature-controlled').run()
    app.slider(key='priority_weight_0').set_value(60).run()
    app.chat_input(key='followup_question').set_value('Why is the current leader first?').run()
    assert evidence(calls)['candidate_states'] == ['NY'] and len(calls) == 4
    app.button(key='open_dashboard').click().run()
    app.button(key='return_to_ask').click().run()
    assert app.session_state['candidate_states'] == ['NY']
    assert app.session_state['chosen_counties'] == ['36061']
    assert app.slider(key='priority_weight_0').value == 60
    assert len(app.session_state['question_history']) == 2 and len(calls) == 4
    app.button(key='start_new_question').click().run()
    app.run()
    assert not app.exception and not app.metric and len(calls) == 4
    assert 'chosen_counties' not in app.session_state
    first(app, 'Where should I put a warehouse?')
    supplied = evidence(calls)
    assert not app.exception and supplied['candidate_states'] == STATES
    assert supplied['scenario'] == DEFAULT_SCENARIO
    assert list(supplied['priority_weights_pct'].values()) == PRESETS[DEFAULT_SCENARIO]
    data, _ = load_data()
    ranked = score_counties(data, PRESETS[DEFAULT_SCENARIO])
    assert app.session_state['chosen_counties'] == list(ranked.head(3).fips)
    assert supplied['question_context']['fips'] == [ranked.iloc[0].fips]
    assert json.loads(calls[-1]['input'][1]['content'])['conversation'] == []
    assert len(calls) == 6
    # A fresh explicit constraint still goes through intent parsing normally.
    app.multiselect(key='candidate_states').set_value(['NY']).run()
    app.button(key='start_new_question').click().run()
    pa_calls = workflow(monkeypatch, intent(candidate_states=['PA']))
    first(app, 'Where should I put a warehouse in Pennsylvania?')
    assert not app.exception and evidence(pa_calls)['candidate_states'] == ['PA']
    before = json.loads(pa_calls[0]['input'][0]['content'])['current_controls']
    assert before['candidate_states'] == STATES
    app.run()
    assert len(pa_calls) == 2


def test_all_turns_share_markdown_format_and_history_preserves_it(monkeypatch):
    calls = workflow(monkeypatch)
    app = first(make_app())
    for question in ('What risks should I investigate?', 'Why is the current leader first?'):
        app.chat_input(key='followup_question').set_value(question).run()
    assert not app.exception and len(calls) == 6
    answers = [call for call in calls if call['text']['format']['name'] != 'analysis_intent']
    assert all(ANSWER_STYLE in call['instructions'] for call in answers)
    assert len([item for item in app.markdown if item.value == ANSWER]) == 3
    assert not any(item.value == ANSWER for item in app.text)
    older = app.get('expander')[1]
    assert older.proto.expanded is False
    assert any(item.value == ANSWER for item in older.markdown)
    assert all(turn['result']['answer'] == ANSWER for turn in app.session_state['question_history'])
    change_calls = workflow(monkeypatch, intent(candidate_states=['PA']))
    app.chat_input(key='followup_question').set_value('Only compare Pennsylvania').run()
    assert not app.exception and len(change_calls) == 2
    assert ANSWER_STYLE in change_calls[-1]['instructions']
    assert app.session_state['question_answer']['analysis_changed']
    assert app.session_state['question_answer']['result']['answer'] == ANSWER
