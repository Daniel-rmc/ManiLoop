"""One entry point for interactive debugging, offline checks and batch experiments."""

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
from maniloop.evaluation.benchmark import Experiment, load_suite, run_episode
from maniloop.backends.factory import create_environment, options_from_args


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="maniloop", description="MuJoCo × LLM manipulation experiments"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    chat = commands.add_parser("chat", help="Text-only API connection workbench (no simulation)")
    chat.add_argument("--port", type=int, default=8769)
    chat.add_argument("--model", default=None)
    listing = commands.add_parser("list", help="List bundled components")
    demo = commands.add_parser("demo", help="Local web debugging")
    smoke = commands.add_parser("smoke", help="Render cameras without a model request")
    batch = commands.add_parser("benchmark", help="Fixed-policy episode or TOML matrix")
    for p in (listing, demo, smoke, batch):
        p.add_argument("--backend", choices=["mujoco", "libero", "robosuite"], default="mujoco")
        p.add_argument("--libero-suite", default="libero_spatial")
        p.add_argument("--libero-task-id", type=int, default=0)
        p.add_argument("--init-state-id", type=int, default=0)
    for p in (demo, smoke, batch):
        p.add_argument("--robot", choices=["arx5", "panda"], default=None)
        p.add_argument(
            "--scene", choices=["tabletop_a", "tabletop_b"], default="tabletop_a"
        )
        p.add_argument("--task", default="pick_place", help="Task ID; validated by the selected backend")
        p.add_argument(
            "--output",
            type=Path,
            default=Path("runs") if p != smoke else Path("artifacts"),
        )
    for p in (demo, batch):
        p.add_argument(
            "--timing", choices=["controlled", "realtime"], default="controlled"
        )
        p.add_argument("--model", default=None)
        p.add_argument("--codex-login", action="store_true", help="Use the official Codex CLI's ChatGPT login; no API key")
    demo.add_argument("--port", type=int, default=8765)
    for p in (demo, batch):
        p.add_argument("--llm-control", choices=["tcp_target_servo_v2", "osc_step"], default="tcp_target_servo_v2")
        p.add_argument("--observation-profile", choices=["llm_rgb512", "debug_rgb128"], default="llm_rgb512")
    batch.add_argument("--request-timeout-seconds", type=float, default=120)
    batch.add_argument("--context-mode", choices=["current", "paired"], default="current")
    batch.add_argument("--record-episode", action="store_true", help="Record every real LIBERO control-step frame; requires controlled timing")
    batch.add_argument("--reasoning-effort", choices=["auto", "low", "medium", "high", "xhigh"], default="auto")
    batch.add_argument(
        "--suite", type=Path, help="Experiment matrix TOML (contains no credentials)"
    )
    batch.add_argument("--agent", choices=["mock_vla", "llm_cloud", "lerobot"], default="mock_vla")
    batch.add_argument("--local-model", choices=["smolvla-libero", "act-libero", "diffusion-libero"], default="smolvla-libero")
    batch.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    batch.add_argument("--seed", type=int, default=0)
    batch.add_argument("--max-calls", type=int, default=30, help="Decision budget; 0 disables this limit (simulation and wall-time limits remain)")
    batch.add_argument("--max-sim-seconds", type=float, default=120.0)
    batch.add_argument("--max-wall-seconds", type=float, default=600.0)
    batch.add_argument(
        "--provider-config",
        type=Path,
        help="Provider TOML/JSON or CC Switch DB; key may use OPENAI_API_KEY",
    )
    batch.add_argument(
        "--no-render", action="store_true", help="Only for offline mock adapter checks"
    )
    args = parser.parse_args(argv)
    if args.command == "chat":
        from maniloop.ui.server import serve_chat
        serve_chat(args)
    elif args.command == "list" and args.backend == "libero":
        from maniloop.backends.libero.transport import list_tasks

        print(json.dumps(list_tasks(args.libero_suite), ensure_ascii=False, indent=2))
    elif args.command == "list" and args.backend == "robosuite":
        from maniloop.backends.robosuite.catalog import list_tasks
        print(json.dumps({"backend": "robosuite", "tasks": list_tasks(),
                          "setup": "python scripts/setup_robosuite.py"}, ensure_ascii=False, indent=2))
    elif args.command == "list":
        print(
            json.dumps(
                {
                    "robots": ["arx5", "panda"],
                    "scenes": ["tabletop_a", "tabletop_b"],
                    "tasks": ["pick_place", "push"],
                    "agents": ["llm_cloud", "mock_vla"],
                    "representations": ["rgbd_proprio_v1"],
                    "controllers": ["position_v1"],
                },
                indent=2,
            )
        )
    elif args.command == "demo":
        from maniloop.ui.server import serve

        serve(args)
    elif args.command == "smoke":
        sim = create_environment(**options_from_args(args))
        try:
            sim.step(2 if args.backend in ("libero", "robosuite") else 500)
            observation, images = sim.observe()
            destination = (
                args.output
                / sim.backend
                / sim.robot_name
                / sim.scene_name
                / sim.task_name
            )
            destination.mkdir(parents=True, exist_ok=True)
            for camera, data in images.items():
                (destination / f"{camera}.jpg").write_bytes(data)
            (destination / "observation.json").write_text(
                json.dumps(observation, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "robot": sim.robot_name,
                        "backend": sim.backend,
                        "cameras": list(images),
                        "output": str(destination),
                    }
                )
            )
        finally:
            sim.close()
    else:
        import os

        cases = (
            load_suite(args.suite)
            if args.suite
            else [
                Experiment(
                    backend=args.backend,
                    libero_suite=args.libero_suite,
                    libero_task_id=args.libero_task_id,
                    init_state_id=args.init_state_id,
                    robot=args.robot,
                    scene=args.scene,
                    task=args.task,
                    agent=args.agent,
                    local_model=args.local_model,
                    device=args.device,
                    timing=args.timing,
                    llm_control=args.llm_control, observation_profile=args.observation_profile,
                    request_timeout_seconds=args.request_timeout_seconds, reasoning_effort=args.reasoning_effort,
                    context_mode=args.context_mode,
                    record_episode=args.record_episode,
                    seed=args.seed,
                    max_calls=args.max_calls,
                    max_sim_seconds=args.max_sim_seconds,
                    max_wall_seconds=args.max_wall_seconds,
                )
            ]
        )
        if args.suite and args.record_episode:
            cases = [replace(case, record_episode=True) for case in cases]
        connection = {
            "credential_source": "codex" if args.codex_login else "file" if args.provider_config else "manual",
            "config_path": str(args.provider_config) if args.provider_config else None,
            "api_key": None if args.codex_login else os.environ.get("OPENAI_API_KEY"),
            "model": args.model,
        }
        args.output.mkdir(parents=True, exist_ok=True)
        failed = False
        summary = args.output / (
            "summary-" + __import__("uuid").uuid4().hex[:8] + ".jsonl"
        )
        for case in cases:
            result = run_episode(
                case, args.output, connection, render=not args.no_render
            )
            with summary.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(result, ensure_ascii=False) + "\n")
            failed |= result["phase"] == "error"
            print(
                json.dumps(
                    {
                        "backend": result["environment"]["backend"],
                        "robot": result["environment"]["robot"],
                        "scene": result["environment"]["scene"],
                        "task": result["environment"]["task"],
                        "phase": result["phase"],
                        "success": result["evaluation"]["success"],
                        "is_mock": result["is_mock"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        print(f"Results: {summary}")
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
