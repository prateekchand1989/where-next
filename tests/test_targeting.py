"""Recommendation subjects are independent of manual comparison selections."""
import io
import json

import pytest
from streamlit.testing.v1 import AppTest

from core import LABELS, PRESETS, load_data, score_counties, weight_sensitivity
from fema import load_fema_context
from interpretation import build_evidence
from analysis_intent import parse_changes
from answer_fixtures import structured_answer


@pytest.fixture
def screening():
    data, _ = load_data()
    scored = score_counties(data, PRESETS['General merchandise'])
    ranked = scored[scored.complete & scored.state.eq('NJ')]
    selected = scored[scored.fips.eq('34023')]
    fema, metadata = load_fema_context(data)
    return data, scored, ranked, selected, fema, metadata


def evidence(screening, question):
    data, scored, ranked, selected, fema, metadata = screening
    return build_evidence(selected, ranked.iloc[0], PRESETS['General merchandise'],
                          'General merchandise', ['NJ'], None, fema, metadata, {}, LABELS[0],
                          weight_sensitivity(data, PRESETS['General merchandise'], 0, ['NJ']),
                          scored=scored, ranked=ranked, question=question)


@pytest.mark.parametrize('question', ['What risks should I investigate?', 'Why does the leader rank first?',
                                    'What is the best location?', 'What risks affect the current county?'])
def test_broad_question_uses_somerset_even_if_middlesex_selected(screening, question):
    result = evidence(screening, question)
    assert result['current_leader']['fips'] == '34035'
    assert result['selected_counties'][0]['fips'] == '34023'
    assert result['question_context']['kind'] == 'current_leader'
    assert [county['fips'] for county in result['question_target_counties']] == ['34035']
    assert result['question_target_counties'][0]['fema'] == result['current_leader']['fema']
    assert result['current_leader']['nws']['alerts']['status'] == 'not_fetched_in_this_session'


@pytest.mark.parametrize('question,target', [
    ('What risks should I investigate in Middlesex County?', '34023'),
    ('What risks should I investigate in Somerset County, NJ?', '34035'),
    ('What risks should I investigate in Lackawanna County?', '42069'),
    ('What risks should I investigate in New York County?', '36061'),
])
def test_explicit_name_resolves_only_known_county(screening, question, target):
    result = evidence(screening, question)
    assert result['question_context']['kind'] == 'explicit_counties'
    assert [county['fips'] for county in result['question_target_counties']] == [target]
    assert result['selected_counties'][0]['fips'] == '34023'
    assert 'fema' in result['question_target_counties'][0]


@pytest.mark.parametrize('question', ['Compare the risk trade-offs between these counties.',
                                    'What are the trade-offs between these counties?'])
def test_comparison_uses_manual_selection(screening, question):
    result = evidence(screening, question)
    assert result['question_context']['kind'] == 'selected_comparison'
    assert [county['fips'] for county in result['question_target_counties']] == ['34023']


def test_shortlist_uses_python_ranked_top_five(screening):
    result = evidence(screening, 'What risks affect the current shortlist?')
    expected = list(screening[2].head(5).fips)
    assert [county['fips'] for county in result['question_target_counties']] == expected
    assert [county['fips'] for county in result['current_top_five']] == expected
    assert [county['rank'] for county in result['current_top_five']] == [1, 2, 3, 4, 5]
    assert all(set(county) == {'fips', 'county', 'state', 'rank', 'score'} for county in result['current_top_five'])


def test_unknown_and_ambiguous_county_not_invented(screening):
    result = evidence(screening, 'What risks affect Atlantis County?')
    assert result['question_target_counties'] == [] and result['question_context']['unresolved_names']
    data, scored, _, selected, fema, metadata = screening
    ranked = scored[scored.complete]
    result = build_evidence(selected, ranked.iloc[0], [40,30,20,10], 'General merchandise',
                            ['NJ','PA'], None, fema, metadata, {}, LABELS[0], [],
                            scored=scored, ranked=ranked, question='What risks affect Somerset County?')
    assert result['question_target_counties'] == []
    assert result['question_context']['unresolved_names'] == ['Somerset County']


def mock_model(monkeypatch, updates=None):
    calls = []
    def respond(request, timeout):
        body = json.loads(request.data); calls.append(body)
        if body['text']['format']['name'] == 'analysis_intent':
            result = {'intent': 'update_analysis' if updates else 'question_only',
                      'scenario': None, 'candidate_states': None, 'priority_weights': None,
                      'selected_counties': None, 'explanation': '', **(updates or {})}
        else:
            supplied = json.loads(body['input'][0]['content'])
            names = ', '.join(county['county'] for county in supplied['question_target_counties'])
            result = structured_answer('**County context**\n- ' + names + '\n\n**Risk context**\n- Use supplied county FEMA context; property-level flood risk is unavailable.')
        return io.BytesIO(json.dumps({'status':'completed','output':[{'type':'message','content':[
            {'type':'output_text','text':json.dumps(result)}]}]}).encode())
    monkeypatch.setattr('urllib.request.urlopen', respond)
    return calls


def workspace():
    app = AppTest.from_file('../app.py', default_timeout=60)
    app.secrets['OPENAI_API_KEY'] = 'test-key'; app.secrets['AI_PROVIDER'] = 'openai'
    app.session_state['experience_mode'] = 'analysis'
    app.session_state['candidate_states'] = ['NJ']
    app.session_state['chosen_counties'] = ['34023']
    return app.run()


def ask(app, question):
    return app.chat_input(key='followup_question').set_value(question).run()


def test_request_context_and_dashboard_only_features(monkeypatch):
    calls = mock_model(monkeypatch)
    app = workspace()
    assert not app.exception and not calls
    assert not any(header.value in ('Optional AI interpretation', 'Scenario sensitivity',
                                   'How stable is this recommendation?') for header in app.subheader)
    assert not any(button.label in ('Explain selected locations', 'Generate overall summary') for button in app.button)
    ask(app, 'What risks should I investigate?')
    assert not app.exception and len(calls) == 2
    supplied = json.loads(calls[-1]['input'][0]['content'])
    assert supplied['current_leader']['fips'] == '34035'
    assert supplied['question_target_counties'][0]['fips'] == '34035'
    assert app.multiselect(key='chosen_counties').value == ['34023']
    ask(app, 'What risks should I investigate in Middlesex County?')
    assert len(calls) == 4 and app.multiselect(key='chosen_counties').value == ['34023']
    supplied = json.loads(calls[-1]['input'][0]['content'])
    assert supplied['question_target_counties'][0]['fips'] == '34023'
    # Newly fetched Middlesex weather does not invalidate Somerset's scoped answer.
    assert len(app.session_state['question_history']) == 2
    assert not any('Your analysis has changed' in info.value for info in app.info)
    app.button(key='open_dashboard').click().run()
    assert any(header.value == 'How stable is this recommendation?' for header in app.subheader)
    assert app.button(key='overall_summary').label == 'Generate overall summary'
    factor = app.selectbox(key='sensitivity_factor').value
    scenarios = weight_sensitivity(load_data()[0], [40,30,20,10], LABELS.index(factor), ['NJ'])
    top_tables = [frame.value for frame in app.dataframe if frame.value.columns.tolist() == ['Rank','County / state','Score']]
    assert len(top_tables) == 3
    for table, scenario in zip(top_tables, scenarios):
        assert table.Score.tolist() == scenario['top_five'].score.tolist()
    assert len(calls) == 4


def test_manual_and_natural_language_weights_rebuild_targets(monkeypatch):
    calls = mock_model(monkeypatch)
    app = workspace()
    ask(app, 'What risks should I investigate?')
    app.slider(key='priority_weight_2').set_value(100).run()
    assert len(calls) == 2
    ask(app, 'What risks should I investigate?')
    supplied = json.loads(calls[-1]['input'][0]['content'])
    assert supplied['current_leader']['fips'] == '34023'
    assert supplied['current_top_five'][0]['fips'] == '34023'
    assert supplied['question_target_counties'][0]['fips'] == '34023'
    calls = mock_model(monkeypatch, {'priority_weights': dict(zip(LABELS, [100,0,0,0]))})
    ask(app, 'Make market reach the only priority.')
    supplied = json.loads(calls[-1]['input'][0]['content'])
    expected = score_counties(load_data()[0], [100,0,0,0]).query('state == "NJ" and complete').head(5)
    assert supplied['current_leader']['fips'] == '34035'
    assert [row['fips'] for row in supplied['current_top_five']] == list(expected.fips)
    assert supplied['question_target_counties'][0]['fips'] == '34035'
    assert app.multiselect(key='chosen_counties').value == ['34023']


def test_parser_cannot_replace_selection_for_named_risk_question(screening):
    class Provider:
        def parse_intent(self, *args):
            return {'intent':'update_analysis','scenario':None,'candidate_states':None,'priority_weights':None,
                    'selected_counties':['34035'],'explanation':''}
    controls = {'scenario':'General merchandise','candidate_states':['NJ'],
                'priority_weights':[40,30,20,10],'selected_counties':['34023']}
    assert parse_changes(Provider(), 'What risks affect Somerset County?', controls, screening[0]) == {}
