"""Compare LIBERO step commands with proprioceptive target feedback; no model API."""

import argparse
import json
from pathlib import Path

import numpy as np
from maniloop.backends.libero import LiberoEnvironment


def run_case(env, mode):
    env.reset(0)
    observation, _ = env.observe()
    start = np.array(observation["tcp_position"])
    offset = np.array([0.0, 0.0, 0.01])
    target = start + offset
    steps = 1 if mode == "single_control_step" else 20
    for index in range(steps):
        if mode == "proprio_target_servo_20":
            delta = target - env.tcp_position
        else:
            delta = offset if index == 0 else np.zeros(3)
        result = env.execute(
            dict(kind="move", frame="world", delta_position=delta.tolist(),
                 delta_rotation=[0, 0, 0])
        )
        if result["status"] != "accepted":
            raise RuntimeError(result["message"])
        env.step()
    return {
        "mode": mode,
        "requested_z_mm": 10,
        "control_steps": steps,
        "simulation_seconds": env.simulation_time,
        "measured_delta_mm": ((env.tcp_position - start) * 1000).round(4).tolist(),
        "position_error_mm": round(float(np.linalg.norm(target - env.tcp_position) * 1000), 4),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/diagnostics/libero-control.json"))
    args = parser.parse_args()
    env = LiberoEnvironment(render=False, suite="libero_spatial", task_id=0, init_state_id=0)
    try:
        result = {
            "scope": "Sensor-only controller diagnostic, not model inference or task success",
            "suite": "libero_spatial", "task_id": 0, "init_state_id": 0, "seed": 0,
            "records": [run_case(env, mode) for mode in (
                "single_control_step", "single_then_zero_19", "proprio_target_servo_20"
            )],
        }
    finally:
        env.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
