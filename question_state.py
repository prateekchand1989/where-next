"""Shared first-session defaults and the explicit fresh-question boundary."""
from core import LABELS, PRESETS
from analysis_intent import STATES
from question_targeting import question_targets

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
    for key in ('chosen_counties', 'comparison_manual', 'comparison_scope',
                'highlighted_fips', 'highlighted_rank', 'highlight_scope', 'ranking_parameters',
                'weather_county', 'annual_kwh', 'sensitivity_factor',
                'pending_question', 'pending_answer', 'question_answer',
                'location_interpretation', 'question_target', 'question_context',
                'question_intent', 'pending_intent', 'question_fingerprint',
                'analysis_fingerprint'):
        state.pop(key, None)
    state.update(question_defaults())


def sync_county_state(state, scored, ranked, states, question=None, weights=None, scenario=None):
    """Presentation selections follow current rankings without changing their math."""
    scope = tuple(sorted(states))
    scope_changed = state.get('comparison_scope') != scope
    parameters = (tuple(weights), scope, scenario) if weights is not None else None
    ranking_changed = parameters is not None and state.get('ranking_parameters') != parameters
    manual = state.get('comparison_manual', 'chosen_counties' in state)
    allowed = set(scored.loc[scored.state.isin(states), 'fips'])
    selected = list(dict.fromkeys(fips for fips in state.get('chosen_counties', []) if fips in allowed))[:3]
    if (scope_changed or (ranking_changed and not manual)) and (not manual or state.get('comparison_scope') is not None or not selected):
        if not manual:
            selected = []
        selected += [fips for fips in ranked.fips if fips not in selected][:3 - len(selected)]
    state.update(chosen_counties=selected, comparison_manual=manual, comparison_scope=scope)
    current = state.get('highlighted_fips')
    if ranking_changed or ranked.empty or current not in set(scored.fips) or (state.get('highlight_scope') != scope and current not in allowed):
        current = ranked.iloc[0].fips if not ranked.empty else None
    if question is not None and not ranked.empty:
        selection = scored[scored.fips.isin(selected)]
        context = question_targets(question, scored, ranked, selection, states, current)
        if context['kind'] in ('current_leader', 'ranked_county', 'explicit_counties'):
            current = context['fips'][0] if context['fips'] else None
    ranks = {fips: position for position, fips in enumerate(ranked.fips, 1)}
    state.update(highlighted_fips=current, highlighted_rank=ranks.get(current), highlight_scope=scope)
    if parameters is not None:
        state['ranking_parameters'] = parameters
