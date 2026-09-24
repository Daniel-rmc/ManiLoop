"""Real manual rotation through the shared runner, without a model or API."""
import math
import os
import numpy as np
import pytest
from maniloop.backends.factory import create_environment
from maniloop.controllers.geometry import rotation_matrix, rotation_vector
from maniloop.runtime.runner import EpisodeRunner


@pytest.mark.parametrize('backend,task,flag', [
    ('robosuite', 'Lift', 'MANILOOP_TEST_ROBOSUITE'),
    ('robocasa', 'OpenDrawer', 'MANILOOP_TEST_ROBOCASA'),
    ('libero', 'pick_place', 'MANILOOP_TEST_LIBERO'),
])
@pytest.mark.parametrize('reference', ['fixed', 'tool'])
def test_six_rotation_jogs_use_declared_axes_and_report_actual_tracking(backend, task, flag, reference, tmp_path):
    if os.environ.get(flag) != '1':
        pytest.skip('Optional real backend not enabled')
    env = create_environment(backend=backend, task=task, observation_profile='debug_rgb128')
    env.set_llm_control('tcp_target_servo_v2')
    runner = EpisodeRunner(env, output=tmp_path)
    try:
        for axis in range(3):
            for sign in (1, -1):
                before, _ = env.observe()
                position = np.array(before['tcp_position'])
                r = np.array(before['tcp_rotation_matrix'])
                delta = np.zeros(3); delta[axis] = sign * math.radians(5)
                target = r @ rotation_matrix(delta) if reference == 'tool' else rotation_matrix(delta) @ r
                runner.command('manual', dict(delta_position=[0, 0, 0],
                    delta_rotation=delta.tolist(), reference_frame=reference))
                assert env.feedback['status'] == 'accepted'
                for _ in range(65):
                    if not env.busy:
                        break
                    runner.advance(.05)
                after, images = env.observe()
                error = np.linalg.norm(rotation_vector(target @ np.array(after['tcp_rotation_matrix']).T))
                drift = np.linalg.norm(np.array(after['tcp_position']) - position)
                # Check direction and truthful tracking, not ideal rigid kinematics.
                # The explicit 3-second manual target budget can time out on a rotation.
                actual = rotation_vector(np.array(after['tcp_rotation_matrix']) @ r.T)
                expected_axis = r @ delta if reference == 'tool' else delta
                assert np.dot(actual, expected_axis) > 0, (backend, reference, axis, sign)
                assert env.feedback['rotation_error_rad'] == pytest.approx(error, abs=1e-6)
                assert env.feedback['position_error_m'] == pytest.approx(drift, abs=1e-8)
                assert env.feedback['status'] in ('reached', 'timed_out')
                if env.feedback['status'] == 'reached':
                    assert error < .02 and drift < .002
                else:
                    assert env.feedback['control_steps'] == 60
                print(backend, reference, axis, sign, env.feedback['status'],
                      'rotation_error_deg=', math.degrees(error), 'position_error_mm=', drift * 1000)
                assert set(images) == {'external', 'wrist'}
                clock = env.simulation_time
                runner.advance(.5)
                assert env.simulation_time == clock
        assert runner.api_calls == 0
    finally:
        runner.close()
