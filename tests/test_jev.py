"""Jev contracts without a paid model: synthetic responses are always explicit."""
import json
import math
from copy import deepcopy
from unittest.mock import patch
import pytest
from maniloop.providers.typesafe import TypeSafeClient, validate_choice, DEFAULT_MODEL
from maniloop.providers.responses import PolicyError
from maniloop.agents.jev import JevAgent, candidates_for, instruction_lines
from maniloop.controllers.geometry import rotation_matrix


def observation():
    return dict(observation_id="obs-1", frame_id="world", tcp_position=[0, 0, 1],
        tcp_rotation_matrix=rotation_matrix([0, math.pi/2, 0]).tolist(), gripper_opening=.5,
        action_limits={"translation_max_m": .05, "rotation_max_rad": .5}, last_feedback={"status": "ready"})


def answer(criteria, chosen=None):
    chosen = chosen or next(iter(criteria))
    return {"model": DEFAULT_MODEL, "answers": {"action": {"type": "choice", "choice": chosen,
        "probabilities": {key: float(key == chosen) for key in criteria}, "confidence": 1.}},
        "usage": {"input_tokens": 100, "output_tokens": 25}}


@pytest.fixture
def model(monkeypatch):
    calls = []
    def post(self, payload):
        request = json.loads(payload); calls.append(request)
        options = request['questions']['action']['criteria']
        command = request['state'].get('instruction', '')
        chosen = 'tool_rotate_Z_plus' if 'Rotate' in command else 'fixed_translate_Z_plus'
        if 'gripper' in command: chosen = 'gripper_open'
        if 'cup' in command: chosen = 'needs_perception'
        if 'request' in request['state']: chosen = 'hold'
        return answer(options, chosen)
    monkeypatch.setattr(TypeSafeClient, '_post', post)
    return calls


def test_units_frames_and_once_only_consumption(model):
    task = 'Move up 10 mm.\nRotate about tool Z by 5 degrees.\nOpen the gripper.'
    p = JevAgent(task, api_key='fixture-not-a-real-key')
    obs = observation()
    first = p.decide(task, obs, {'external': b'PRIVATE_IMAGE'}, [], [])
    assert first['delta_position'] == [0, 0, .01]
    obs['last_feedback'] = {'status': 'reached'}
    second = p.decide(task, obs, {}, [], [])
    assert second['delta_rotation'][0] == pytest.approx(math.radians(5))
    third = p.decide(task, obs, {}, [], [])
    assert third['kind'] == 'gripper' and p.commands_complete
    with pytest.raises(PolicyError): p.decide(task, obs, {}, [], [])
    assert len(model) == 3 and 'PRIVATE_IMAGE' not in json.dumps(model)
    assert all('observation_id' not in r['state'] for r in model)
    assert p.last_decision['explanation_source'] == 'program_template' if p.last_decision else True
    p.reset(); assert not p.commands_complete
    p.close()


@pytest.mark.parametrize('task', ['move 100 mm', 'move 1e3 mm', 'rotate 90 degrees',
    'move 10', 'move 5 mm and 6 mm', 'rotate 0 degrees'])
def test_unsupported_numeric_arguments_fail_before_api(task, model):
    p = JevAgent(task, api_key='fixture')
    with pytest.raises(PolicyError): p.decide(task, observation(), {}, [], [])
    assert not model


@pytest.mark.parametrize('extra', ['evaluation', 'object_pose', 'success'])
def test_privileged_observation_rejected(extra, model):
    p = JevAgent('Move up 10 mm', api_key='fixture')
    obs = observation(); obs[extra] = {'value': 1}
    with pytest.raises((ValueError, PolicyError)): p.decide(p.task, obs, {}, [], [])
    assert not model


def test_no_vision_is_reported_instead_of_inventing_coordinates(model):
    p = JevAgent('Pick up the cup.', api_key='fixture')
    with pytest.raises(PolicyError, match='视觉'): p.decide(p.task, observation(), {}, [], [])
    assert p.index == 0 and p.last_decision['choice'] == 'needs_perception'


def test_control_failure_does_not_request_another_decision(model):
    p = JevAgent('Move up 10 mm\nOpen the gripper', api_key='fixture')
    obs = observation(); p.decide(p.task, obs, {}, [], [])
    obs['last_feedback'] = {'status': 'timed_out'}
    with pytest.raises(PolicyError, match='上一条'): p.decide(p.task, obs, {}, [], [])
    assert len(model) == 1


@pytest.mark.parametrize('change', ['unknown_choice', 'missing_probability', 'nan', 'sum', 'not_argmax',
    'wrong_model', 'wrong_type', 'bad_confidence', 'extra_answer', 'bad_usage'])
def test_malformed_probability_responses_are_rejected(change):
    criteria = {'a': 'A', 'b': 'B'}; value = answer(criteria, 'a'); a = value['answers']['action']
    if change == 'unknown_choice': a['choice'] = 'c'
    if change == 'missing_probability': del a['probabilities']['b']
    if change == 'nan': a['probabilities']['a'] = float('nan')
    if change == 'sum': a['probabilities']['a'] = .5
    if change == 'not_argmax': a['choice'] = 'b'
    if change == 'wrong_model': value['model'] = 'jev-0.0.0'
    if change == 'wrong_type': a['type'] = 'noul'
    if change == 'bad_confidence': a['confidence'] = True
    if change == 'extra_answer': value['answers']['extra'] = a
    if change == 'bad_usage': value['usage']['input_tokens'] = -1
    with pytest.raises(PolicyError): validate_choice(value, criteria, DEFAULT_MODEL)


def test_diagnostic_uses_real_provider_contract_but_never_calls_control(model):
    p = JevAgent('diagnostic', api_key='fixture')
    result = p.diagnose('action', '', observation(), {'external': b'IMAGE'})
    assert result['executed'] is False and result['choice'] == 'hold'
    assert p.index == 0 and len(model) == 1 and 'IMAGE' not in json.dumps(model)


def test_missing_key_does_not_use_openai_credentials(monkeypatch):
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', 'unrelated-fixture')
    with pytest.raises(PolicyError, match='TYPESAFE_API_KEY'): TypeSafeClient()
