"""Sensor-only inference through the official Codex CLI's existing login.

Authentication stays inside Codex. Each request uses a fresh, ephemeral session,
an isolated input directory and disabled agent integrations. No token is read by
ManiLoop and no evaluator file is accessible to model tools.
"""

import base64
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time

from .responses import DEFAULT_MODEL, GPTPolicy, PolicyError


DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "code_mode", "code_mode_host", "apps",
    "plugins", "hooks", "multi_agent", "multi_agent_v2", "browser_use",
    "browser_use_external", "computer_use", "in_app_browser", "image_generation",
    "memories", "goals", "tool_suggest", "workspace_dependencies",
)

# Codex 0.154.0 emits this startup notice even when Code Mode is explicitly
# disabled. It confirms that the unavailable integration fails closed. This exact
# notice may be ignored only before inference starts; other errors remain fatal.
DISABLED_CODE_MODE_NOTICE = (
    "Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; "
    "enable `features.code_mode_host` and install `codex-code-mode-host`."
)


def codex_environment():
    # Preserve the user's auth location; never copy credentials or inherit API
    # keys, alternate provider settings, project paths or cloud run metadata.
    allowed = {"PATH", "HOME", "CODEX_HOME", "TMPDIR", "TEMP", "TMP", "LANG",
               "LC_ALL", "SYSTEMROOT", "WINDIR", "USERPROFILE", "APPDATA",
               "LOCALAPPDATA", "SSL_CERT_FILE", "SSL_CERT_DIR"}
    return {key: value for key, value in os.environ.items() if key in allowed}


def resolve_codex_executable(executable=None):
    """Explicit binary, project override, then PATH; never parse a shell command."""
    selected = executable if executable is not None else os.environ.get("MANILOOP_CODEX_BIN")
    if selected is not None:
        try:
            selected = os.fspath(selected)
        except TypeError:
            raise PolicyError("Codex 可执行文件必须是单个绝对路径", category="configuration") from None
        if (not isinstance(selected, str) or not selected or any(c in selected for c in "\x00\r\n")
                or not os.path.isabs(selected)):
            raise PolicyError("Codex 可执行文件必须是单个绝对路径", category="configuration")
        # Spaces in a valid pathname are preserved. Popen receives this as argv[0]
        # with shell=False, so flags or shell expressions are never interpreted.
        return selected
    found = shutil.which("codex")
    return os.path.abspath(found) if found else None


@lru_cache(maxsize=16)
def codex_version(executable):
    """Read public CLI provenance once per binary; no inference or auth required."""
    try:
        result = subprocess.run([executable, "--version"], capture_output=True, text=True,
                                timeout=5, env=codex_environment())
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.fullmatch(r"codex-cli ([0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?)", result.stdout.strip())
    return match.group(1) if result.returncode == 0 and match else None


def login_status(executable=None):
    try:
        executable = resolve_codex_executable(executable)
    except PolicyError:
        return {"available": False, "logged_in": False, "message": "Codex 可执行文件必须是单个绝对路径"}
    if not executable:
        return {"available": False, "logged_in": False, "message": "未找到 Codex CLI"}
    try:
        result = subprocess.run([executable, "login", "status"], capture_output=True,
                                text=True, timeout=15, env=codex_environment())
        logged_in = result.returncode == 0 and "using ChatGPT" in result.stdout + result.stderr
        return {"available": True, "logged_in": logged_in,
                "message": "检测到本机 ChatGPT 登录记录；有效性待请求验证" if logged_in else "请先在 Codex CLI 登录 ChatGPT"}
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "logged_in": False, "message": "无法检查 Codex CLI 登录"}


class CodexPolicy(GPTPolicy):
    """Reuse the validated sensor/action protocol with a separate transport."""

    def __init__(self, model=None, *, request_options=None, executable=None):
        self.model = model or DEFAULT_MODEL
        self.executable = resolve_codex_executable(executable)
        if not self.executable:
            raise PolicyError("未找到 Codex CLI，请安装并登录后重试", category="configuration")
        options = dict(request_options or {})
        if set(options) - {"timeout_seconds", "max_output_tokens", "reasoning_effort"}:
            raise PolicyError("请求设置包含不支持的字段", category="configuration")
        self.timeout = options.get("timeout_seconds", 120)
        self.max_output_tokens = options.get("max_output_tokens", 4096)
        self.reasoning_effort = options.get("reasoning_effort", "low")
        if self.reasoning_effort in (None, "auto"):
            self.reasoning_effort = "low"
        if (type(self.timeout) not in (int, float) or not math.isfinite(self.timeout)
                or not 0 < self.timeout <= 600 or type(self.max_output_tokens) is not int
                or not 256 <= self.max_output_tokens <= 32768
                or type(self.reasoning_effort) is not str
                or self.reasoning_effort not in {"low", "medium", "high", "xhigh", "max"}):
            raise PolicyError("Codex 请求设置无效", category="configuration")
        self.last_usage = {}
        self.last_latency = 0.0
        self.last_response_id = None
        self.client = None
        self._lock = threading.Lock()
        self._process = None
        self._cancelled = threading.Event()

    @property
    def request_options(self):
        return {"timeout_seconds": self.timeout, "reasoning_effort": self.reasoning_effort,
                "transport": "codex_exec_chatgpt_v1", "policy_retries": 0,
                "cli_version": codex_version(self.executable),
                "transport_retries": "managed_by_codex",
                "ephemeral": True, "agent_tools": "disabled",
                "startup_warning_policy": "exact_disabled_code_mode_before_turn_v1",
                "output_limit": "schema_and_client_size_limit",
                "output_limit_chars": self.max_output_tokens * 16}

    def reset(self, seed=0):
        self._cancelled.clear()

    def _arguments(self, directory, images, schema):
        args = [self.executable, "exec", "--ignore-user-config", "--ephemeral",
                "--skip-git-repo-check", "--json", "--color", "never",
                "--cd", str(directory), "--model", self.model]
        settings = {
            "model_provider": "openai", "model_reasoning_effort": self.reasoning_effort,
            "approval_policy": "never", "web_search": "disabled",
            "project_doc_max_bytes": 0, "skills.include_instructions": False,
            "skills.bundled.enabled": False, "include_apps_instructions": False,
            "default_permissions": "maniloop_observer",
            "permissions.maniloop_observer.filesystem": {"/": "deny", str(directory): "read"},
        }
        # TOML inline tables, not JSON object syntax, for the filesystem map.
        for key, value in settings.items():
            encoded = ("{" + ", ".join(json.dumps(k) + " = " + json.dumps(v)
                       for k, v in value.items()) + "}") if isinstance(value, dict) else json.dumps(value)
            args += ["-c", key + "=" + encoded]
        for feature in DISABLED_FEATURES:
            args += ["--disable", feature]
        if schema is not None:
            path = directory / "response-schema.json"
            path.write_text(json.dumps(schema), encoding="utf-8")
            args += ["--output-schema", str(path)]
        for path in images:
            args += ["--image", str(path)]
        return args + ["-"]

    def _request_text(self, request):
        self.last_usage, self.last_response_id = {}, None
        if self._cancelled.is_set():
            raise PolicyError("Codex 请求已取消", category="interrupted")
        started = time.monotonic()
        try:
            with tempfile.TemporaryDirectory(prefix="maniloop-observer-") as tmp:
                directory = Path(tmp).resolve()
                texts = [request.get("instructions", ""),
                         "Return only the requested final answer. Do not use tools, files, skills or browsing. "
                         "Only the attached sensor observations are available. Each attached image follows "
                         "the label with the matching Image number below."]
                images = []
                for message in request["input"]:
                    for content in message["content"]:
                        if content["type"] == "input_text":
                            texts.append(content["text"])
                        elif content["type"] == "input_image":
                            uri = content["image_url"]
                            if not isinstance(uri, str) or "," not in uri:
                                raise PolicyError("Codex 仅接收显式传感器图像")
                            header, payload = uri.split(",", 1)
                            if header not in {"data:image/jpeg;base64", "data:image/png;base64"}:
                                raise PolicyError("Codex 仅接收显式传感器图像")
                            image = directory / (f"sensor-{len(images)}" + (".png" if "png" in header else ".jpg"))
                            try:
                                decoded = base64.b64decode(payload, validate=True)
                            except ValueError:
                                raise PolicyError("Codex 传感器图像编码无效") from None
                            if not decoded:
                                raise PolicyError("Codex 传感器图像为空")
                            image.write_bytes(decoded)
                            images.append(image)
                            texts.append(f"Image {len(images)}: attached sensor image.")
                        else:
                            raise PolicyError("不支持的 Codex 传感输入类型")
                schema = request.get("text", {}).get("format", {}).get("schema")
                args = self._arguments(directory, images, schema)
                with self._lock:
                    if self._cancelled.is_set():
                        raise PolicyError("Codex 请求已取消", category="interrupted")
                    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, text=True, env=codex_environment(),
                                            start_new_session=(os.name != "nt"))
                    self._process = proc
                try:
                    stdout, stderr = proc.communicate("\n\n".join(texts), timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    self._terminate(proc)
                    proc.communicate()
                    raise PolicyError("Codex 请求超时；未自动重试，远端可能已计入使用量", category="timeout") from None
                finally:
                    with self._lock:
                        self._process = None
                if self._cancelled.is_set():
                    raise PolicyError("Codex 请求已取消，动作不会执行", category="interrupted")
                return self._parse(stdout, stderr, proc.returncode)
        except OSError:
            raise PolicyError("无法启动 Codex CLI", category="connection") from None
        finally:
            self.last_latency = time.monotonic() - started

    def _parse(self, stdout, stderr, returncode):
        if len(stdout) > 4 * 1024 * 1024:
            raise PolicyError("Codex 输出超过限制")
        answers = []
        completed = 0
        turn_started = False
        failed = False
        errors = []
        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError:
                failed = True
                continue
            if not isinstance(event, dict):
                failed = True
                continue
            kind = event.get("type")
            if kind == "thread.started":
                thread_id = event.get("thread_id")
                if (self.last_response_id is not None or type(thread_id) is not str
                        or not thread_id.strip() or len(thread_id) > 256):
                    failed = True
                else:
                    self.last_response_id = thread_id
            elif kind == "turn.started":
                if turn_started or self.last_response_id is None:
                    failed = True
                turn_started = True
            elif kind in {"item.started", "item.updated", "item.completed"}:
                item = event.get("item", {})
                if not isinstance(item, dict):
                    failed = True
                    continue
                if item.get("type") == "agent_message":
                    if kind == "item.completed":
                        answers.append(item.get("text"))
                elif (kind == "item.completed" and item.get("type") == "error"
                      and not turn_started and self.last_response_id is not None
                      and item.get("message") == DISABLED_CODE_MODE_NOTICE):
                    pass
                elif item.get("type") != "reasoning":
                    # No native tool output is allowed into a robot decision.
                    failed = True
            elif kind == "turn.completed":
                completed += 1
                usage = event.get("usage", {})
                if not isinstance(usage, dict):
                    failed = True
                    continue
                self.last_usage = {k: v for k, v in usage.items()
                                   if k in {"input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"}
                                   and type(v) is int and v >= 0}
            elif kind in {"turn.failed", "error"}:
                failed = True
                error = event.get("error", event)
                if isinstance(error, dict) and isinstance(error.get("message"), str):
                    errors.append(error["message"])
            else:
                failed = True
        answer = answers[0] if len(answers) == 1 else None
        if (returncode or failed or not turn_started or completed != 1 or self.last_response_id is None
                or not isinstance(answer, str) or not answer.strip()):
            combined = (" ".join(errors) + stderr).lower()
            category, detail = "invalid_response", "未执行动作。"
            if "requires a newer version of codex" in combined or "upgrade to the latest app or cli" in combined:
                category = "client_outdated"
                detail = "所选模型要求更新的 Codex；请更新 CLI，或通过 MANILOOP_CODEX_BIN 指定已更新应用中的可执行文件。"
            elif any(s in combined for s in ("refresh token", "access token", "unauthorized", "authentication", "not logged in")):
                category = "authentication"
                detail = "Codex 登录无法完成认证，请在终端重新登录；本地登录记录不代表令牌仍有效。"
            elif any(s in combined for s in ("usage limit", "rate limit", "quota")):
                category, detail = "rate_limit", "Codex 使用额度或请求速率受限。"
            elif "not supported" in combined or "model_not_found" in combined:
                category, detail = "model_unavailable", "当前 Codex 登录无法使用所选模型。"
            # Never echo free-form CLI errors, which can contain account data or
            # arbitrary secrets that token-pattern redaction cannot recognize.
            raise PolicyError(f"Codex 未返回完整的无工具响应（{category}，退出码 {returncode}）：{detail}", category=category)
        if len(answer) > self.max_output_tokens * 16:
            raise PolicyError("Codex 最终响应超过客户端长度限制")
        return answer

    @staticmethod
    def _terminate(proc):
        if proc.poll() is None:
            try:
                if os.name != "nt":
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
            except ProcessLookupError:
                pass

    def cancel(self):
        self._cancelled.set()
        with self._lock:
            if self._process is not None:
                self._terminate(self._process)

    def close(self):
        self.cancel()
