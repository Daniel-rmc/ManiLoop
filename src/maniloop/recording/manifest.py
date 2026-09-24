"""Public provenance only. Credential values and private config paths are never recorded."""

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
from maniloop import __version__


def source_digest():
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".xml", ".json", ".html", ".js", ".css"}:
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def describe_run(runner):
    sim = runner.sim
    implementation = source_digest()
    policy = {
        "implementation_sha256": implementation,
        "kind": runner.policy_kind,
        "model": runner.model,
        "representation": (
            ("libero_rgb512_proprio_v2" if sim.describe().get("observation_profile") == "llm_rgb512" else "libero_rgb_proprio_v1")
            if sim.backend == "libero"
            else runner.representation.name
        ),
        "controller": sim.describe()["controller"],
        "backend_protocol": sim.describe()["protocol"],
        "action_interface": (
            ("libero_osc_chunk_v1" if sim.backend == "libero" else "joint_chunk_v1")
            if runner.policy_kind in ("mock_vla", "lerobot")
            else (
                "libero_tcp_to_osc_v1"
                if sim.backend == "libero"
                else "tcp_step_depth_v1"
            )
        ),
        "timing": runner.timing,
        "memory": "reset_per_episode",
        "context_mode": runner.context_mode,
        "feedback_protocol": "sensor_transition_v1" if runner.context_mode == "paired" else "action_feedback_v1",
        "initial_cadence": "single_step" if runner.single_step else "continuous",
        "human_pause_budget": "wall_clock_includes_pauses",
        "observation_max_age": runner.max_age if runner.timing == "realtime" and runner.max_age > 0 else None,
        "configured_observation_max_age_seconds": runner.max_age,
        "snapshot_identity_validation": "always",
        "endpoint": (
            runner.credentials["base_url"]
            if runner.policy_kind == "llm_cloud"
            else None
        ),
        "cameras_rendered": sim.render_enabled,
        "max_decisions": runner.max_steps or None,
        "max_sim_seconds": runner.sim_budget,
        "max_wall_seconds": runner.wall_budget,
    }
    if sim.backend == "libero":
        info = sim.describe()
        policy["backend_revision"] = info["upstream_revision"]
        policy["controller_config"] = info["controller_config"]
        policy["runtime_dependencies"] = info["runtime_dependencies"]
        policy["camera_preprocessing"] = info["camera_preprocessing"]
    if sim.backend == "robosuite":
        info = sim.describe()
        policy["representation"] = info["protocol"]
        policy["action_interface"] = (
            "robosuite_osc_chunk_v1" if runner.policy_kind == "mock_vla"
            else "robosuite_tcp_target_servo_v1" if info.get("llm_control") == "tcp_target_servo_v2"
            else "robosuite_tcp_to_osc_v1")
        for key in ("controller_config", "runtime_dependencies", "camera_preprocessing",
                    "upstream_revision", "upstream_source_sha256", "controller_overrides"):
            policy[key] = info[key]
        if info.get("llm_control") == "tcp_target_servo_v2":
            policy["target_controller"] = info["target_controller"]
    if sim.backend == "robocasa":
        info = sim.describe()
        policy["representation"] = info["protocol"]
        policy["action_interface"] = "robocasa_world_arm_subset_v1"
        for key in ("controller_config", "runtime_dependencies", "camera_preprocessing",
                    "upstream_revision", "upstream_source_sha256", "robosuite_source",
                    "robosuite_source_sha256", "action_adapter", "control_scope"):
            policy[key] = info[key]
        if info.get("llm_control") == "tcp_target_servo_v2":
            policy["action_interface"] = "robocasa_world_arm_target_servo_v1"
            policy["target_controller"] = info["target_controller"]
    if runner.policy_kind == "lerobot":
        policy["learned_policy"] = runner.policy.metadata
        policy["action_interface"] = "lerobot_select_action_osc_20hz_v1"
    if runner.policy_kind == "llm_cloud":
        effective = getattr(runner.policy, "request_options", None)
        policy["request_options"] = effective if isinstance(effective, dict) else {"source": "unavailable_adapter"}
        if sim.backend == "libero" and sim.describe().get("llm_control") == "tcp_target_servo_v2":
            policy["action_interface"] = "tcp_target_servo_v2"
            policy["target_controller"] = sim.describe()["target_controller"]
    if runner.policy_kind == "jev":
        policy.update(action_interface="jev_primitives_v1", representation="text_proprioception_v1",
                      endpoint="https://api.typesafe.ai/v1/systemone",
                      request_options=runner.policy.request_options, images_sent_to_policy=False,
                      completion_semantics="input_sequence_consumed_not_task_success")
    policy["diagnostic_stage"] = runner.diagnostic_stage
    # Robot/task/seed remain separate axes in the results. Different policy assistance or
    # timing/budget settings produce different comparison groups.
    group = hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()[:16]
    return {
        "schema_version": 1,
        "version": __version__,
        "source_sha256": implementation,
        "mode": "connection_diagnostic" if runner.diagnostic_stage else "fixed_policy_evaluation" if runner.benchmark else "interactive_debug",
        "robot": sim.robot_name,
        "scene": sim.scene_name,
        "task": sim.task_name,
        "seed": runner.seed,
        "instruction": runner.task,
        "policy": policy,
        "comparison_group": group,
        "is_mock": runner.policy_kind == "mock_vla",
        **sim.describe(),
        "executed_instruction": runner.task,
        "official_instruction": sim.instruction,
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("mujoco", "numpy", "Pillow", "openai")
        },
    }
