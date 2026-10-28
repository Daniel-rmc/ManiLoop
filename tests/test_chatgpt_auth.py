"""OAuth fixtures only: no user credentials, browser login or model requests."""

import base64
import hashlib
from http.client import HTTPConnection
import json
import multiprocessing
import os
from pathlib import Path
import socket
import stat
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

from maniloop.providers import chatgpt_auth as auth


class FakeServer:
    next_port = 43100

    def __init__(self, address, handler):
        assert address == ("127.0.0.1", 0)
        self.server_port = self.next_port
        FakeServer.next_port += 1
        self.closed = False

    def serve_forever(self):
        pass

    def shutdown(self):
        pass

    def server_close(self):
        self.closed = True


class FixtureHTTP:
    def __init__(self):
        self.calls = []
        self.error = None
        self.scopes = auth.SCOPES
        self.revoked = False

    def __call__(self, method, url, *, data=None):
        self.calls.append((method, url, data))
        if self.error:
            raise self.error
        if url == auth.DISCOVERY_URL:
            return {"issuer": auth.ISSUER, "jwks_uri": auth.ISSUER + "/keys", "revocation_endpoint": auth.ISSUER + "/revoke"}
        if url.endswith("/revoke"):
            self.revoked = True
            return {}
        assert url == auth.TOKEN_URL
        refreshed = data["grant_type"] == "refresh_token"
        return {"access_token": "ACCESS-REFRESHED" if refreshed else "ACCESS-SECRET",
                "refresh_token": "REFRESH-ROTATED" if refreshed else "REFRESH-SECRET",
                "id_token": "ID-SECRET", "token_type": "Bearer", "scope": self.scopes, "expires_in": 3600}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "ThreadingHTTPServer", FakeServer)
    now = [1_800_000_000.0]
    subject = ["subject-a"]
    http = FixtureHTTP()

    def validator(token, client, nonce):
        assert token == "ID-SECRET"
        return {"iss": auth.ISSUER, "aud": client, "nonce": nonce, "exp": now[0] + 3600,
                "sub": subject[0], "email": "person@example.test"}

    store = auth.ChatGPTAuthStore(tmp_path / "auth", http=http, clock=lambda: now[0], validate_id_token=validator)
    yield store, http, now, subject
    store.close()


def begin(store, account_id=None, **kwargs):
    result = store.start_login(account_id, **kwargs)
    params = {k: v[0] for k, v in parse_qs(urlsplit(result["authorization_url"]).query).items()}
    return result, params


def finish(store, params, client="oaiapp-fixture", **changes):
    args = {"code": "CODE-SECRET", "state": params["state"], "client_id": client, **changes}
    return store.handle_callback("/auth/callback?" + urlencode(args))


def login(store, client="oaiapp-fixture", account_id=None):
    _, params = begin(store, account_id)
    finish(store, params, client)
    return store.status()["active_account_id"]


def read_state(store):
    return json.loads((store.directory / "sessions.json").read_text())


def test_registration_pkce_scope_stable_host_and_public_views(setup):
    store, http, _, _ = setup
    result, params = begin(store)
    pending = store._pending
    assert urlsplit(result["authorization_url"]).path == "/api/accounts/authorize"
    assert params["client_id"] == "dynamic_agent_client"
    assert params["agent_name_hint"] == "ManiLoop"
    assert params["resource"] == auth.RESOURCE
    assert set(params["scope"].split()) == set(auth.SCOPES.split())
    assert params["redirect_uri"].startswith("http://127.0.0.1:")
    assert params["redirect_uri"].endswith("/auth/callback")
    assert "id_token_hint" not in params
    assert params["code_challenge"] == base64.urlsafe_b64encode(hashlib.sha256(pending["verifier"].encode()).digest()).decode().rstrip("=")
    assert len(params["state"]) >= 32 and params["state"] != params["nonce"]
    finish(store, params)
    status = store.status()
    assert status["logged_in"] and status["plan_enabled"] and not status["pending"]
    assert len(status["accounts"]) == 1
    assert all(secret not in json.dumps(status) for secret in ["ACCESS-SECRET", "REFRESH-SECRET", "ID-SECRET", "CODE-SECRET"])
    token_call = http.calls[0][2]
    assert token_call["redirect_uri"] == params["redirect_uri"]
    assert token_call["client_id"] == "oaiapp-fixture"
    assert token_call["code_verifier"] == pending["verifier"]
    if os.name != "nt":
        assert stat.S_IMODE(store.directory.stat().st_mode) == 0o700
        assert stat.S_IMODE((store.directory / "sessions.json").stat().st_mode) == 0o600
    _, again = begin(store, status["active_account_id"])
    assert again["ext_agent_host_id"] == params["ext_agent_host_id"]
    assert again["client_id"] == "oaiapp-fixture"
    assert "agent_name_hint" not in again and "id_token_hint" not in again
    assert again["state"] != params["state"]


def test_bad_state_duplicate_params_and_replay_never_exchange(setup):
    store, http, _, _ = setup
    _, params = begin(store)
    for path in ["/auth/callback?state=wrong&code=private", "/wrong?state=" + params["state"],
                 "/auth/callback?state=" + params["state"] + "&state=" + params["state"]]:
        with pytest.raises(auth.ChatGPTAuthError):
            store.handle_callback(path)
    assert not http.calls and store.status()["pending"]
    finish(store, params)
    with pytest.raises(auth.ChatGPTAuthError):
        finish(store, params)
    assert len(http.calls) == 1


@pytest.mark.parametrize("client", ["", "dynamic_agent_client"])
def test_new_registration_requires_issued_client(setup, client):
    store, http, _, _ = setup
    _, params = begin(store)
    with pytest.raises(auth.ChatGPTAuthError):
        finish(store, params, client)
    assert not http.calls and not store.status()["accounts"]


def test_declined_expired_or_cancelled_never_replace_existing(setup):
    store, http, now, _ = setup
    original = login(store)
    before = read_state(store)
    _, params = begin(store)
    with pytest.raises(auth.ChatGPTAuthError):
        finish(store, params, error="access_denied")
    assert read_state(store) == before
    _, params = begin(store)
    now[0] += 601
    assert not store.status()["pending"]
    with pytest.raises(auth.ChatGPTAuthError):
        finish(store, params)
    _, params = begin(store)
    store.cancel_login()
    with pytest.raises(auth.ChatGPTAuthError):
        finish(store, params)
    assert store.status()["active_account_id"] == original
    assert len(http.calls) == 1


def test_returning_identity_or_client_mismatch_does_not_overwrite(setup):
    store, http, _, subject = setup
    original = login(store)
    before = read_state(store)
    _, params = begin(store, original)
    with pytest.raises(auth.ChatGPTAuthError):
        finish(store, params, "another-client")
    assert len(http.calls) == 1
    subject[0] = "subject-b"
    _, params = begin(store, original)
    with pytest.raises(auth.ChatGPTAuthError):
        finish(store, params)
    assert read_state(store) == before


def test_multiple_registrations_same_email_and_pinned_account(setup):
    store, http, _, subject = setup
    first = login(store)
    subject[0] = "subject-b"
    second = login(store, "oaiapp-second")
    assert first != second
    assert len(store.status()["accounts"]) == 2
    assert store.access_token(first) == "ACCESS-SECRET"
    store.select_account(first)
    assert store.status()["active_account_id"] == first
    store.logout(second)
    assert store.status()["active_account_id"] == first
    assert store.access_token(first) == "ACCESS-SECRET"
    assert http.revoked


def test_sign_in_without_plan_permission_cannot_infer_and_reconsents(setup):
    store, http, _, _ = setup
    http.scopes = "openid profile email offline_access"
    account = login(store)
    assert store.status()["logged_in"] and not store.status()["plan_enabled"]
    with pytest.raises(auth.ChatGPTAuthError, match="套餐"):
        store.access_token()
    _, params = begin(store, account)
    assert params["prompt"] == "consent"


def test_refresh_rotates_atomically_and_uses_saved_client(setup):
    store, http, now, _ = setup
    account = login(store)
    now[0] += 3550
    assert store.access_token(account) == "ACCESS-REFRESHED"
    record = read_state(store)["accounts"][account]
    assert record["refresh_token"] == "REFRESH-ROTATED"
    assert record["expires_at"] == now[0] + 3600
    assert record["id_token"] == "ID-SECRET"
    body = http.calls[-1][2]
    assert body["client_id"] == "oaiapp-fixture" and body["resource"] == auth.RESOURCE
    assert body["refresh_token"] == "REFRESH-SECRET" and "scope" not in body
    assert store.access_token() == "ACCESS-REFRESHED" and len(http.calls) == 2


def test_transient_refresh_preserves_credentials_terminal_error_removes_tokens(setup):
    store, http, now, _ = setup
    account = login(store)
    before = read_state(store)
    now[0] += 3601
    http.error = auth.ChatGPTAuthError("暂时不可用", category="connection")
    with pytest.raises(auth.ChatGPTAuthError):
        store.access_token()
    assert read_state(store) == before
    http.error = auth.ChatGPTAuthError("失效", code="refresh_token_reused")
    with pytest.raises(auth.ChatGPTAuthError):
        store.access_token()
    record = read_state(store)["accounts"][account]
    assert record["client_id"] == "oaiapp-fixture"
    assert not any(field in record for field in auth._TOKEN_FIELDS)
    assert not store.status()["logged_in"]


def test_remote_logout_failure_still_clears_local_tokens_keeps_registration(setup):
    store, http, _, _ = setup
    account = login(store)
    http.error = auth.ChatGPTAuthError("网络错误", category="connection")
    result = store.logout()
    assert not result["revocation_confirmed"] and not result["logged_in"]
    assert "未确认" in result["error"]
    assert read_state(store)["accounts"][account]["client_id"] == "oaiapp-fixture"


def test_exchange_remains_pending_and_cancellation_rejects_late_result(setup):
    store, http, _, _ = setup
    original_http = store._http
    started, release = threading.Event(), threading.Event()

    def delayed(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return original_http(*args, **kwargs)

    store._http = delayed
    _, params = begin(store)
    errors = []

    def worker():
        try:
            finish(store, params)
        except auth.ChatGPTAuthError as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    assert started.wait(2)
    assert store.status()["pending"]
    with pytest.raises(auth.ChatGPTAuthError):
        finish(store, params)
    begin(store)  # cancels old attempt and starts a separate listener
    new_server = store._server
    release.set()
    thread.join(5)
    assert errors and not read_state(store)["accounts"]
    assert store.status()["pending"] and not new_server.closed


def test_failed_registration_retry_is_explicit_and_new_account_is_fresh(setup):
    store, http, _, _ = setup
    _, params = begin(store)
    http.error = auth.ChatGPTAuthError("授权码失效", code="invalid_grant")
    with pytest.raises(auth.ChatGPTAuthError):
        finish(store, params)
    assert store.status()["registration_retry_available"]
    _, fresh = begin(store)
    assert fresh["client_id"] == "dynamic_agent_client"
    _, retry = begin(store, retry_registration=True)
    assert retry["client_id"] == "oaiapp-fixture"


@pytest.mark.parametrize("field,value", [("access_token", ""), ("token_type", 123), ("expires_in", -1),
                                         ("expires_in", float("nan")), ("scope", None)])
def test_invalid_token_response_is_not_persisted(setup, field, value):
    store, http, _, _ = setup
    original = store._http

    def malformed(*args, **kwargs):
        return {**original(*args, **kwargs), field: value}

    store._http = malformed
    _, params = begin(store)
    with pytest.raises(auth.ChatGPTAuthError):
        finish(store, params)
    assert not read_state(store)["accounts"]


@pytest.mark.skipif(os.name == "nt", reason="Unix permission and symlink semantics")
def test_rejects_insecure_or_symlinked_session_store(setup, tmp_path):
    store, _, _, _ = setup
    login(store)
    path = store.directory / "sessions.json"
    path.chmod(0o644)
    with pytest.raises(auth.ChatGPTAuthError):
        store.status()
    path.chmod(0o600)
    original = path.read_bytes()
    path.unlink()
    target = tmp_path / "other"
    target.write_bytes(original)
    path.symlink_to(target)
    with pytest.raises(auth.ChatGPTAuthError):
        store.status()
    assert target.read_bytes() == original


@pytest.mark.parametrize("url", ["http://auth.openai.com/key", "https://evil.example/key", "https://auth.openai.com.evil/key",
                                  "https://user:secret@auth.openai.com/key", "https://auth.openai.com/key?token=secret"])
def test_discovery_urls_must_be_fixed_official_https(url):
    with pytest.raises(auth.ChatGPTAuthError) as caught:
        auth._official_auth_url(url)
    assert "secret" not in str(caught.value)


def _cross_process_refresh(directory, counter, results):
    def request(method, url, *, data=None):
        with counter.get_lock():
            counter.value += 1
        time.sleep(0.1)
        return {"access_token": "NEXT-TOKEN", "refresh_token": "NEXT-REFRESH", "token_type": "Bearer",
                "expires_in": 3600, "scope": auth.SCOPES}

    store = auth.ChatGPTAuthStore(directory, http=request)
    results.put(store.access_token())


def test_cross_process_refresh_is_serialized(tmp_path):
    directory = tmp_path / "parallel-auth"
    store = auth.ChatGPTAuthStore(directory)
    with store._locked():
        state = store._read()
        state["accounts"]["fixture"] = {"client_id": "oaiapp-test", "subject": "s", "scopes": auth.SCOPES.split(),
            "access_token": "OLD", "refresh_token": "OLD-REFRESH", "expires_at": time.time() - 1}
        state["active"] = "fixture"
        store._write(state)
    context = multiprocessing.get_context("spawn")
    counter, results = context.Value("i", 0), context.Queue()
    processes = [context.Process(target=_cross_process_refresh, args=(str(directory), counter, results)) for _ in range(2)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(15)
        assert process.exitcode == 0
    assert results.get(timeout=1) == results.get(timeout=1) == "NEXT-TOKEN"
    assert counter.value == 1


def test_real_jwks_signature_and_claim_validation(tmp_path):
    jwt = pytest.importorskip("jwt")
    crypto = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.rsa")
    private = crypto.generate_private_key(public_exponent=65537, key_size=2048)
    other = crypto.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwk.update(kid="fixture", use="sig", alg="RS256")

    def http(method, url, **_kwargs):
        if url == auth.DISCOVERY_URL:
            return {"issuer": auth.ISSUER, "jwks_uri": auth.ISSUER + "/keys", "revocation_endpoint": auth.ISSUER + "/revoke"}
        assert url == auth.ISSUER + "/keys"
        return {"keys": [jwk]}

    store = auth.ChatGPTAuthStore(tmp_path, http=http)
    base = {"iss": auth.ISSUER, "aud": "oaiapp-test", "exp": time.time() + 300, "sub": "verified-user", "nonce": "NONCE"}

    def encoded(claims, key=private):
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "fixture"})

    assert store._validate_identity(encoded(base), "oaiapp-test", "NONCE")["sub"] == "verified-user"
    for bad in [encoded(base, other), encoded({**base, "iss": "https://other.example"}),
                encoded({**base, "aud": "wrong-client"}), encoded({**base, "exp": time.time() - 10}),
                encoded({**base, "nonce": "wrong"}), encoded({**base, "aud": ["oaiapp-test", "other"]}),
                jwt.encode(base, "", algorithm="none")]:
        with pytest.raises(auth.ChatGPTAuthError):
            store._validate_identity(bad, "oaiapp-test", "NONCE")


def test_loopback_callback_host_guard_and_secret_free_html(tmp_path):
    http = FixtureHTTP()

    def validator(token, client, nonce):
        return {"iss": auth.ISSUER, "aud": client, "nonce": nonce, "exp": time.time() + 300, "sub": "s"}

    store = auth.ChatGPTAuthStore(tmp_path / "callback", http=http, validate_id_token=validator)
    try:
        _, params = begin(store)
        port = urlsplit(params["redirect_uri"]).port
        callback = "/auth/callback?" + urlencode({"code": "CODE-SECRET", "state": params["state"], "client_id": "oaiapp-test"})
        connection = HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("GET", callback, headers={"Host": "attacker.example"})
        response = connection.getresponse()
        assert response.status == 400
        response.read()
        connection.close()
        assert store.status()["pending"] and not http.calls
        connection = HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("GET", callback)
        response = connection.getresponse()
        assert response.status == 200 and response.getheader("Cache-Control") == "no-store"
        body = response.read().decode()
        connection.close()
        assert "CODE-SECRET" not in body and params["state"] not in body
        assert store.status()["logged_in"]
    finally:
        store.close()


def test_lost_browser_connection_does_not_cancel_loopback_authorization(tmp_path):
    """The listener belongs to the login attempt, not a browser TCP connection.

    COOP may sever a popup reference; only an explicit cancel API may end login.
    This test uses a fresh test-only listener and synthetic OAuth credentials.
    """
    fixture_http = FixtureHTTP()

    def validator(token, client, nonce):
        return {"iss": auth.ISSUER, "aud": client, "nonce": nonce,
                "exp": time.time() + 300, "sub": "offline-browser"}

    store = auth.ChatGPTAuthStore(tmp_path / "disconnected-browser", http=fixture_http,
                                  validate_id_token=validator)
    try:
        _, params = begin(store)
        port = urlsplit(params["redirect_uri"]).port
        # A browser/socket can disappear before any callback request is sent.
        with socket.create_connection(("127.0.0.1", port), timeout=5):
            pass
        # Polls from the workbench and unrelated requests must keep login alive.
        for _ in range(3):
            assert store.status()["pending"]
        connection = HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("GET", "/favicon.ico")
        response = connection.getresponse()
        assert response.status == 404
        response.read()
        connection.close()
        assert store.status()["pending"] and not fixture_http.calls
        # A new browser connection can complete the original pending attempt.
        callback = "/auth/callback?" + urlencode({"code": "OFFLINE-CODE", "state": params["state"],
                                                  "client_id": "oaiapp-offline-browser"})
        connection = HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("GET", callback)
        response = connection.getresponse()
        assert response.status == 200
        response.read()
        connection.close()
        status = store.status()
        assert status["logged_in"] and not status["pending"] and not status["error"]
        assert len(fixture_http.calls) == 1
    finally:
        store.close()
