"""Shared first-session defaults and the explicit fresh-question boundary."""
from core import LABELS, PRESETS
from analysis_intent import STATES

DEFAULT_SCENARIO = next(iter(PRESETS))
WEIGHT_KEYS = [f'priority_weight_{i}' for i in range(len(LABELS))]


def question_defaults():
    # Return fresh mutable values; never share history or state lists across sessions.
    return dict(experience_mode='landing', view_mode='ask', submitted_question='',
                question_history=[], landing_question='', followup_question='',
                suggested_question=None, scenario=DEFAULT_SCENARIO,
                weight_preset=DEFAULT_SCENARIO, candidate_states=list(STATES),
                **dict(zip(WEIGHT_KEYS, PRESETS[DEFAULT_SCENARIO])))


def initialize_question_state(state):
    for key, value in question_defaults().items():
        state.setdefault(key, value)


def reset_for_new_question(state):
    """Restore fresh screening; leave data/configuration and reusable NWS intact."""
    for key in ('chosen_counties', 'weather_county', 'annual_kwh', 'sensitivity_factor',
                'pending_question', 'pending_answer', 'question_answer',
                'location_interpretation', 'question_target', 'question_context',
                'question_intent', 'pending_intent', 'question_fingerprint',
                'analysis_fingerprint'):
        state.pop(key, None)
    state.update(question_defaults())
