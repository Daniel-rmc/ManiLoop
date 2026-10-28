"""Independent plan connection: local HTTP and fake auth/model, no paid requests."""

from concurrent.futures import Future
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import threading
from unittest.mock import MagicMock

import pytest

from maniloop.runtime.runner import EpisodeRunner
from maniloop.simulation.environment import RobotSim
from maniloop.ui.server import handler_for


class Auth:
    def __init__(self):
        self.pending = False
        self.calls = []

    def status(self):
        return {"accounts": [{"id": "account-A", "label": "Test account",
                              "logged_in": True, "plan_enabled": True}],
                "active_account_id": "account-A", "pending": self.pending, "error": ""}

    def start_login(self, account_id=None, *, retry_registration=False):
        self.calls.append(("retry" if retry_registration else "login", account_id))
        return {"authorization_url": "https://auth.openai.com/api/accounts/authorize?state=test"}

    def select_account(self, account_id):
        self.calls.append(("select", account_id))

    def logout(self, account_id=None):
        self.calls.append(("logout", account_id))

    def cancel_login(self):
        self.calls.append(("cancel", None))
        self.pending = False

    def close(self):
        pass


@pytest.fixture
def runner(tmp_path):
    runner = EpisodeRunner(RobotSim(render=False), output=tmp_path)
    runner._chatgpt_auth = Auth()
    yield runner
    runner.close()


def test_plan_start_does_not_load_api_or_codex_credentials(runner, monkeypatch):
    pytest.importorskip("httpx")
    factory = MagicMock()
    policy = factory.return_value
    policy.request_options = {"transport": "chatgpt_plan_direct_v1"}
    monkeypatch.setattr("maniloop.providers.chatgpt_plan.ChatGPTPlanPolicy", factory)
    runner.resolve_connection = MagicMock(side_effect=AssertionError("API configuration read"))
    runner.command("diagnose", {"credential_source": "chatgpt_plan", "stage": "text",
                                "model": "gpt-6-astra", "chatgpt_account_id": "account-A"})
    assert runner.policy is policy
    assert runner.credential_source == "chatgpt_plan"
    assert runner.key == ""
    assert factory.call_args.kwargs["account_id"] == "account-A"
    assert factory.call_args.kwargs["auth_store"] is runner._chatgpt_auth
    runner.resolve_connection.assert_not_called()
    assert "Test account" not in json.dumps(runner.credentials)  # No account identity in episodes.


def test_plan_models_are_explicit_network_action(runner, monkeypatch):
    pytest.importorskip("httpx")
    fetch = MagicMock(return_value=["gpt-6-astra"])
    monkeypatch.setattr("maniloop.providers.chatgpt_plan.list_plan_models", fetch)
    payload = {"credential_source": "chatgpt_plan"}
    preview = runner.connection_request("config-preview", payload)
    assert preview["config"]["key_configured"]
    fetch.assert_not_called()
    assert runner.connection_request("models", payload)["models"] == ["gpt-6-astra"]
    fetch.assert_called_once_with(runner._chatgpt_auth, "account-A")


@pytest.mark.parametrize("busy", ["running", "future", "chunk"])
@pytest.mark.parametrize("action", ["login", "logout", "select", "cancel"])
def test_auth_changes_are_blocked_during_episode(runner, busy, action):
    setattr(runner, busy, True if busy == "running" else Future() if busy == "future" else object())
    with pytest.raises(ValueError, match="停止任务"):
        runner.command("chatgpt/" + action, {})
    assert not runner._chatgpt_auth.calls
    setattr(runner, busy, False if busy == "running" else None)


def test_pending_auth_blocks_plan_start_and_unknown_account_is_rejected(runner):
    runner._chatgpt_auth.pending = True
    with pytest.raises(ValueError, match="完成或取消"):
        runner.chatgpt_account()
    runner._chatgpt_auth.pending = False
    with pytest.raises(ValueError, match="已保存"):
        runner.chatgpt_account("unknown")
    with pytest.raises(ValueError, match="不支持"):
        runner.command("chatgpt/login", {"redirect_uri": "https://other.example"})


@pytest.fixture
def local_http(runner):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(runner))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    yield conn, server
    conn.close()
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_auth_status_is_public_and_same_origin_only(local_http):
    conn, _ = local_http
    conn.request("GET", "/api/chatgpt/status")
    response = conn.getresponse()
    assert response.status == 200
    public = json.loads(response.read())
    assert public["active_account_id"] == "account-A"
    assert "access_token" not in public
    conn.request("GET", "/api/chatgpt/status", headers={"Origin": "https://other.example"})
    response = conn.getresponse()
    assert response.status == 403
    response.read()


@pytest.mark.parametrize("headers,status", [
    ({"Content-Type": "text/plain"}, 415),
    ({"Content-Type": "application/json", "Origin": "https://other.example"}, 403),
    ({"Content-Type": "application/json", "Host": "attacker.example"}, 403),
])
def test_auth_mutations_reject_cross_origin_and_simple_form_posts(local_http, runner, headers, status):
    conn, _ = local_http
    conn.request("POST", "/api/chatgpt/login", body="{}", headers=headers)
    response = conn.getresponse()
    assert response.status == status
    response.read()
    assert not runner._chatgpt_auth.calls


def test_queued_auth_command_returns_authorization_url(runner):
    import queue
    result = queue.Queue()
    runner.commands.put(("chatgpt/login", {}, result))
    runner.tick()
    value = result.get_nowait()
    assert value["ok"]
    assert value["authorization_url"].startswith("https://auth.openai.com/")
    assert runner.api_calls == 0


def test_registration_retry_is_explicit_and_cannot_select_an_account(runner):
    assert runner.command("chatgpt/login", {"retry_registration": True})["ok"]
    assert runner._chatgpt_auth.calls == [("retry", None)]
    for action, payload in [
        ("login", {"retry_registration": True, "account_id": "account-A"}),
        ("logout", {"retry_registration": True}),
        ("login", {"retry_registration": "true"}),
    ]:
        with pytest.raises(ValueError, match="注册重试"):
            runner.command("chatgpt/" + action, payload)


@pytest.mark.parametrize("closed", [False, True])
def test_transport_still_exiting_blocks_new_run_and_auth_changes(runner, closed):
    # A deadline/cancel can resolve the outer Future while HTTP I/O is still
    # waiting for response headers. A new policy must not bypass that worker.
    from types import SimpleNamespace
    policy = SimpleNamespace(transport_busy=True, close=MagicMock(), cancel=MagicMock())
    runner.policy = policy
    runner.future = None
    runner.running = False
    if closed:
        runner.close_policy()
    assert runner.transport_busy
    for action, payload in [
        ("diagnose", {"stage": "text", "credential_source": "chatgpt_plan"}),
        ("start", {"task": "Wait", "credential_source": "manual"}),
        ("chatgpt/logout", {}), ("chatgpt/login", {}),
        ("chatgpt/select", {"account_id": "account-A"}),
    ]:
        with pytest.raises(ValueError, match="请求"):
            runner.command(action, payload)
    assert not runner._chatgpt_auth.calls
    policy.transport_busy = False
    assert not runner.transport_busy
    assert runner.command("chatgpt/login", {})["ok"]
