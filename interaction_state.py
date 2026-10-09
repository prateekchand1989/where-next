"""Validated control events and guarded refresh bookkeeping; no scoring or provider code."""
import hashlib
import json
import re
from copy import deepcopy

from analysis_intent import STATES, intent_schema, validated_changes
from core import LABELS, PRESETS
from question_targeting import STATE_NAMES, explicit_screening_states

WEIGHT_KEYS = [f'priority_weight_{i}' for i in range(len(LABELS))]


def initialize_interactions(state):
    state.setdefault('interaction_revision', 0)
    state.setdefault('ai_refresh', {'status': 'idle'})
    state.setdefault('last_user_question', state.get('submitted_question', ''))
    state.setdefault('active_question', state.get('submitted_question', ''))
    state.setdefault('last_valid_states', list(state.get('candidate_states', STATES)))


def reset_interactions(state):
    revision = state.get('interaction_revision', 0) + 1
    counter = state.get('request_counter', 0)
    for key in ('interaction_revision', 'ai_refresh', 'last_user_question', 'active_question',
                'last_valid_states', 'manual_refresh_mode', 'manual_refresh_kind', 'manual_scope_override',
                'last_successful_context',
                'active_request', 'request_counter', 'state_selection_notice', 'retry_requested', 'retry_target'):
        state.pop(key, None)
    initialize_interactions(state)
    state['interaction_revision'] = revision
    state['request_counter'] = counter


def controls(state):
    scenario = state.get('scenario', next(iter(PRESETS)))
    return {'scenario': scenario,
            'priority_weights': [state.get(k, v) for k, v in zip(WEIGHT_KEYS, PRESETS[scenario])],
            'candidate_states': list(state.get('candidate_states', STATES)),
            'selected_counties': list(state.get('chosen_counties', []))}


def validated_patch(state, patch, data):
    """Use main's atomic validator for both widget and parsed-intent updates."""
    intent = dict.fromkeys(intent_schema()['properties'])
    intent.update(intent='update_analysis', explanation='', **patch)
    if isinstance(intent.get('priority_weights'), list):
        intent['priority_weights'] = dict(zip(LABELS, intent['priority_weights']))
    previous = controls(state)
    # Force validation even for values the native widget has already written.
    for key in patch:
        previous[key] = None
    return validated_changes(intent, previous, data)


def apply_patch(state, patch, data):
    clean = validated_patch(state, patch, data)
    for name in ('scenario', 'candidate_states'):
        if name in clean:
            state[name] = clean[name]
    if 'priority_weights' in clean:
        state.update(dict(zip(WEIGHT_KEYS, clean['priority_weights'])))
        state['weight_preset'] = state.get('scenario', next(iter(PRESETS)))
    if 'selected_counties' in clean:
        state['chosen_counties'] = clean['selected_counties']
        state['comparison_manual'] = True
    if 'candidate_states' in clean:
        state['last_valid_states'] = list(clean['candidate_states'])
    return clean


def mark_manual_change(state, kind='auto'):
    state['interaction_revision'] = state.get('interaction_revision', 0) + 1
    state['manual_refresh_mode'] = 'apply' if kind == 'weights' else 'manual'
    state['manual_refresh_kind'] = kind
    if kind == 'states':
        state['manual_scope_override'] = True
    state.pop('retry_requested', None)
    state.pop('retry_target', None)
    if state.get('pending_answer', {}).get('automatic'):
        state.pop('pending_answer', None)
    if state.get('ai_refresh', {}).get('status') != 'failed':
        state['ai_refresh'] = {'status': 'stale'}


def accept_states(state, data):
    patch = apply_patch(state, {'candidate_states': state.get('candidate_states', [])}, data)
    if 'candidate_states' not in patch:
        state['candidate_states'] = list(state.get('last_valid_states', STATES))
        state['state_selection_notice'] = 'Select at least one supported state. Your previous selection was kept.'
        return False
    state.pop('state_selection_notice', None)
    mark_manual_change(state, 'states')
    return True


def apply_refresh(state):
    state['manual_refresh_mode'] = 'manual'
    if state.get('ai_refresh', {}).get('status') != 'failed':
        state['ai_refresh'] = {'status': 'stale'}


def retry_refresh(state, target='answer'):
    state['retry_requested'] = True
    state['retry_target'] = target
    state['ai_refresh'] = {'status': 'pending'}


def current_question(state):
    original = state.get('last_user_question') or state.get('submitted_question', '')
    if not state.get('manual_scope_override') or not explicit_screening_states(original):
        return original
    aliases = [*STATE_NAMES, *STATE_NAMES.values()]
    token = '(?:' + '|'.join(re.escape(s) for s in sorted(aliases, key=len, reverse=True)) + r')\b(?!\s+County)'
    pattern = r'\b(in|within|across|from)\s+' + token + r'(?:\s*(?:,|and|or|&|\+)\s*' + token + ')*'
    scope = ' and '.join(STATE_NAMES[code] for code in state['candidate_states'])
    return re.sub(pattern, lambda m: m.group(1) + ' ' + scope, original, flags=re.I)


def control_signature(state):
    values = controls(state)
    values['candidate_states'] = sorted(values['candidate_states'])
    values.update(annual_kwh=state.get('annual_kwh'),
                  sensitivity_factor=state.get('sensitivity_factor', LABELS[0]),
                  highlighted_fips=state.get('highlighted_fips'))
    return json.dumps(values, sort_keys=True)


def context_key(question, fingerprint):
    return hashlib.sha256((question + '\0' + fingerprint).encode()).hexdigest()


def begin_request(state, question, fingerprint):
    number = state.get('request_counter', 0) + 1
    state['request_counter'] = number
    token = dict(id=number, revision=state.get('interaction_revision', 0),
                 controls=control_signature(state), key=context_key(question, fingerprint))
    state['active_request'] = token
    state['ai_refresh'] = {'status': 'running', 'key': token['key']}
    state.pop('manual_refresh_mode', None)
    state.pop('retry_requested', None)
    return token


def request_is_current(state, token):
    return (state.get('active_request') == token
            and state.get('interaction_revision', 0) == token['revision']
            and control_signature(state) == token['controls'])


def finish_request(state, token, result):
    if state.get('active_request') != token:
        return False
    if not request_is_current(state, token):
        state['ai_refresh'] = {**state.get('ai_refresh', {}),
            'status': 'stale'}
        return False
    if result['status'] == 'ok':
        state['last_successful_context'] = token['key']
    state['ai_refresh'] = {'status': 'succeeded' if result['status'] == 'ok' else 'failed',
                          'key': token['key']}
    return True


def reusable_turn(state, question, fingerprint):
    return next((deepcopy(t) for t in reversed(state.get('question_history', []))
                 if t['question'] == question and t['fingerprint'] == fingerprint
                 and t['result']['status'] == 'ok'), None)
