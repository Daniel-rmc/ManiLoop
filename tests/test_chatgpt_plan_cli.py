"""CLI routing only: no credentials, network requests or simulation processes."""
import pytest

from maniloop import cli


def fake_result():
    return {"phase": "completed", "evaluation": {"success": True}, "is_mock": False,
            "environment": {"backend": "libero", "robot": "panda", "scene": "fixture", "task": "fixture"}}


def test_benchmark_direct_plan_routes_without_api_key_and_preserves_recording_options(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setenv("OPENAI_API_KEY", "offline-must-not-be-forwarded")
    def run(case, output, connection, *, render):
        calls.append((case, output, connection, render))
        return fake_result()
    monkeypatch.setattr(cli, "run_episode", run)
    cli.main(["benchmark", "--backend", "libero", "--agent", "llm_cloud", "--chatgpt-plan",
              "--model", "gpt-6-astra", "--libero-suite", "libero_spatial", "--libero-task-id", "0",
              "--max-calls", "0", "--reasoning-effort", "medium", "--record-episode",
              "--output", str(tmp_path)])
    assert len(calls) == 1
    case, output, connection, render = calls[0]
    assert connection == {"credential_source": "chatgpt_plan", "config_path": None,
                          "api_key": None, "model": "gpt-6-astra"}
    assert case.max_calls == 0
    assert case.reasoning_effort == "medium"
    assert case.record_episode is True and case.timing == "controlled"
    assert case.agent == "llm_cloud" and case.backend == "libero"
    assert render is True and output == tmp_path


@pytest.mark.parametrize("flags", [
    ["--chatgpt-plan", "--codex-login"],
    ["--chatgpt-plan", "--provider-config", "never-read.toml"],
    ["--codex-login", "--provider-config", "never-read.toml"],
])
def test_benchmark_rejects_ambiguous_connection_before_execution(flags, tmp_path, monkeypatch, capsys):
    def unexpected(*args, **kwargs):
        pytest.fail("Conflicting credentials must fail before a run starts")
    monkeypatch.setattr(cli, "run_episode", unexpected)
    with pytest.raises(SystemExit) as exc:
        cli.main(["benchmark", *flags, "--output", str(tmp_path / "not-created")])
    assert exc.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err
    assert not (tmp_path / "not-created").exists()


def test_demo_rejects_both_chatgpt_routes_before_startup(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["demo", "--chatgpt-plan", "--codex-login"])
    assert exc.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


@pytest.mark.parametrize("flags,source", [([], "manual"), (["--codex-login"], "codex"),
                                        (["--provider-config", "fixture.toml"], "file")])
def test_existing_benchmark_routes_keep_their_connection(flags, source, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setenv("OPENAI_API_KEY", "offline-api-key")
    def run(case, output, connection, *, render):
        calls.append(connection)
        return fake_result()
    monkeypatch.setattr(cli, "run_episode", run)
    cli.main(["benchmark", *flags, "--output", str(tmp_path)])
    assert calls[0]["credential_source"] == source
    assert calls[0]["api_key"] == (None if source == "codex" else "offline-api-key")


def test_cli_wide_target_selection_and_backend_boundary(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "run_episode", lambda case, *args, **kwargs: calls.append(case) or fake_result())
    cli.main(["benchmark", "--backend", "libero", "--agent", "llm_cloud", "--chatgpt-plan",
              "--llm-control", "tcp_target_servo_v3", "--output", str(tmp_path)])
    assert calls[0].llm_control == "tcp_target_servo_v3"
    calls[0].validate()
    with pytest.raises(SystemExit) as exc:
        cli.main(["demo", "--backend", "mujoco", "--llm-control", "tcp_target_servo_v3"])
    assert exc.value.code == 2
