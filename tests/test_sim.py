"""Physics/geometry tests use no API. Scripted fixture motion is only a test oracle."""
import time
import numpy as np
import pytest
from arx5_demo.sim import RobotSim

@pytest.fixture
def sim():
    s=RobotSim(render=False)
    yield s
    s.close()


def move_to(sim,target):
    for _ in range(30):
        delta=np.array(target)-sim.tcp_position
        if np.linalg.norm(delta)<.002:
            return
        delta*=min(1,.035/np.linalg.norm(delta))
        result=sim.execute({'kind':'move','delta_position':delta.tolist(),'gripper_opening':0})
        assert result['status']=='accepted', result
        sim.step(750)
    pytest.fail('Controller did not reach target')


def test_hold_and_small_action_preserves_gripper(sim):
    home=sim.tcp_position
    sim.step(1500)
    np.testing.assert_allclose(sim.tcp_position,home,atol=.001)
    result=sim.execute({'kind':'move','delta_position':[0,0,-.02],'gripper_opening':0})
    assert result['status']=='accepted'
    sim.step(800)
    np.testing.assert_allclose(sim.tcp_position,home+[0,0,-.02],atol=.002)
    assert sim.gripper_opening>.98  # unused schema field must not close gripper


@pytest.mark.parametrize('payload',[
    {'delta_position':[.2,0,0]}, {'delta_rotation':[0,0,.3]},
    {'delta_position':[float('nan'),0,0]}, {'delta_position':[1,2]},
    {'kind':'gripper','gripper_opening':2}, {'kind':'arbitrary_code'},
])
def test_reject_without_motion(sim,payload):
    ctrl=sim.data.ctrl.copy()
    assert sim.execute(payload)['status']=='rejected'
    np.testing.assert_array_equal(sim.data.ctrl,ctrl)
    assert sim.trajectory is None


def test_public_observation_and_staleness(sim):
    o,_=sim.observe()
    assert set(o).isdisjoint({'object_pose','cube_position','evaluation','contacts','success','target_center'})
    assert sim.validate_snapshot(o)[0]
    old=dict(o,timestamp_monotonic=time.monotonic()-100)
    assert not sim.validate_snapshot(old,max_age=60)[0]
    sim.reset(7)
    assert not sim.validate_snapshot(o)[0]


def test_depth_query_uses_calibrated_pixels_not_object_pose(sim):
    o,_=sim.observe()
    sim._snapshot['depth']=np.full((480,640),.6)
    query={'observation_id':o['observation_id'],'camera':'external','pixel':[320,240]}
    result=sim.depth_query(query)
    assert result['valid']
    k=o['cameras']['external']['intrinsics']
    local=[(320-k['cx'])*.6/k['fx'],-(240-k['cy'])*.6/k['fy'],-.6]
    expected=np.array(o['cameras']['external']['position_in_base'])+np.array(o['cameras']['external']['rotation_in_base'])@local
    np.testing.assert_allclose(result['position_in_base'],expected)
    assert not sim.depth_query(dict(query,camera='wrist'))['valid']
    assert not sim.depth_query(dict(query,pixel=[640,0]))['valid']


def test_contact_grasp_transport_release_and_independent_success(sim):
    # This deterministic test is NOT the GPT policy and never runs from the task UI.
    assert sim.model.neq == 0  # no weld, attachment or teleportation during manipulation
    move_to(sim,[.30,-.06,.021])
    assert sim.execute({'kind':'gripper','gripper_opening':0})['status']=='accepted'
    sim.step(700)
    move_to(sim,[.30,-.06,.15])
    assert sim.data.body('red_cube').xpos[2]>.10  # physically held above table
    move_to(sim,[.31,.10,.15])
    move_to(sim,[.31,.10,.025])
    sim.execute({'kind':'gripper','gripper_opening':1})
    sim.step(600)
    move_to(sim,[.31,.10,.15])
    sim.evaluation()
    sim.step(700)
    assert sim.evaluation()['success']
