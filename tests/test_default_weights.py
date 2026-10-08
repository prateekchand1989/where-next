"""Scenario defaults reset atomically without changing scope or calling AI."""
import pytest

from core import PRESETS, load_data, score_counties
from answer_fixtures import card_values
from test_targeting import mock_model
from test_analysis_workflow import first, make_app
from test_reactive_ranking import assert_current_panels


@pytest.mark.parametrize('preset', list(PRESETS))
def test_repeated_default_weights_reset_preserves_preferences_and_reactivity(monkeypatch, preset):
    calls = mock_model(monkeypatch)
    app = first(make_app())
    app.selectbox(key='scenario').select(preset).run()
    app.multiselect(key='candidate_states').set_value(['PA', 'MD']).run()
    app.checkbox(key='national_map').set_value(True).run()
    app.number_input(key='annual_kwh').set_value(100000).run()
    for slider, value in [('priority_weight_3', 82), ('priority_weight_0', 100)]:
        app.slider(key=slider).set_value(value).run()
        assert app.slider(key=slider).value == value
        app.button(key='default_weights').click().run()
        assert [app.slider(key=f'priority_weight_{i}').value for i in range(4)] == PRESETS[preset]
        assert sum(app.slider(key=f'priority_weight_{i}').value for i in range(4)) == 100
        assert_current_panels(app)
        assert app.multiselect(key='candidate_states').value == ['PA', 'MD']
        assert app.checkbox(key='national_map').value is True
        assert app.number_input(key='annual_kwh').value == 100000
        assert app.selectbox(key='scenario').value == preset
        app.button(key='default_weights').click().run()
        assert_current_panels(app)
    manual = ['42069', '24021', '42077']
    app.multiselect(key='chosen_counties').set_value(manual).run()
    app.slider(key='priority_weight_1').set_value(73).run()
    app.button(key='default_weights').click().run()
    assert not app.exception
    assert app.multiselect(key='chosen_counties').value == manual
    ranked = score_counties(load_data()[0], PRESETS[preset])
    ranked = ranked[ranked.complete & ranked.state.isin(['PA', 'MD'])]
    assert card_values(app)[0] == f'{ranked.iloc[0].county}, {ranked.iloc[0].state}'
    assert len(calls) == 2
