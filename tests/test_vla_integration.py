"""Opt-in REAL checkpoint inference; requires all reviewed models and LIBERO.

MANILOOP_TEST_VLA=1 enables this separate layer. Simulator-only tests do not
validate a learned policy. No cloud provider, model downloads or API keys.
"""
import io
import json
import os
import numpy as np
from PIL import Image
import pytest
from maniloop.agents.lerobot import LeRobotAgent
from maniloop.agents.lerobot.catalog import MODELS
from maniloop.backends.factory import create_environment

pytestmark = pytest.mark.skipif(os.environ.get('MANILOOP_TEST_VLA') != '1',
                               reason='Optional inference runtime/checkpoints and LIBERO required')


@pytest.mark.parametrize('model', list(MODELS))
def test_actual_local_checkpoint_controls_libero(model, tmp_path):
    env = create_environment(backend='libero', observation_profile='lerobot_rgb256')
    agent = None
    try:
        agent = LeRobotAgent(model=model, device='auto')
        agent.reset(0)
        assert agent.metadata['strict_weights'] is True
        assert agent.metadata['revision'] == MODELS[model]['revision']
        assert agent.metadata['actual_state_dimension'] == 8
        steps, inferences, actions = 4, 0, []
        before, _ = env.observe()
        for _ in range(steps):
            observation, images = env.observe()
            assert set(images) == {'external', 'wrist'}
            assert all(Image.open(io.BytesIO(data)).size == (256, 256) for data in images.values())
            chunk = agent.decide(env.instruction, observation, images, [], [])
            chunk.validate()
            assert chunk.observation_id == observation['observation_id']
            assert len(chunk.actions) == 1 and chunk.interval_seconds == .05
            values = chunk.actions[0].values
            assert len(values) == 7 and np.isfinite(values).all() and max(map(abs, values)) <= 1
            actions.append(list(values)); inferences += agent.last_usage['model_inferences']
            executor = env.create_chunk_executor(chunk)
            assert executor.tick()['status'] == 'accepted'
            env.step()
        after, _ = env.observe()
        assert inferences >= 1 and env.simulation_time == pytest.approx(steps * .05)
        assert not np.allclose(before['joint_positions'], after['joint_positions'], atol=1e-6)
        report = {'model':model, 'device':agent.metadata['device'], 'strict_weights':True,
                  'control_steps':steps, 'model_inferences':inferences, 'actions':actions,
                  'weight_sha256':agent.metadata['weight_sha256'], 'evaluation':env.evaluation(),
                  'external_api_calls':0, 'is_mock':False}
        (tmp_path/'inference.json').write_text(json.dumps(report, indent=2))
        print(json.dumps({k:v for k,v in report.items() if k != 'actions'}))
    finally:
        if agent is not None: agent.close()
        env.close()
