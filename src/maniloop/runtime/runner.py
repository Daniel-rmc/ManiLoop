"""Local browser UI, real-time physics and one-request-at-a-time GPT loop."""

from __future__ import annotations
from dataclasses import asdict
from copy import deepcopy
from maniloop.core.observations import paired_sensors, guard_sensor_tree
from maniloop.core.actions import Action, ActionChunk
from maniloop.backends.base import Environment
from maniloop.agents.mock_vla import MockVLAAgent
from maniloop.representations.sensors import SensorRepresentation
import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import signal
import threading
import time
from urllib.parse import urlparse

import numpy as np
from PIL import Image
import io

from maniloop.backends.factory import create_environment
from maniloop.agents.llm import LLMAgent as GPTPolicy
from maniloop.providers.responses import DEFAULT_MODEL
from maniloop.recording.manifest import describe_run
from maniloop.providers.credentials import (
    CredentialConfig,
    ConfigError,
    discover_configs,
    load_local_config,
    load_toml_config,
    normalize_base_url,
)
from maniloop.providers.catalog import fetch_models, ModelCatalogError

ROOT = Path.cwd()


class EpisodeRunner:
    def __init__(
        self,
        sim: Environment,
        model=None,
        *,
        timing="controlled",
        output=None,
        benchmark=False,
    ):
        if timing not in ("controlled", "realtime"):
            raise ValueError("Unknown timing mode")
        self.sim = sim
        self.timing = timing
        self.output = Path(output) if output else None
        self.benchmark = benchmark
        self.representation = SensorRepresentation()
        self.chunk = None
        self.policy_kind = "llm_cloud"
        self.sim_budget = 120.0
        self.wall_budget = 600.0
        self.started_wall = None
        self.started_sim = float(sim.simulation_time)
        self._last_wall = time.monotonic()
        self._physics_remainder = 0.0
        self.seed = 0
        self.model = model or os.environ.get("OPENAI_MODEL") or "gpt-6-astra"
        self.default_model = self.model
        self.manual_base_url = None
        self.key = os.environ.get("OPENAI_API_KEY", "")
        self.manual_key = self.key
        self.credential_source = "manual"
        self.config_path = None
        self.config_key_override = None
        self.config_key_base_url = None
        self.model_override = None
        self.credential_fingerprint = None
        self.credentials = {
            "source": "manual",
            "path": "",
            "provider": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "model": self.model,
            "key_configured": bool(self.key),
            "models": [self.model],
            "error": "",
        }
        self.commands = queue.Queue()
        self.lock = threading.RLock()
        self.images = {}
        self.state = {}
        self.events = []
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gpt")
        self.future = None
        self.running = False
        self.paused = False
        self.pause_requested = False
        self.single_step = False
        self.context_mode = "current"
        self.last_transition = None
        self.transition_before = None
        self.replay_frames = []
        self.replay_html = b""
        self._review_signature = None
        self.termination_reason = None
        self.phase = "ready"
        self.error = ""
        self.task = ""
        self.max_steps = 30
        self.api_calls = 0
        self.step_count = 0
        self.history = []
        self.geometry = []
        self.last_action = None
        self.pending_observation, self.request_images = sim.observe()
        self.api_latency = None
        self.policy = None
        self.request_options = {}
        self.diagnostic_stage = None
        self.diagnostic_result = None
        self.awaiting_execution = False
        self.token = 0
        self.future_token = -1
        self.log_file = None
        self.next_request = 0.0
        self.max_age = float(os.environ.get("ARX_OBSERVATION_MAX_AGE", "60"))
        self.event("info", f"{sim.robot_name} 场景已准备；输入任务后开始闭环")

    def event(self, kind, message, **details):
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "type": kind,
            "message": message,
            **details,
        }
        self.events.append(entry)
        self.events = self.events[-120:]
        if self.log_file:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, allow_nan=False) + "\n")

    def stop(self, message="任务已停止", reason="user_stop"):
        if not self.running and self.log_file and self.termination_reason:
            # A completed run is immutable even if Stop/Reset is sent again.
            self.update_review()
            self.sim.hold()
            return
        self.running = False
        self.paused = self.pause_requested = False
        self.chunk = None
        self.awaiting_execution = False
        self.phase = "stopped"
        self.termination_reason = reason
        self.token += 1
        if self.future is not None and hasattr(self.policy, "cancel"):
            self.policy.cancel()
        self.sim.hold()
        self.event("info", message)
        self.update_review()

    def update_review(self):
        """Human-only artifact: never used to build a policy request."""
        if not self.log_file:
            return
        signature = (self.api_calls, self.step_count, self.phase, self.termination_reason)
        if signature == self._review_signature:
            return
        from maniloop.recording.replay import render_replay
        # A human review must not replace the synchronized policy snapshot or
        # invalidate a pending depth query. Use only read-only sensor properties.
        images, _ = self.sim.render_images()
        observation = {"simulation_time": float(self.sim.simulation_time),
                       "frame_id": self.pending_observation.get("frame_id"),
                       "tcp_position": self.sim.tcp_position.tolist(),
                       "gripper_opening": self.sim.gripper_opening}
        summary = {"api_calls": self.api_calls, "step_count": self.step_count,
                   "termination_reason": self.termination_reason, "error": self.error,
                   "evaluation": self.sim.evaluation(), "paused": self.paused,
                   "phase": self.phase, "diagnostic_stage": self.diagnostic_stage,
                   "human_pause_used": getattr(self, "human_pause_used", False)}
        frames = self.replay_frames + [{"request_index": self.api_calls,
            "observation": paired_sensors(observation), "images": images, "phase": "final"}]
        # Read the complete event stream; the live panel deliberately keeps only 120 events.
        events = [json.loads(line) for line in self.log_file.read_text(encoding="utf-8").splitlines()]
        html = render_replay(manifest=self.manifest, frames=frames, events=events, summary=summary)
        (self.log_file.parent / "replay.html").write_bytes(html)
        (self.log_file.parent / "review-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        self.replay_html = html
        self._review_signature = signature

    def pause_at_boundary(self):
        if (self.running and self.pause_requested and self.future is None
                and self.chunk is None and not self.sim.busy and self.sim.settled):
            self.paused = True
            self.pause_requested = False
            self.phase = "paused"
            self.event("pause", "已在动作结束处暂停；继续前不再调用模型")
            self.update_review()

    def finish_transition(self):
        if self.transition_before is None:
            return
        before, images, action, request_index = self.transition_before
        after, after_images = self.sim.observe()
        feedback = deepcopy(self.sim.feedback)
        guard_sensor_tree({"feedback": feedback})
        transition = {"protocol": "sensor_transition_v1", "request_index": request_index,
                      "before": paired_sensors(before), "action": action,
                      "feedback": feedback, "after": paired_sensors(after)}
        self.last_transition = (transition, images)
        if self.history and self.history[-1].get("action") == action:
            self.history[-1] = {"action": action, "feedback": feedback}
        self.replay_frames.append({"request_index": request_index,
            "observation": paired_sensors(after), "images": dict(after_images), "phase": "after"})
        self.event("transition", "动作前后传感证据已记录", transition=transition,
                   request_index=request_index)
        self.transition_before = None

    def resolve_connection(self, payload, *, allow_missing_key=False):
        source = payload.get("credential_source", "manual")
        if source == "file":
            path = payload.get("config_path") or None
            if path is not None and (not isinstance(path, str) or len(path) > 2048):
                raise ConfigError("配置文件路径无效")
            return load_local_config(
                path,
                api_key=payload.get("api_key"),
                allow_missing_key=allow_missing_key,
            )
        if source == "upload":
            return load_toml_config(
                payload.get("config_toml"),
                api_key=payload.get("api_key"),
                name=payload.get("config_name") or "config.toml",
                allow_missing_key=allow_missing_key,
            )
        if source != "manual":
            raise ConfigError("请选择本地配置、导入 TOML 或手动密钥")
        key = payload.get("api_key") or self.manual_key
        if not isinstance(key, str) or not key.strip():
            raise ValueError("尚未配置 OPENAI_API_KEY，请选择本地配置文件或输入密钥")
        key = key.strip()
        base = normalize_base_url(
            payload.get("base_url")
            or self.manual_base_url
            or os.environ.get("OPENAI_BASE_URL")
        )
        fingerprint = hashlib.sha256(json.dumps([key, base]).encode()).hexdigest()
        return CredentialConfig(
            api_key=key,
            base_url=base,
            model=self.default_model,
            provider="手动配置",
            path="",
            fingerprint=fingerprint,
            models=(),
        )

    def activate_connection(self, config, model, source):
        policy = GPTPolicy(
            model=model, api_key=config.api_key, base_url=config.base_url,
            **({"request_options": self.request_options} if self.request_options else {}),
        )
        self.close_policy()
        self.policy = policy
        self.key = config.api_key
        self.model = model
        self.credential_fingerprint = config.fingerprint
        self.credentials = {
            "source": source,
            **config.public(),
            "model": model,
            "error": "",
        }

    def refresh_local_connection(self):
        """Reload the selected provider as one credential/endpoint/model bundle."""
        config = load_local_config(self.config_path, api_key=self.config_key_override)
        if self.config_key_override and config.base_url != self.config_key_base_url:
            raise ConfigError(
                "配置的 API 地址已切换。请为新供应商填写对应的 API Key 后重新开始。"
            )
        model = self.model_override or config.model or DEFAULT_MODEL
        changed = (
            config.fingerprint != self.credential_fingerprint or model != self.model
        )
        if changed:
            if self.benchmark:
                raise ConfigError(
                    "批量评测期间配置发生变化，当前 episode 已终止；请重新开始实验"
                )
            self.activate_connection(config, model, "file")
            self.geometry = []
            self.event(
                "config",
                "已重新读取本地配置，后续决策使用当前供应商",
                provider=config.provider,
                model=model,
            )
        return changed

    def connection_request(self, name, payload):
        # Called on an HTTP worker: listing models must never block physics.
        if payload.get("credential_source") == "codex":
            from maniloop.providers.codex import login_status
            status = login_status()
            public = {"source": "codex", "provider": "Codex · ChatGPT 登录",
                      "base_url": "", "path": "", "model": DEFAULT_MODEL,
                      "models": [DEFAULT_MODEL], "key_configured": status["logged_in"],
                      "error": "" if status["logged_in"] else status["message"], **status}
            return {"ok": status["logged_in"], "config": public, "models": [DEFAULT_MODEL]}
        if name == "config-preview":
            config = self.resolve_connection(
                {"credential_source": "file", **payload}, allow_missing_key=True
            )
            return {"ok": True, "config": config.public()}
        config = self.resolve_connection(payload)
        return {
            "ok": True,
            "models": fetch_models(config.api_key, config.base_url),
            "config": config.public(),
        }

    def command(self, name, payload):
        if name == "stop":
            self.stop()
        elif name in {"pause", "resume", "step"}:
            if not self.running or self.diagnostic_stage:
                raise ValueError("请先开始一个机器人演示")
            if self.policy_kind != "llm_cloud":
                raise ValueError("单步与暂停目前仅用于 LLM 演示")
            if name == "pause":
                self.human_pause_used = True
                self.pause_requested = not self.paused
                self.pause_at_boundary()
            else:
                if not self.paused:
                    raise ValueError("请等待当前动作完成并暂停")
                self.paused = False
                self.single_step = name == "step"
                self.pause_requested = False
                self.phase = "observing"
                self.event("resume", "执行下一次决策" if self.single_step else "恢复连续执行")
        elif name == "configure":
            if self.running or self.future is not None:
                raise ValueError("请先停止任务并等待请求结束")
            backend = payload.get("backend", self.sim.backend)
            replacement = create_environment(
                backend=backend,
                render=self.sim.render_enabled,
                robot=payload.get("robot", "panda" if backend == "libero" else "arx5"),
                scene=payload.get("scene", "tabletop_a"),
                task=payload.get("task_id", "pick_place"),
                libero_suite=payload.get("libero_suite", "libero_spatial"),
                libero_task_id=int(payload.get("libero_task_id", 0)),
                init_state_id=int(payload.get("init_state_id", 0)),
                observation_profile=payload.get("observation_profile", "debug_rgb128"),
            )
            timing = payload.get("timing", self.timing)
            if timing not in ("controlled", "realtime"):
                replacement.close()
                raise ValueError("未知时序模式")
            if self.log_file:
                self.update_review()
                self.log_file = None
            self.sim.close()
            self.sim = replacement
            self.timing = timing
            if self.sim.backend == "libero":
                self.sim.set_llm_control(payload.get("llm_control", "osc_step"))
            self.chunk = None
            self._physics_remainder = 0.0
            self.command("reset", {"seed": payload.get("seed", 0)})
        elif name == "reset":
            if self.log_file and not self.running:
                self.update_review()
                self.log_file = None
            self.stop("正在重置场景，旧请求返回后将被丢弃")
            self.log_file = None
            self.last_transition = self.transition_before = None
            self.seed = int(payload.get("seed", 0))
            self.sim.reset(self.seed)
            self.phase = "ready"
            self.diagnostic_stage = None
            self.diagnostic_result = None
            self.error = ""
            self.step_count = 0
            self.api_calls = 0
            self.last_action = None
            self.history = []
            self.geometry = []
            self.pending_observation, self.request_images = self.sim.observe()
            self.event("info", "场景已重置")
        elif name in ("start", "diagnose"):
            diagnostic = payload.get("stage") if name == "diagnose" else None
            if name == "diagnose" and diagnostic not in ("text", "vision", "action"):
                raise ValueError("诊断阶段必须为 text / vision / action")
            task = "Connection diagnostic; never execute actions" if diagnostic else str(payload.get("task", "")).strip()
            if not task or len(task) > 4000:
                raise ValueError("请输入1至4000字的任务")
            if self.running or self.future is not None or self.sim.busy:
                raise ValueError("已有任务或API请求尚未结束，请停止并等待请求返回")
            context_mode = payload.get("context_mode", "current")
            single_step = payload.get("single_step", False)
            if context_mode not in {"current", "paired"} or type(single_step) is not bool:
                raise ValueError("上下文模式或单步设置无效")
            if single_step and (diagnostic or payload.get("agent", "llm_cloud") != "llm_cloud"):
                raise ValueError("单步仅用于 LLM 操作演示")
            self.context_mode = context_mode
            self.single_step = single_step
            self.diagnostic_stage = diagnostic
            self.diagnostic_result = None
            if diagnostic and payload.get("agent", "llm_cloud") != "llm_cloud":
                raise ValueError("连接诊断仅适用于云端 LLM")
            if payload.get("agent") == "lerobot":
                from maniloop.agents.lerobot import LeRobotAgent

                if self.sim.backend != "libero" or not self.sim.render_enabled:
                    raise ValueError("本地模型需要 LIBERO 后端和相机渲染")
                max_steps = int(payload.get("max_steps", 500))
                if not 0 <= max_steps <= 1000:
                    raise ValueError("本地策略决策上限须为 0（不限次数）或 1 至 1000")
                if self.sim.describe().get("observation_profile") != "lerobot_rgb256":
                    info = self.sim.describe()
                    replacement = create_environment(
                        backend="libero",
                        libero_suite=info["suite"],
                        libero_task_id=info["task_id"],
                        init_state_id=info["init_state_id"],
                        observation_profile="lerobot_rgb256",
                    )
                    self.sim.close()
                    self.sim = replacement
                    self.event(
                        "info", "本地策略已从所选官方初始化重新开始，使用 256 像素相机"
                    )
                self.sim.set_llm_control("osc_step")
                self.sim.reset(self.seed)
                self.pending_observation, self.request_images = self.sim.observe()
                self._physics_remainder = 0.0
                self.close_policy()
                self.policy = LeRobotAgent(
                    model=payload.get("local_model", "smolvla-libero"),
                    device=payload.get("device", "auto"),
                )
                self.policy_kind = "lerobot"
                self.model = self.policy.metadata["repo"]
                self.credential_source = "local_policy"
                self.begin_episode(task, max_steps)
                return
            if payload.get("agent") == "mock_vla":
                if self.sim.backend == "libero":
                    self.sim.set_llm_control("osc_step")
                self.close_policy()
                self.policy = MockVLAAgent()
                self.policy_kind = "mock_vla"
                self.model = "mock-vla-plumbing-v1"
                self.credential_source = "mock"
                self.begin_episode(task, int(payload.get("max_steps", 30)))
                return
            self.policy_kind = "llm_cloud"
            source = payload.get("credential_source", "manual")
            config = None if source == "codex" else self.resolve_connection(payload)
            override = payload.get("model") or None
            if override is not None and (
                not isinstance(override, str)
                or not override.strip()
                or len(override) > 120
            ):
                raise ValueError("模型名称无效")
            override = override.strip() if override else None
            model = override or (config.model if config else None) or DEFAULT_MODEL
            max_steps = 1 if diagnostic else int(payload.get("max_steps", 30))
            if not 0 <= max_steps <= 100:
                raise ValueError("API调用上限须为0（不限次数）或1至100")
            options = payload.get("request_options", {})
            if type(options) is not dict:
                raise ValueError("请求设置必须是对象")
            self.request_options = dict(options)
            if source == "codex":
                from maniloop.providers.codex import CodexPolicy
                policy = CodexPolicy(model=model, request_options=self.request_options)
                self.close_policy()
                self.policy = policy
                self.key = ""
                self.model = model
                self.credentials = {"source": "codex", "provider": "Codex · ChatGPT 登录",
                    "path": "", "base_url": "", "model": model, "models": [model],
                    "key_configured": True, "error": ""}
            else:
                self.activate_connection(config, model, source)
            if not diagnostic and self.sim.backend == "libero":
                profile = payload.get("observation_profile", self.sim.describe().get("observation_profile", "debug_rgb128"))
                mode = payload.get("llm_control", self.sim.llm_control)
                if mode not in ("osc_step", "tcp_target_servo_v2"):
                    raise ValueError("未知 LLM 控制模式")
                if profile != self.sim.describe().get("observation_profile", "debug_rgb128"):
                    info = self.sim.describe()
                    replacement = create_environment(backend="libero", render=self.sim.render_enabled,
                        libero_suite=info["suite"], libero_task_id=info["task_id"],
                        init_state_id=info["init_state_id"], observation_profile=profile)
                    self.sim.close()
                    self.sim = replacement
                    self.sim.reset(self.seed)
                    self.event("info", "相机配置已切换，场景从所选初始化重新开始")
                self.sim.set_llm_control(mode)
            if not diagnostic and payload.get("reset_on_start", False):
                self.sim.reset(self.seed)
                self._physics_remainder = 0.0
            if not diagnostic:
                for key, attr in (("max_wall_seconds", "wall_budget"), ("max_sim_seconds", "sim_budget")):
                    if key in payload:
                        value = payload[key]
                        if type(value) not in (int, float) or not np.isfinite(value) or value <= 0:
                            raise ValueError("实验时间预算必须是正数")
                        setattr(self, attr, float(value))
            self.max_steps = max_steps
            self.credential_source = source
            self.config_path = config.path if source == "file" else None
            self.config_key_override = (
                (payload.get("api_key") or None) if source == "file" else None
            )
            self.config_key_base_url = (
                config.base_url if self.config_key_override else None
            )
            self.model_override = override
            if source == "manual":
                self.manual_key = config.api_key
                self.manual_base_url = config.base_url
            self.begin_episode(task, max_steps)
        elif name == "manual":
            if self.running or self.future is not None:
                raise ValueError("请先停止GPT任务并等待在途请求结束，再手动点动")
            self.diagnostic_stage = None
            result = self.sim.execute({"kind": "move", **payload})
            self.event("manual", result["message"], action=payload, feedback=result)
        else:
            raise ValueError("未知操作")

    def begin_episode(self, task, max_steps):
        limit = 1000 if self.policy_kind == "lerobot" else 100
        if type(max_steps) is not int or not 0 <= max_steps <= limit:
            raise ValueError(f"调用上限须为0（不限次数）或1至{limit}")
        if self.sim.terminated and not self.diagnostic_stage:
            self.sim.reset(self.seed)
            self._physics_remainder = 0.0
            self.event("info", "已结束场景已重置，随后才会请求模型")
        if hasattr(self.policy, "reset"):
            self.policy.reset(self.seed)
        self.max_steps = max_steps
        self.api_latency = None
        self.awaiting_execution = False
        self.paused = self.pause_requested = False
        self.human_pause_used = self.single_step
        self.last_transition = self.transition_before = None
        self.replay_frames = []
        self.replay_html = b""
        self._review_signature = None
        self.termination_reason = None
        self.task = task
        self.step_count = 0
        self.api_calls = 0
        self.history = []
        self.geometry = []
        self.chunk = None
        self.last_action = None
        self.error = ""
        self.running = True
        self.phase = "observing"
        self.token += 1
        self.next_request = 0.0
        self.started_wall = time.monotonic()
        self.started_sim = float(self.sim.simulation_time)
        run = (self.output or ROOT / "runs") / (
            time.strftime("%Y%m%d-%H%M%S") + "-" + __import__("uuid").uuid4().hex[:8]
        )
        run.mkdir(parents=True, exist_ok=False)
        self.log_file = run / "events.jsonl"
        self.manifest = describe_run(self)
        (run / "manifest.json").write_text(
            json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.event(
            "start", "开始任务", task=task, model=self.model, max_calls=max_steps or None
        )

    def advance(self, simulation_seconds=0.02):
        """Shared CLI/UI clock. Controlled inference freezes physics, including depth follow-ups."""
        now = time.monotonic()
        elapsed = min(0.2, now - self._last_wall)
        self._last_wall = now
        if self.running and self.started_wall is not None:
            diagnostic_timeout = getattr(self.policy, "request_options", {}).get("timeout_seconds", 120) if self.diagnostic_stage else 0
            wall_budget = diagnostic_timeout + 15 if self.diagnostic_stage else self.wall_budget
            if (
                now - self.started_wall >= wall_budget
                or self.sim.simulation_time - self.started_sim >= self.sim_budget
            ):
                reason = (
                    "wall_budget"
                    if now - self.started_wall >= wall_budget
                    else "simulation_budget"
                )
                self.stop("达到实验时间预算", reason=reason)
        if self.running and self.sim.terminated and not self.diagnostic_stage:
            self.stop("环境已结束", reason="environment_terminated")
        self.tick()
        if not self.running and self.log_file:
            self.update_review()
        if self.paused:
            self._physics_remainder = 0.0
            return
        if self.diagnostic_stage:
            return  # Diagnostics never advance physics, including realtime mode.
        if (
            self.timing == "controlled"
            and self.running
            and (self.future is not None or self.geometry)
        ):
            return
        if (
            getattr(self.sim, "pause_when_idle", False)
            and not self.running
            and not self.sim.busy
        ):
            self._physics_remainder = 0.0
            return
        duration = elapsed if self.timing == "realtime" else simulation_seconds
        self._physics_remainder += duration
        count = int((self._physics_remainder + 1e-12) / self.sim.timestep)
        self._physics_remainder -= count * self.sim.timestep
        for _ in range(count):
            if (
                self.running
                and self.started_wall is not None
                and self.sim.simulation_time - self.started_sim >= self.sim_budget
            ):
                self.stop("达到仿真时间预算", reason="simulation_budget")
                break
            if self.chunk is not None:
                result = self.chunk.tick()
                if result:
                    if result["status"] == "accepted":
                        self.step_count += 1
                    self.event("chunk_sample", result["message"], feedback=result)
                    self.history.append({"feedback": result})
                    self.history = self.history[-8:]
                if self.chunk.completed:
                    self.chunk = None
                    self.phase = "executing"
                    if self.sim.backend == "libero":
                        break
            self.sim.step()
            if self.running and self.sim.terminated:
                self.stop("环境已结束", reason="environment_terminated")
                break

    def close_policy(self):
        policy, self.policy = self.policy, None
        if policy is not None and hasattr(policy, "close"):
            policy.close()
        elif policy is not None and hasattr(policy, "client"):
            policy.client.close()

    def close(self):
        self.running = False
        self.chunk = None
        self.token += 1
        self.close_policy()
        self.pool.shutdown(wait=True, cancel_futures=True)
        self.sim.close()

    def _visual_changed(self, old_images, new_images):
        # A conservative image-change heuristic, not object recognition or a safety guarantee.
        if "external" not in old_images or "external" not in new_images:
            return False
        a = np.asarray(
            Image.open(io.BytesIO(old_images["external"])).resize((160, 120)),
            dtype=float,
        )
        b = np.asarray(
            Image.open(io.BytesIO(new_images["external"])).resize((160, 120)),
            dtype=float,
        )
        return float(np.mean(np.max(np.abs(a - b), axis=2) > 45)) > 0.003

    def tick(self):
        while True:
            try:
                name, payload, done = self.commands.get_nowait()
            except queue.Empty:
                break
            try:
                self.command(name, payload)
                done.put({"ok": True, "task_instruction": self.sim.instruction})
            except Exception as exc:
                message = str(exc)
                self.event("error", message)
                done.put({"ok": False, "error": message})
        if self.awaiting_execution and not self.sim.busy:
            self.awaiting_execution = False
            feedback = dict(self.sim.feedback)
            self.event("execution", feedback["message"], feedback=feedback, request_index=self.api_calls)
        if self.transition_before is not None and not self.sim.busy and self.sim.settled:
            self.finish_transition()
        self.pause_at_boundary()
        # Never schedule a second request until the first has returned, even after stop/reset.
        if self.future is not None and self.future.done():
            future = self.future
            self.future = None
            try:
                if self.future_token != self.token or not self.running:
                    future.exception()
                    self.event("info", "已丢弃停止或重置前的API响应")
                    return
                if self.single_step and not self.diagnostic_stage:
                    self.pause_requested = True
                if self.credential_source == "file" and self.refresh_local_connection():
                    future.exception()
                    self.event("info", "配置已切换，已丢弃旧供应商响应并重新观察")
                    self.phase = "observing"
                    return
                latency = self.policy.last_latency
                self.api_latency = latency if type(latency) in (int, float) and np.isfinite(latency) else None
                action = future.result()
                if self.diagnostic_stage:
                    def redact(value):
                        if isinstance(value, str):
                            return value.replace(self.key, "[REDACTED]") if self.key else value
                        if isinstance(value, dict):
                            return {k: redact(v) for k, v in value.items()}
                        if isinstance(value, list):
                            return [redact(v) for v in value]
                        return value
                    self.diagnostic_result = redact({**action, "latency_seconds": self.api_latency,
                        "usage": self.policy.last_usage or None,
                        "request_options": self.policy.request_options})
                    self.running = False
                    self.paused = self.pause_requested = False
                    self.phase = "completed"
                    self.termination_reason = "diagnostic_complete"
                    self.event("diagnostic", "诊断响应通过；没有执行机器人动作", result=self.diagnostic_result)
                    return
                if self.future_token != self.token or not self.running:
                    self.event("info", "已丢弃停止或重置前的API响应")
                    return
                self.last_action = (
                    asdict(action) if isinstance(action, ActionChunk) else action
                )
                valid, reason = self.sim.validate_snapshot(
                    self.pending_observation,
                    self.max_age if self.timing == "realtime" else float("inf"),
                )
                if not valid:
                    self.event("rejected", reason)
                    self.geometry = []
                    self.sim.feedback = {"status": "rejected", "message": reason}
                    return
                fresh_images, _ = self.sim.render_images()
                if self._visual_changed(self.request_images, fresh_images):
                    self.sim.feedback = {
                        "status": "rejected",
                        "message": "等待期间画面明显变化，重新观察后决策",
                    }
                    self.event("rejected", self.sim.feedback["message"])
                    self.geometry = []
                    return
                if isinstance(action, ActionChunk):
                    if (
                        action.observation_id
                        != self.pending_observation["observation_id"]
                    ):
                        raise ValueError("Chunk observation ID mismatch")
                    self.chunk = self.sim.create_chunk_executor(action)
                    self.geometry = []
                    self.phase = "executing"
                    self.event(
                        "decision",
                        "收到定时动作块",
                        action=asdict(action),
                        latency_seconds=self.api_latency,
                        request_index=self.api_calls,
                        usage=self.policy.last_usage,
                    )
                    return
                if (
                    action.get("observation_id")
                    != self.pending_observation["observation_id"]
                ):
                    raise ValueError("Action observation ID mismatch")
                self.event(
                    "decision",
                    action.get("explanation", ""),
                    action=action,
                    latency_seconds=self.api_latency,
                    request_index=self.api_calls,
                    usage=self.policy.last_usage,
                )
                if action["kind"] == "query_depth":
                    result = self.sim.depth_query(action)
                    self.geometry.append(result)
                    self.geometry = self.geometry[-8:]
                    self.event("geometry", "已返回深度查询结果", result=result)
                    self.phase = "observing"
                    # Keep the synchronized snapshot for the follow-up query/action; revalidate before execution.
                elif action["kind"] == "done":
                    self.running = False
                    self.paused = self.pause_requested = False
                    self.phase = "completed"
                    self.termination_reason = "model_done"
                    self.event("complete", "模型声明任务结束；成功与否以独立评估为准")
                else:
                    self.transition_before = (deepcopy(self.pending_observation), dict(self.request_images),
                                              deepcopy(action), self.api_calls)
                    result = self.sim.execute(
                        Action.from_legacy(
                            action, frame=self.pending_observation["frame_id"]
                        ).legacy()
                    )
                    self.awaiting_execution = (result["status"] == "accepted" and
                        self.sim.describe().get("llm_control") == "tcp_target_servo_v2")
                    self.history.append({"action": action, "feedback": result})
                    self.history = self.history[-8:]
                    self.geometry = []
                    self.step_count += 1
                    self.phase = (
                        "executing" if result["status"] == "accepted" else "observing"
                    )
                    self.event(result["status"], result["message"], feedback=result, request_index=self.api_calls)
                    self.next_request = time.monotonic() + (
                        0.15 if self.timing == "realtime" else 0.0
                    )
                if self.single_step and self.running:
                    self.pause_requested = True
            except Exception as exc:
                self.running = False
                self.paused = self.pause_requested = False
                self.phase = "error"
                self.termination_reason = "policy_error"
                self.error = str(exc)
                if self.key:
                    self.error = self.error.replace(self.key, "[REDACTED]")
                if isinstance(exc, ConfigError):
                    self.credentials = {
                        **self.credentials,
                        "key_configured": False,
                        "error": self.error,
                    }
                self.sim.hold()
                self.event("error", self.error,
                    request_index=self.api_calls,
                    category=getattr(exc, "category", "policy_error"),
                    http_status=getattr(exc, "http_status", None),
                    latency_seconds=self.api_latency,
                    usage=self.policy.last_usage if type(self.policy.last_usage) is dict and self.policy.last_usage else None)
        if (
            self.running
            and not self.paused
            and not self.pause_requested
            and self.future is None
            and self.chunk is None
            and self.sim.settled
            and time.monotonic() >= self.next_request
        ):
            if self.max_steps > 0 and self.api_calls >= self.max_steps:
                self.stop("达到决策调用上限，已保持当前位置", reason="decision_budget")
                return
            if self.credential_source == "file":
                try:
                    self.refresh_local_connection()
                except ConfigError as exc:
                    self.running = False
                    self.phase = "error"
                    self.termination_reason = "policy_error"
                    self.error = str(exc)
                    self.credentials = {
                        **self.credentials,
                        "key_configured": False,
                        "error": self.error,
                    }
                    self.sim.hold()
                    self.event("error", self.error)
                    return
            if self.geometry and self.pending_observation:
                valid, _ = self.sim.validate_snapshot(
                    self.pending_observation,
                    self.max_age if self.timing == "realtime" else float("inf"),
                )
                if not valid:
                    self.geometry = []
            if not self.geometry:
                self.pending_observation, self.request_images = self.sim.observe()
            self.pending_observation["execution_mode"] = self.timing
            self.phase = "thinking"
            self.api_calls += 1
            self.future_token = self.token
            policy_images = dict(self.request_images)
            policy_history = deepcopy(self.history)
            if self.context_mode == "paired" and self.last_transition is not None:
                transition, before_images = self.last_transition
                policy_history.append({"transition": deepcopy(transition)})
                policy_images.update({"previous/" + name: data for name, data in before_images.items()})
            guard_sensor_tree(policy_history)
            self.replay_frames.append({"request_index": self.api_calls,
                "observation": paired_sensors(self.pending_observation),
                "images": dict(self.request_images), "phase": "before"})
            if self.log_file:
                directory = self.log_file.parent
                for camera, data in self.request_images.items():
                    suffix = "png" if data.startswith(b"\x89PNG") else "jpg"
                    (directory / f"{self.api_calls:03d}-{camera}.{suffix}").write_bytes(
                        data
                    )
                (directory / f"{self.api_calls:03d}-observation.json").write_text(
                    json.dumps(self.pending_observation, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (directory / f"{self.api_calls:03d}-context.json").write_text(
                    json.dumps({"context_mode": self.context_mode, "history": policy_history,
                                "image_labels": list(policy_images)}, ensure_ascii=False, indent=2),
                    encoding="utf-8")
            self.event(
                "request", f"第 {self.api_calls} 次策略调用：读取双相机和机器人状态"
            )
            if self.diagnostic_stage:
                self.future = self.pool.submit(self.policy.diagnose, self.diagnostic_stage,
                    self.task, self.representation.encode(self.pending_observation), self.request_images)
                return
            self.future = self.pool.submit(
                self.policy.decide,
                self.task,
                self.representation.encode(self.pending_observation),
                policy_images,
                policy_history,
                list(self.geometry),
            )

    def publish(self, render=True):
        if render:
            images, _ = self.sim.render_images()
        else:
            images = {}
        state = {
            "running": self.running,
            "paused": self.paused,
            "pause_requested": self.pause_requested,
            "context_mode": self.context_mode,
            "replay_available": bool(self.replay_html),
            "ready": True,
            "error": self.error,
            "phase": self.phase,
            "model": self.model,
            "key_configured": self.credentials["key_configured"],
            "step": self.step_count,
            "manual_key_configured": bool(self.manual_key),
            "credentials": dict(self.credentials),
            "api_calls": self.api_calls,
            "max_steps": self.max_steps,
            "api_latency": self.api_latency,
            "pending_request": self.future is not None,
            "diagnostic_result": self.diagnostic_result,
            "diagnostic_stage": self.diagnostic_stage,
            "max_wall_seconds": self.wall_budget,
            "max_sim_seconds": self.sim_budget,
            "motion_busy": self.sim.busy or self.chunk is not None,
            "backend": self.sim.backend,
            "environment": self.sim.describe(),
            "robot": self.sim.robot_name,
            "scene": self.sim.scene_name,
            "task_id": self.sim.task_name,
            "task_instruction": self.sim.instruction,
            "timing": self.timing,
            "agent": self.policy_kind,
            "credential_source": self.credential_source,
            "sim_time": float(self.sim.simulation_time),
            "tcp_position": self.sim.tcp_position.tolist(),
            "gripper_opening": self.sim.gripper_opening,
            "last_action": self.last_action,
            "last_feedback": self.sim.feedback,
            "events": list(self.events[-60:]),
            "evaluation": self.sim.evaluation(),
            "observation": self.pending_observation or {},
        }
        with self.lock:
            self.state = state
            if images:
                self.images = images


# Descriptive public name; Demo remains a compatibility alias for earlier callers.
Demo = EpisodeRunner
