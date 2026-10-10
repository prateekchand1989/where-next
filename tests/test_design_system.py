"""UI behavior tests using real app state and mocked providers; no network calls."""
import json
from streamlit.testing.v1 import AppTest
from core import load_data, score_counties, PRESETS, LABELS
from design_system import initialize_theme, toggle_theme, select_county, ranking_table_html
from question_state import initialize_question_state, reset_for_new_question
from ui_styles import application_styles
from test_question_flow import model, submit
from answer_fixtures import card_values


def make_app():
    return AppTest.from_file('../app.py', default_timeout=60).run()


def test_theme_state_is_independent_of_analysis_reset():
    state = {}
    initialize_question_state(state)
    initialize_theme(state)
    assert state['ui_theme'] == 'dark'
    toggle_theme(state)
    initialize_theme(state)
    reset_for_new_question(state)
    assert state['ui_theme'] == 'light'
    assert state['experience_mode'] == 'landing'


def test_landing_toggle_and_dashboard_entry_without_model(monkeypatch):
    calls = model(monkeypatch)
    app = make_app()
    assert not app.exception and app.session_state['ui_theme'] == 'dark'
    app.button(key='toggle_theme').click().run()
    assert app.session_state['ui_theme'] == 'light'
    app.button(key='explore_dashboard').click().run()
    assert not app.exception and app.session_state['view_mode'] == 'dashboard'
    assert not calls and not calls.intent_calls
    before = card_values(app)
    fips = app.session_state['highlighted_fips']
    weights = [app.session_state[f'priority_weight_{i}'] for i in range(len(LABELS))]
    app.button(key='toggle_theme').click().run()
    assert card_values(app) == before and app.session_state['highlighted_fips'] == fips
    assert [app.session_state[f'priority_weight_{i}'] for i in range(len(LABELS))] == weights
    app.button(key='nav_ask').click().run()
    assert app.session_state['ui_theme'] == 'dark' and not calls
    app.button(key='nav_overview').click().run()
    app.button(key='start_new_question').click().run()
    assert app.session_state['ui_theme'] == 'dark' and app.session_state['experience_mode'] == 'landing'


def test_ranking_and_map_picker_share_authoritative_selection(monkeypatch):
    calls = model(monkeypatch)
    app = make_app().button(key='explore_dashboard').click().run()
    data = load_data()[0]
    scored = score_counties(data, PRESETS['General merchandise'])
    ranked = scored[scored.complete & scored.state.isin(app.session_state['candidate_states'])]
    target = ranked.iloc[2]
    app.selectbox(key='ranking_selection').select(target.fips).run()
    assert not app.exception and app.session_state['highlighted_fips'] == target.fips
    assert app.session_state['highlighted_rank'] == 3
    assert app.session_state['chosen_counties'][0] == target.fips
    assert card_values(app)[0] == f'{target.county}, {target.state}'
    chart = next(c for c in app.get('plotly_chart') if c.key == 'county_map')
    marker = json.loads(chart.proto.spec)['data'][-1]
    selected = marker['text'].index(f'{target.county}, {target.state}')
    assert marker['lat'][selected] == target.lat and marker['lon'][selected] == target.lon
    assert marker['marker']['size'][selected] == 14
    scored = score_counties(data, PRESETS['General merchandise'])
    missing = scored.loc[~scored.complete].iloc[0]
    app.selectbox(key='map_county_selection').select(missing.fips).run()
    assert not app.exception and app.session_state['highlighted_fips'] == missing.fips
    assert app.session_state['highlighted_rank'] is None
    assert 'Unavailable' in card_values(app)
    assert not calls


def test_theme_retains_main_question_history_and_four_factor_scenarios(monkeypatch):
    calls = model(monkeypatch)
    app = make_app()
    app.secrets['OPENAI_API_KEY'] = 'test-key'
    app.secrets['AI_PROVIDER'] = 'openai'
    app = submit(app, 'Best county in PA')
    assert not app.exception
    history = list(app.session_state['question_history'])
    app.button(key='toggle_theme').click().run()
    assert app.session_state['question_history'] == history and len(calls) == 1
    app.button(key='nav_overview').click().run()
    app.selectbox(key='scenario').select('Temperature-controlled').run()
    assert app.session_state['ui_theme'] == 'light'
    assert len(LABELS) == 4
    assert [app.session_state[f'priority_weight_{i}'] for i in range(4)] == PRESETS['Temperature-controlled']
    assert 'priority_weight_4' not in app.session_state
    assert 'ranking_coverage' not in app.session_state
    assert len(calls) == 1 and len(calls.intent_calls) == 1
    assert len(app.session_state['question_history']) == 1


def test_tokens_responsive_accessibility_and_escaped_table():
    assert '#080F0D' in application_styles(theme='dark')
    assert '#F5F8F6' in application_styles(theme='light')
    css = application_styles()
    assert 'prefers-reduced-motion' in css and 'focus-visible' in css
    assert '@media(max-width:1100px)' in css and '@media(max-width:650px)' in css
    markup = ranking_table_html([dict(fips='1', county='<script>', state='PA', score=80,
        display_rent=float('nan'), employment=100)], '1')
    assert '&lt;script&gt;' in markup and 'Unavailable' in markup and 'aria-current="true"' in markup
    state = {'highlighted_fips': '1'}
    select_county(state, 'invalid', {'1'})
    assert state['highlighted_fips'] == '1'
