"""Opt-in real upstream checks: MANILOOP_TEST_LIBERO=1; no cloud API calls."""

import io
import os
import numpy as np
from PIL import Image
import pytest
from maniloop.backends.libero import LiberoEnvironment
from maniloop.backends.libero.transport import list_tasks, SUITES

pytestmark = pytest.mark.skipif(
    os.environ.get("MANILOOP_TEST_LIBERO") != "1",
    reason="Optional LIBERO runtime and graphics required",
)


@pytest.fixture(scope="module")
def official():
    env = LiberoEnvironment()
    yield env
    env.close()


def test_official_reset_images_native_motion_and_scoring(official):
    official.reset(7)
    before, images = official.observe()
    assert set(images) == {"external", "wrist"}
    for value in images.values():
        rgb = np.asarray(Image.open(io.BytesIO(value)))
        assert rgb.shape == (128, 128, 3) and rgb.std() > 10
    official.reset(7)
    again, _ = official.observe()
    np.testing.assert_allclose(
        before["joint_positions"], again["joint_positions"], atol=1e-7
    )
    np.testing.assert_allclose(before["tcp_position"], again["tcp_position"], atol=1e-7)
    for _ in range(10):
        result = official.execute(
            dict(kind="move", frame="world", delta_position=[0, 0, 0.005])
        )
        assert result["status"] == "accepted"
        official.step()
    after, _ = official.observe()
    assert after["tcp_position"][2] > again["tcp_position"][2] + 0.005
    assert official.simulation_time == 0.5
    evaluation = official.evaluation()
    assert (
        evaluation["evaluator"] == "libero_check_success" and not evaluation["success"]
    )
    assert "success" not in after and "object-state" not in after
    assert official.describe()["paper_comparable"] is False


@pytest.mark.parametrize("suite", SUITES)
def test_official_task_catalog(suite):
    tasks = list_tasks(suite)
    assert len(tasks) == (90 if suite == "libero_90" else 10)
    assert all(task["id"] == i and task["instruction"] for i, task in enumerate(tasks))


def test_learned_policy_observation_profile():
    with_profile = LiberoEnvironment(observation_profile="lerobot_rgb256")
    try:
        packet, images = with_profile.observe()
        assert len(packet["tcp_quaternion_xyzw"]) == 4
        assert len(packet["gripper_joint_positions"]) == 2
        assert with_profile.describe()["observation_profile"] == "lerobot_rgb256"
        for data in images.values():
            assert data.startswith(b"\x89PNG")
            assert Image.open(io.BytesIO(data)).size == (256, 256)
        assert not {"object-state", "success", "contacts"}.intersection(packet)
    finally:
        with_profile.close()
