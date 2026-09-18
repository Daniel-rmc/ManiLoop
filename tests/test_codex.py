"""Codex transport contracts using fake processes; never runs the CLI or a model."""

import json
import os
from pathlib import Path
import subprocess
import threading
import unittest
from unittest.mock import MagicMock, patch

from maniloop.providers.codex import (
    CodexPolicy, DISABLED_CODE_MODE_NOTICE, DISABLED_FEATURES, codex_environment, codex_version, login_status,
    resolve_codex_executable,
)
from maniloop.providers.responses import action_schema_for, PolicyError


def fake_path(*parts):
    """Native absolute argv fixtures, including a drive on Windows; no files needed."""
    return str(Path(Path.cwd().anchor, "fake", *parts))


FAKE_CODEX = fake_path("codex")


def action(**changes):
    result = {
        "observation_id": "observation-offline", "kind": "move",
        "delta_position": [0.01, 0, 0], "delta_rotation": [0, 0, 0],
        "gripper_opening": 0, "pixel": [0, 0], "camera": "",
        "explanation": "从当前传感器视图向前移动一小步。",
    }
    result.update(changes)
    return result


def events(answer="READY", extra=(), usage=None):
    return "\n".join(json.dumps(event) for event in [
        {"type": "thread.started", "thread_id": "thread-offline"},
        {"type": "turn.started"},
        *extra,
        {"type": "item.completed", "item": {"type": "agent_message", "text": answer}},
        {"type": "turn.completed", "usage": usage or {"input_tokens": 100, "output_tokens": 12}},
    ])


class CodexTests(unittest.TestCase):
    def setUp(self):
        self.policy = CodexPolicy(executable=FAKE_CODEX)
        self.observation = {"observation_id": "observation-offline", "frame_id": "base",
                            "tcp_position": [0.3, 0, 0.2]}
        self.images = {"external": b"offline-jpeg-external", "wrist": b"offline-jpeg-wrist"}

    def decide(self, **changes):
        args = dict(task="把碗放到盘子上", observation=self.observation, images=self.images,
                    history=[], geometry_results=[])
        args.update(changes)
        return self.policy.decide(**args)

    def test_environment_preserves_auth_location_without_forwarding_api_credentials(self):
        env = {"HOME": "/fake/home", "CODEX_HOME": "/fake/codex-home", "PATH": "/fake/bin",
               "LANG": "en_US.UTF-8", "OPENAI_API_KEY": "private-example", "OPENAI_BASE_URL": "private-endpoint",
               "AZURE_OPENAI_KEY": "private-example", "CODEX_THREAD_ID": "private-thread",
               "UNRELATED_CREDENTIAL": "private-example", "PWD": "/private/project"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(codex_environment(), {k: env[k] for k in ("HOME", "CODEX_HOME", "PATH", "LANG")})

    def test_login_status_reports_presence_without_claiming_token_validity(self):
        result = subprocess.CompletedProcess([], 0, "", "Logged in using ChatGPT")
        with patch("maniloop.providers.codex.subprocess.run", return_value=result) as run:
            status = login_status(FAKE_CODEX)
        self.assertTrue(status["logged_in"])
        self.assertIn("有效性待请求验证", status["message"])
        self.assertEqual(run.call_args.args[0], [FAKE_CODEX, "login", "status"])
        self.assertEqual(run.call_args.kwargs["timeout"], 15)
        for output in ("Not logged in; private@example.test", "Logged in using an API key: private-example"):
            with self.subTest(output=output), patch("maniloop.providers.codex.subprocess.run", return_value=
                    subprocess.CompletedProcess([], 0, output, "")):
                status = login_status(FAKE_CODEX)
                self.assertFalse(status["logged_in"])
                self.assertNotIn("private", status["message"])

    def test_executable_resolution_and_login_use_same_explicit_override(self):
        with patch.dict(os.environ, {"MANILOOP_CODEX_BIN": fake_path("Bundled App", "codex")}), patch(
                "maniloop.providers.codex.shutil.which", return_value=fake_path("global", "codex")) as which:
            self.assertEqual(resolve_codex_executable(fake_path("explicit", "codex")), fake_path("explicit", "codex"))
            self.assertEqual(resolve_codex_executable(), fake_path("Bundled App", "codex"))
            self.assertEqual(CodexPolicy().executable, fake_path("Bundled App", "codex"))
            with patch("maniloop.providers.codex.subprocess.run", return_value=
                    subprocess.CompletedProcess([], 0, "Logged in using ChatGPT", "")) as run:
                self.assertTrue(login_status()["logged_in"])
            self.assertEqual(run.call_args.args[0], [fake_path("Bundled App", "codex"), "login", "status"])
            which.assert_not_called()
        with patch.dict(os.environ, {}, clear=True), patch("maniloop.providers.codex.shutil.which", return_value=fake_path("global", "codex")):
            self.assertEqual(resolve_codex_executable(), fake_path("global", "codex"))
        for invalid in ("codex --model gpt-6-astra", [FAKE_CODEX, "exec"], "", FAKE_CODEX + "\nexec"):
            with self.subTest(invalid=invalid), self.assertRaises(PolicyError):
                resolve_codex_executable(invalid)

    def test_version_provenance_is_public_cached_and_never_echoes_unknown_output(self):
        codex_version.cache_clear()
        self.addCleanup(codex_version.cache_clear)
        with patch("maniloop.providers.codex.subprocess.run", return_value=
                subprocess.CompletedProcess([], 0, "codex-cli 0.154.0-alpha.6.2\n", "")) as run:
            self.assertEqual(self.policy.request_options["cli_version"], "0.154.0-alpha.6.2")
            self.assertEqual(self.policy.request_options["cli_version"], "0.154.0-alpha.6.2")
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0], [FAKE_CODEX, "--version"])
        for output in ("private@example.test", "codex-cli 0.1.0\nprivate", "0.154.0"):
            codex_version.cache_clear()
            with self.subTest(output=output), patch("maniloop.providers.codex.subprocess.run", return_value=
                    subprocess.CompletedProcess([], 0, output, "")):
                self.assertIsNone(codex_version(FAKE_CODEX))

    def test_cli_receives_only_sensor_files_and_explicit_tool_isolation(self):
        proc = MagicMock(returncode=0)
        captured = {}

        def communicate(prompt, timeout):
            args = popen.call_args.args[0]
            directory = Path(args[args.index("--cd") + 1])
            captured.update(directory=directory, args=args, prompt=prompt)
            self.assertEqual({p.name for p in directory.iterdir()},
                             {"sensor-0.jpg", "sensor-1.jpg", "response-schema.json"})
            self.assertEqual((directory / "sensor-0.jpg").read_bytes(), self.images["external"])
            self.assertEqual((directory / "sensor-1.jpg").read_bytes(), self.images["wrist"])
            self.assertEqual(json.loads((directory / "response-schema.json").read_text(encoding="utf-8")), action_schema_for(self.observation, self.images))
            self.assertEqual(timeout, 120)
            return events(json.dumps(action())), ""

        proc.communicate.side_effect = communicate
        with patch("maniloop.providers.codex.subprocess.Popen", return_value=proc) as popen:
            self.assertEqual(self.decide(), action())
        args = captured["args"]
        for flag in ("--ignore-user-config", "--ephemeral", "--skip-git-repo-check", "--json", "--output-schema"):
            self.assertIn(flag, args)
        disabled = {args[i + 1] for i, token in enumerate(args) if token == "--disable"}
        self.assertEqual(disabled, set(DISABLED_FEATURES))
        settings = [args[i + 1] for i, token in enumerate(args) if token == "-c"]
        for setting in ('model_provider="openai"', 'approval_policy="never"', 'web_search="disabled"',
                        "project_doc_max_bytes=0", "skills.include_instructions=false", "skills.bundled.enabled=false"):
            self.assertIn(setting, settings)
        filesystem = next(s for s in settings if s.startswith("permissions.maniloop_observer.filesystem="))
        self.assertIn('"/" = "deny"', filesystem)
        self.assertIn(json.dumps(str(captured["directory"])) + ' = "read"', filesystem)
        self.assertEqual(args[-1], "-")
        self.assertNotIn("把碗", " ".join(args))  # Payload travels over stdin, not process arguments.
        self.assertIn("把碗放到盘子上", captured["prompt"])
        self.assertIn("Camera: external", captured["prompt"])
        self.assertIn("Image 2", captured["prompt"])
        self.assertFalse(captured["directory"].exists())
        self.assertEqual(self.policy.last_response_id, "thread-offline")
        self.assertEqual(self.policy.last_usage, {"input_tokens": 100, "output_tokens": 12})
        self.assertIsNone(self.policy._process)
        self.assertGreaterEqual(self.policy.last_latency, 0)

    def test_strict_action_validation_is_retained_after_cli_transport(self):
        invalid = [action(observation_id="stale"), action(extra="unexpected"),
                   action(delta_position=[float("nan"), 0, 0]), action(delta_position=[True, 0, 0]),
                   action(kind="execute_python"), action(kind="wait"), action(camera="external")]
        payloads = [json.dumps(value) for value in invalid] + ['{"kind":"wait","kind":"done"}', "```json\n{}\n```"]
        for payload in payloads:
            with self.subTest(payload=payload), patch.object(self.policy, "_request_text", return_value=payload), self.assertRaises(PolicyError):
                self.decide()

    def test_nested_truth_fields_are_rejected_before_starting_process(self):
        private = [dict(history=[{"feedback": {"native_success": True}}]),
                   dict(history=[{"transition": {"after": {"object_pose": [0, 0, 0]}}}]),
                   dict(geometry_results=[{"evaluation": {"success": True}}])]
        with patch("maniloop.providers.codex.subprocess.Popen") as popen:
            for kwargs in private:
                with self.subTest(kwargs=kwargs), self.assertRaises(PolicyError):
                    self.decide(**kwargs)
        popen.assert_not_called()

    def test_parser_rejects_tool_attempts_even_without_completed_tool_output(self):
        for event_type in ("item.started", "item.updated", "item.completed"):
            for item_type in ("command_execution", "mcp_tool_call", "web_search", "todo_list", "file_change"):
                with self.subTest(event_type=event_type, item_type=item_type), self.assertRaises(PolicyError):
                    CodexPolicy(executable=FAKE_CODEX)._parse(events(extra=[
                        {"type": event_type, "item": {"type": item_type}}]), "", 0)

    def test_parser_rejects_malformed_incomplete_or_ambiguous_stream(self):
        invalid = ["", "[]", "null", '"a string"', "unstructured stdout\n" + events(),
                   events() + "\n" + json.dumps({"type": "turn.completed", "usage": {}}),
                   events(extra=[{"type": "item.completed", "item": {"type": "agent_message", "text": "OTHER"}}]),
                   events(extra=[{"type": "item.completed", "item": None}]),
                   events(extra=[{"type": "future_unknown_event"}]),
                   events().replace('"thread-offline"', "null"),
                   events().replace('"usage": {"input_tokens": 100, "output_tokens": 12}', '"usage": null'),
                   "\n".join(events().splitlines()[:-1]), "\n".join(events().splitlines()[1:])]
        for stream in invalid:
            with self.subTest(stream=stream[:80]), self.assertRaises(PolicyError):
                CodexPolicy(executable=FAKE_CODEX)._parse(stream, "", 0)

    def test_reasoning_is_ignored_and_usage_is_allowlisted(self):
        result = self.policy._parse(events(extra=[{"type": "item.completed", "item": {
            "type": "reasoning", "text": "private internal explanation"}}], usage={
                "input_tokens": 10, "cached_input_tokens": 3, "output_tokens": 2,
                "total_tokens": True, "private-metadata": 12}), "", 0)
        self.assertEqual(result, "READY")
        self.assertEqual(self.policy.last_usage, {"input_tokens": 10, "cached_input_tokens": 3, "output_tokens": 2})

    def test_real_bundled_cli_disabled_code_mode_notice_is_allowed_only_before_turn(self):
        warning = {"type": "item.completed", "item": {"type": "error", "message": DISABLED_CODE_MODE_NOTICE}}
        fixture = [
            {"type": "thread.started", "thread_id": "thread-offline"}, warning,
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "READY"}},
            {"type": "turn.completed", "usage": {"input_tokens": 8398, "cached_input_tokens": 0,
                "cache_write_input_tokens": 0, "output_tokens": 5, "reasoning_output_tokens": 0}},
        ]
        self.assertEqual(self.policy._parse("\n".join(map(json.dumps, fixture)), "", 0), "READY")
        self.assertEqual(self.policy.last_usage, {"input_tokens": 8398, "cached_input_tokens": 0, "output_tokens": 5})
        with patch("maniloop.providers.codex.codex_version", return_value="0.154.0-alpha.6.2"):
            self.assertEqual(self.policy.request_options["startup_warning_policy"], "exact_disabled_code_mode_before_turn_v1")
        invalid = [
            [fixture[0], fixture[2], warning, *fixture[3:]],  # Same notice during inference.
            [warning, fixture[0], *fixture[2:]],  # Notice before a known session.
            [fixture[0], warning, *fixture[3:]],  # No turn.started.
            [fixture[0], warning, fixture[2], fixture[2], *fixture[3:]],
            [fixture[0], dict(warning, item={"type": "error", "message": DISABLED_CODE_MODE_NOTICE + " private"}), *fixture[2:]],
            [fixture[0], dict(warning, item={"type": "error", "message": "Other startup error"}), *fixture[2:]],
        ]
        for records in invalid:
            with self.subTest(records=records), self.assertRaises(PolicyError):
                CodexPolicy(executable=FAKE_CODEX)._parse("\n".join(map(json.dumps, records)), "", 0)

    def test_errors_are_categorical_and_never_echo_cli_secrets(self):
        cases = [
            ("Your refresh token was revoked. Log in again.", "authentication"),
            ("You are not logged in", "authentication"),
            ("Usage limit exceeded", "rate_limit"),
            ("model_not_found", "model_unavailable"),
            ("The gpt-6-astra model requires a newer version of Codex. Please upgrade to latest app or CLI", "client_outdated"),
            ("Unrecognized failure", "invalid_response"),
        ]
        secret = "private@example.test access_token=nonstandard-secret /Users/private/config sk-fakeJWT"
        for message, category in cases:
            for in_stderr in (False, True):
                stream = json.dumps({"type": "turn.failed", "error": {"message": "failed" if in_stderr else message + secret}})
                stderr = message + secret if in_stderr else ""
                with self.subTest(message=message, in_stderr=in_stderr), self.assertRaises(PolicyError) as caught:
                    CodexPolicy(executable=FAKE_CODEX)._parse(stream, stderr, 1)
                self.assertEqual(caught.exception.category, category)
                for fragment in ("private", "nonstandard-secret", "sk-fakeJWT"):
                    self.assertNotIn(fragment, str(caught.exception))

    def test_client_output_limit_and_metadata_describe_actual_cli_limits(self):
        policy = CodexPolicy(executable=FAKE_CODEX, request_options={"max_output_tokens": 256})
        with self.assertRaisesRegex(PolicyError, "客户端长度"):
            policy._parse(events("x" * (256 * 16 + 1)), "", 0)
        with patch("maniloop.providers.codex.codex_version", return_value="0.154.0-alpha.6.2"):
            self.assertEqual(policy.request_options["output_limit"], "schema_and_client_size_limit")
            self.assertEqual(policy.request_options["transport_retries"], "managed_by_codex")
            self.assertEqual(policy.request_options["policy_retries"], 0)

    def test_timeout_kills_process_and_does_not_retry(self):
        proc = MagicMock(returncode=-9)
        proc.communicate.side_effect = [subprocess.TimeoutExpired(FAKE_CODEX, 120), ("", "private-error")]
        with patch("maniloop.providers.codex.subprocess.Popen", return_value=proc) as popen, patch.object(self.policy, "_terminate") as terminate:
            with self.assertRaises(PolicyError) as caught:
                self.policy.diagnose("text", "", {}, {})
        self.assertEqual(caught.exception.category, "timeout")
        popen.assert_called_once()
        terminate.assert_called_once_with(proc)
        self.assertIsNone(self.policy._process)

    def test_cancel_kills_inflight_process_and_discards_completed_answer(self):
        started, released = threading.Event(), threading.Event()
        errors = []
        proc = MagicMock(returncode=0)

        def communicate(*_args, **_kwargs):
            started.set()
            if not released.wait(3):
                raise AssertionError("Test cancellation did not release process")
            return events(), ""

        def run():
            try:
                self.policy.diagnose("text", "", {}, {})
            except Exception as error:
                errors.append(error)

        proc.communicate.side_effect = communicate
        with patch("maniloop.providers.codex.subprocess.Popen", return_value=proc), patch.object(self.policy, "_terminate", side_effect=lambda _: released.set()) as terminate:
            worker = threading.Thread(target=run)
            worker.start()
            self.assertTrue(started.wait(3))
            self.policy.cancel()
            worker.join(3)
            self.assertFalse(worker.is_alive())
            terminate.assert_called_once_with(proc)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], PolicyError)
        self.assertEqual(errors[0].category, "interrupted")
        self.assertIsNone(self.policy._process)
        with patch("maniloop.providers.codex.subprocess.Popen") as popen, self.assertRaises(PolicyError):
            self.policy.diagnose("text", "", {}, {})
        popen.assert_not_called()
        self.policy.reset()
        self.assertFalse(self.policy._cancelled.is_set())

    def test_invalid_request_options_are_configuration_errors(self):
        for options in ({"timeout_seconds": True}, {"timeout_seconds": float("nan")},
                        {"max_output_tokens": 1}, {"reasoning_effort": []}, {"reasoning_effort": False},
                        {"unknown": 1}):
            with self.subTest(options=options), self.assertRaises(PolicyError) as caught:
                CodexPolicy(executable=FAKE_CODEX, request_options=options)
            self.assertEqual(caught.exception.category, "configuration")

    def test_malformed_image_never_launches_cli_or_echoes_input(self):
        for uri in ("https://private.example/image", "data:image/jpeg;base64,###private###",
                    "data:image/jpeg;base64,", "data:image/gif;base64,YQ==", None):
            with self.subTest(uri=uri), patch("maniloop.providers.codex.subprocess.Popen") as popen, self.assertRaises(PolicyError) as caught:
                self.policy._request_text({"input": [{"content": [{"type": "input_image", "image_url": uri}]}]})
            popen.assert_not_called()
            self.assertNotIn("private", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
