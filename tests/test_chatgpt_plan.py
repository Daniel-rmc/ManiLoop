"""Offline direct-plan protocol tests. No account, CLI, or model is contacted."""
import json
import os
import time
import threading
from unittest.mock import Mock, patch

import pytest
httpx = pytest.importorskip("httpx")

from maniloop.providers.chatgpt_plan import API_BASE, ChatGPTPlanPolicy, list_plan_models
from maniloop.providers.responses import GPTPolicy, PolicyError

REAL_CLIENT = httpx.Client
OBS = {"observation_id": "obs-1", "frame_id": "base", "tcp_position": [0.3, 0, 0.2]}
IMAGES = {"external": b"external-pixels", "wrist": b"wrist-pixels", "previous/external": b"older-pixels"}
ACTION = {"observation_id": "obs-1", "kind": "wait", "delta_position": [0, 0, 0],
          "delta_rotation": [0, 0, 0], "gripper_opening": 0, "pixel": [0, 0],
          "camera": "", "explanation": "Check the supplied scene."}


def final(text=None, **changes):
    value = {"id": "resp-offline", "status": "completed", "error": None, "incomplete_details": None,
             "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
             "output": [{"type": "message", "role": "assistant", "status": "completed",
                         "content": [{"type": "output_text", "text": text or json.dumps(ACTION)}]}]}
    value.update(changes)
    return value


def sse(*events):
    return "".join("data: " + (event if isinstance(event, str) else json.dumps(event)) + "\n\n" for event in events)


def done(response=None):
    return {"type": "response.completed", "response": response or final()}


def setup_transport(handler):
    return patch("maniloop.providers.chatgpt_plan.httpx.Client", side_effect=lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))


def policy(**options):
    return ChatGPTPlanPolicy(auth_store=Mock(access_token=Mock(return_value="offline-token")), request_options=options)


def decide(p, **changes):
    args = dict(task="Move the bowl", observation=OBS, images=IMAGES, history=[{"feedback": {"status": "completed"}}], geometry_results=[])
    args.update(changes)
    return p.decide(**args)


def test_fixed_url_shared_semantics_and_no_api_key_fallback():
    captured = {}
    p = policy()
    def handler(request):
        captured["request"] = json.loads(request.content)
        assert str(request.url) == API_BASE + "/responses"
        assert request.headers["authorization"] == "Bearer offline-token"
        assert "openai-organization" not in request.headers
        assert "openai-project" not in request.headers
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse(done(), "[DONE]"))
    with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://wrong.invalid", "OPENAI_API_KEY": "never-use-me", "OPENAI_ORG_ID": "wrong", "OPENAI_PROJECT_ID": "wrong"}), setup_transport(handler):
        assert decide(p) == ACTION
    request = captured["request"]
    assert request["store"] is False and request["stream"] is True
    assert "max_output_tokens" not in request
    assert "previous_response_id" not in request
    assert request["reasoning"] == {"effort": "low"}
    assert p.last_usage["total_tokens"] == 120
    assert "offline-token" not in json.dumps(p.last_request_manifest)
    with patch("maniloop.providers.responses.OpenAI"):
        api = GPTPolicy(api_key="offline-api-key", request_options={"reasoning_effort": "low"})
    api.client.responses.create.return_value = final()
    assert decide(api) == ACTION
    api_request = api.client.responses.create.call_args.kwargs
    for field in ("instructions", "input", "text", "reasoning", "store"):
        assert request[field] == api_request[field]
    assert p.last_request_manifest["sensor_request_sha256"] == api.last_request_manifest["sensor_request_sha256"]
    assert len(p.last_request_manifest["images"]) == 3
    assert api_request["max_output_tokens"] == 4096


@pytest.mark.parametrize("option", [{"max_output_tokens": 4096}, {"server_max_output_tokens": 100}, {"temperature": 0}, {"reasoning_effort": []}, {"timeout_seconds": True}])
def test_unsupported_budgets_rejected(option):
    with pytest.raises(PolicyError) as exc:
        policy(**option)
    assert exc.value.category == "configuration"


@pytest.mark.parametrize("body", [sse({"type": "response.output_text.delta", "delta": json.dumps(ACTION)}), sse(done(), done()), sse(done(), {"type": "response.output_text.delta", "delta": "late"}), sse("[DONE]"), sse({"type": "response.incomplete"}), sse("bad-json"), sse(done(final(status="in_progress"))), sse(done(final(output=[{"type": "function_call", "name": "shell"}]))), sse(done(final(text=json.dumps({**ACTION, "observation_id": "stale"}))))])
def test_only_one_valid_completed_response_can_produce_action(body):
    with setup_transport(lambda _: httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)):
        with pytest.raises(PolicyError):
            decide(policy())


@pytest.mark.parametrize("status,category", [(401, "authentication"), (403, "authorization"), (429, "rate_limit"), (500, "http_error"), (302, "http_error")])
def test_errors_sanitized_and_not_retried(status, category):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="private-secret@example.invalid", headers={"location": "https://wrong.invalid"})
    with setup_transport(handler):
        with pytest.raises(PolicyError) as exc:
            decide(policy())
    assert len(calls) == 1
    assert exc.value.category == category
    assert "private-secret" not in str(exc.value)


def test_cancel_before_request_never_fetches_token():
    p = policy()
    p.cancel()
    with pytest.raises(PolicyError) as exc:
        decide(p)
    assert exc.value.category == "interrupted"
    p.auth_store.access_token.assert_not_called()


def test_total_deadline_covers_stream():
    class SlowStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b': initial\n\n'
            time.sleep(0.03)
            yield sse(done()).encode()
    with setup_transport(lambda _: httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=SlowStream())):
        with pytest.raises(PolicyError) as exc:
            decide(policy(timeout_seconds=0.01))
    assert exc.value.category == "timeout"


def test_cancel_during_stream_discards_final_action():
    p = policy()
    class CancelStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b': initial\n\n'
            p.cancel()
            yield sse(done()).encode()
    with setup_transport(lambda _: httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=CancelStream())):
        with pytest.raises(PolicyError) as exc:
            decide(p)
    assert exc.value.category == "interrupted"


def test_sensor_truth_rejected_before_authentication():
    p = policy()
    with pytest.raises(PolicyError):
        decide(p, history=[{"native_success": True}])
    p.auth_store.access_token.assert_not_called()


def test_diagnostics_have_explicit_instructions_and_no_cap():
    def handler(request):
        body = json.loads(request.content)
        assert body["instructions"]
        assert "max_output_tokens" not in body
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse(done(final(text="READY"))))
    with setup_transport(handler):
        result = policy().diagnose("text", "", OBS, IMAGES)
    assert result["output"] == "READY" and result["executed"] is False


def test_models_uses_official_plan_shape_and_visibility():
    store = Mock(access_token=Mock(return_value="offline-token"))
    def handler(request):
        assert str(request.url) == API_BASE + "/models"
        return httpx.Response(200, json={"models": [{"slug": "gpt-6-astra", "visibility": "list"}, {"slug": "hidden", "visibility": "hide"}, {"id": "wrong-format"}, {"slug": "gpt-6-astra", "visibility": "list"}]})
    with setup_transport(handler):
        assert list_plan_models(store, "selected") == ["gpt-6-astra"]
    store.access_token.assert_called_once_with("selected")


@pytest.mark.parametrize("during", ["headers", "stream"])
def test_deadline_returns_while_network_is_blocked(during):
    release = threading.Event()
    p = policy(timeout_seconds=0.03)
    class BlockedStream(httpx.SyncByteStream):
        def __iter__(self):
            release.wait(2)
            yield sse(done()).encode()
    def handler(_):
        if during == "headers":
            release.wait(2)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=BlockedStream())
    try:
        with setup_transport(handler):
            started = time.monotonic()
            with pytest.raises(PolicyError) as exc:
                decide(p)
            assert exc.value.category == "timeout"
            assert time.monotonic() - started < 0.5
            with pytest.raises(PolicyError):
                decide(p)  # Never overlap a still-stopping request.
            assert p.last_response_id is None
    finally:
        release.set()
        p._worker.join(1)


def test_cancel_returns_while_headers_are_blocked():
    release, entered = threading.Event(), threading.Event()
    p = policy(timeout_seconds=2)
    def handler(_):
        entered.set()
        release.wait(2)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse(done()))
    def cancel_when_connected():
        entered.wait(1)
        p.cancel()
    canceller = threading.Thread(target=cancel_when_connected)
    canceller.start()
    try:
        with setup_transport(handler):
            started = time.monotonic()
            with pytest.raises(PolicyError) as exc:
                decide(p)
            assert exc.value.category == "interrupted"
            assert time.monotonic() - started < 0.5
            assert p.last_response_id is None
    finally:
        release.set()
        p._worker.join(1)
        canceller.join(1)


def test_auto_is_recorded_as_effective_low():
    p = policy(reasoning_effort="auto")
    assert p.reasoning_effort == "low"
    assert p.request_options["reasoning_effort"] == "low"


def test_stream_quota_error_has_safe_category():
    body = sse({"type": "error", "error": {"code": "usage_limit_reached", "message": "private-account"}})
    with setup_transport(lambda _: httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)):
        with pytest.raises(PolicyError) as exc:
            decide(policy())
    assert exc.value.category == "rate_limit"
    assert "private-account" not in str(exc.value)


def test_client_limit_is_distinct_from_server_budget():
    body = sse(done(final(text="X" * 300)))
    with setup_transport(lambda _: httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)):
        with pytest.raises(PolicyError, match="client size limit"):
            decide(policy(client_max_response_chars=256))


@pytest.mark.parametrize("prefix", [
    {"type": "response.output_item.added", "item": {"type": "function_call", "name": "shell"}},
    {"type": "response.function_call_arguments.delta", "delta": "{}"},
    {"type": "response.mcp_call.completed"},
])
def test_tool_events_cannot_be_hidden_by_valid_terminal(prefix):
    with setup_transport(lambda _: httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse(prefix, done()))):
        with pytest.raises(PolicyError, match="tool"):
            decide(policy())


def test_transport_rejects_hard_cap_before_auth():
    p = policy()
    with pytest.raises(PolicyError) as exc:
        p._request_text({"input": [], "max_output_tokens": 100})
    assert exc.value.category == "configuration"
    p.auth_store.access_token.assert_not_called()


def test_stream_duplicate_keys_are_rejected():
    body = 'data: {"type":"response.completed","type":"response.created"}\n\n'
    with setup_transport(lambda _: httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)):
        with pytest.raises(PolicyError, match="invalid stream"):
            decide(policy())


def test_auth_temporary_failure_does_not_request_new_login():
    p = policy()
    class AuthNetworkError(Exception):
        category = "connection"
    p.auth_store.access_token.side_effect = AuthNetworkError("private-secret")
    with pytest.raises(PolicyError) as exc:
        decide(p)
    assert exc.value.category == "connection"
    assert "sign in" not in str(exc.value) and "private-secret" not in str(exc.value)


@pytest.mark.parametrize("code,category", [
    ("subscription_sharing_usage_limit_exceeded", "rate_limit"),
    ("subscription_sharing_usage_unavailable", "service_unavailable"),
    ("subscription_sharing_unsupported_capability", "unsupported_capability"),
    ("subscription_sharing_invalid_user", "authentication"),
    ("subscription_sharing_user_not_eligible", "plan_not_eligible"),
    ("subscription_sharing_route_not_supported", "route_not_supported"),
    ("chatpass_v2_scope_not_authorized", "authorization"),
    ("chatpass_v2_invalid_authorization_context", "authorization"),
    ("subscription_sharing_user_unavailable", "service_unavailable"),
])
@pytest.mark.parametrize("transport", ["http", "sse"])
def test_documented_error_codes_have_safe_recovery_and_manifest(code, category, transport):
    p = policy()
    error = {"code": code, "param": "model", "message": "private-account-or-token"}
    def handler(_):
        if transport == "http":
            return httpx.Response(403, json={"error": error})
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              text=sse({"type": "response.failed", "response": {"error": error}}))
    with setup_transport(handler):
        with pytest.raises(PolicyError) as exc:
            decide(p)
    assert exc.value.category == category and exc.value.code == code
    assert exc.value.param == "model"
    assert p.last_request_manifest["error"]["code"] == code
    assert "private-account-or-token" not in str(exc.value)
    assert "private-account-or-token" not in json.dumps(p.last_request_manifest)


@pytest.mark.parametrize("status", [401, 403, 503])
def test_admission_detail_does_not_invent_revocation(status):
    p = policy()
    with setup_transport(lambda _: httpx.Response(status, json={"detail": "private diagnosis token revoked"})):
        with pytest.raises(PolicyError) as exc:
            decide(p)
    assert exc.value.code is None
    assert "sign in again" not in str(exc.value)
    assert "revoked" not in str(exc.value)
    assert exc.value.http_status == status
    assert "private" not in str(exc.value)


def test_unknown_code_and_param_are_not_retained():
    p = policy()
    with setup_transport(lambda _: httpx.Response(400, json={"error": {"code": "private-secret", "param": "private-param", "message": "private-body"}})):
        with pytest.raises(PolicyError) as exc:
            decide(p)
    assert exc.value.code is None and exc.value.param is None
    assert "private" not in json.dumps(p.last_request_manifest)


def test_terminal_usage_and_reported_model_are_recorded_without_snapshot_claim():
    p = policy()
    response = final(model="gpt-6-astra-reported", usage={"input_tokens": 100, "output_tokens": 20,
        "output_tokens_details": {"reasoning_tokens": 13}, "input_tokens_details": {"cached_tokens": 42}})
    with setup_transport(lambda _: httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse(done(response)))):
        decide(p)
    assert p.last_usage == {"input_tokens": 100, "output_tokens": 20, "reasoning_tokens": 13, "cached_input_tokens": 42}
    assert p.last_response_model == "gpt-6-astra-reported"
    assert p.last_request_manifest["model_reported"] == "gpt-6-astra-reported"
    assert p.last_request_manifest["model_reported_scope"] == "provider_identifier_not_snapshot_attestation"
    with patch("maniloop.providers.responses.OpenAI"):
        api = GPTPolicy(api_key="offline-api-key")
    api.client.responses.create.return_value = response
    decide(api)
    assert api.last_usage == p.last_usage
    assert api.last_response_model == p.last_response_model


@pytest.mark.parametrize("value", [None, True, -1, 2.5, "12"])
def test_invalid_or_missing_usage_details_are_not_zero_filled(value):
    p = policy()
    response = final(usage={"output_tokens_details": {"reasoning_tokens": value}, "input_tokens_details": {"cached_tokens": value}})
    with setup_transport(lambda _: httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse(done(response)))):
        decide(p)
    assert "reasoning_tokens" not in p.last_usage
    assert "cached_input_tokens" not in p.last_usage
    assert "model_reported" not in p.last_request_manifest


def test_explicit_zero_usage_is_preserved():
    p = policy()
    response = final(usage={"output_tokens_details": {"reasoning_tokens": 0}, "input_tokens_details": {"cached_tokens": 0}})
    with setup_transport(lambda _: httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse(done(response)))):
        decide(p)
    assert p.last_usage == {"reasoning_tokens": 0, "cached_input_tokens": 0}


@pytest.mark.parametrize("interruption", ["timeout", "cancel"])
def test_transport_busy_remains_true_until_interrupted_worker_exits(interruption):
    release, entered = threading.Event(), threading.Event()
    p = policy(timeout_seconds=0.03 if interruption == "timeout" else 2)
    assert p.transport_busy is False
    with pytest.raises(AttributeError):
        p.transport_busy = True
    def handler(_):
        entered.set()
        release.wait(2)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse(done()))
    canceller = None
    if interruption == "cancel":
        def cancel_when_entered():
            entered.wait(1)
            p.cancel()
        canceller = threading.Thread(target=cancel_when_entered)
        canceller.start()
    try:
        with setup_transport(handler):
            with pytest.raises(PolicyError):
                decide(p)
            assert entered.is_set()
            assert p.transport_busy is True
            with pytest.raises(PolicyError):
                p.reset()
            with pytest.raises(PolicyError):
                decide(p)
    finally:
        release.set()
        p._worker.join(1)
        if canceller:
            canceller.join(1)
    assert p.transport_busy is False
    assert p.last_response_id is None


def test_non_sse_json_is_diagnosed_but_never_accepted():
    import hashlib
    p = policy()
    body = json.dumps({"object": "response", "status": "completed", "output": "private-output",
                       "private-field": "private-secret", "error": {"code": "subscription_sharing_usage_unavailable", "message": "private-message"}}).encode()
    with setup_transport(lambda _: httpx.Response(200, headers={"content-type": "Application/JSON; charset=utf-8"}, content=body)):
        with pytest.raises(PolicyError, match="media type: application/json"):
            decide(p)
    manifest = p.last_request_manifest
    assert manifest["http"] == {"http_status": 200, "media_type": "application/json", "declared_mime": "application/json", "parsed_format": "unverified"}
    diag = manifest["body_diagnostic"]
    assert diag == {"prefix_bytes": len(body), "prefix_sha256": hashlib.sha256(body).hexdigest(),
                    "truncated": False, "is_json": True, "top_level_fields": ["error", "object", "output", "status"],
                    "object_is_response": True, "response_status": "completed", "error_code": "subscription_sharing_usage_unavailable", "framing": "json"}
    assert "private" not in json.dumps(manifest)
    assert p.last_response_id is None


@pytest.mark.parametrize("mime", ["text/html", "text/plain", "", "application/vnd.example+json", "x" * 300])
def test_non_sse_media_is_allowlisted_and_body_is_bounded(mime):
    import hashlib
    p = policy()
    body = b"private-page" * 10000
    with setup_transport(lambda _: httpx.Response(200, headers={"content-type": mime}, content=body)):
        with pytest.raises(PolicyError):
            decide(p)
    diag = p.last_request_manifest["body_diagnostic"]
    assert diag["prefix_bytes"] == 65536 and diag["truncated"] is True
    assert diag["prefix_sha256"] == hashlib.sha256(body[:65536]).hexdigest()
    assert diag["is_json"] is False
    assert "private" not in json.dumps(p.last_request_manifest)
    assert p.last_request_manifest["http"]["media_type"] == (mime if mime in {"text/html", "text/plain", "application/vnd.example+json"} else "missing" if not mime else "other")


def test_http_metadata_recorded_for_valid_sse_and_status_error():
    p = policy()
    with setup_transport(lambda _: httpx.Response(200, headers={"content-type": "text/event-stream; charset=utf-8"}, text=sse(done()))):
        decide(p)
    assert p.last_request_manifest["http"] == {"http_status": 200, "media_type": "text/event-stream", "declared_mime": "text/event-stream", "parsed_format": "sse"}
    with setup_transport(lambda _: httpx.Response(503, json={"detail": "private"})):
        with pytest.raises(PolicyError):
            decide(p)
    assert p.last_request_manifest["http"] == {"http_status": 503, "media_type": "application/json", "declared_mime": "application/json", "parsed_format": "unverified"}
    assert "body_diagnostic" not in p.last_request_manifest


def test_remote_protocol_failure_is_safe_connection_error():
    p = policy()
    def handler(_):
        raise httpx.RemoteProtocolError("private proxy headers")
    with setup_transport(handler):
        with pytest.raises(PolicyError) as exc:
            decide(p)
    assert exc.value.category == "connection"
    assert "private" not in str(exc.value)
    assert "http" not in p.last_request_manifest


@pytest.mark.parametrize("mime", [None, "text/plain", "application/json", "application/octet-stream"])
@pytest.mark.parametrize("prefix,framing", [(b"", "sse_data"), (b"event: response.completed\n", "sse_event"), (b"\xef\xbb\xbf: heartbeat\n\n", "sse_data")])
def test_strict_sse_does_not_require_correct_declared_mime(mime, prefix, framing):
    p = policy()
    headers = {} if mime is None else {"content-type": mime}
    body = prefix + sse(done()).encode()
    with setup_transport(lambda _: httpx.Response(200, headers=headers, content=body)):
        assert decide(p) == ACTION
    http = p.last_request_manifest["http"]
    assert http["declared_mime"] == (mime or "missing")
    assert http["parsed_format"] == "sse"
    assert p.last_request_manifest["body_diagnostic"]["framing"] == framing


@pytest.mark.parametrize("body,framing", [
    (b"<!DOCTYPE html><html>private challenge</html>", "html"),
    (json.dumps(final()).encode(), "json"),
    (sse({"type": "response.output_text.delta", "delta": "partial"}).encode(), "sse_data"),
    (sse({"type": "response.output_item.added", "item": {"type": "function_call"}}, done()).encode(), "sse_data"),
])
def test_missing_mime_does_not_allow_html_json_partial_or_tools(body, framing):
    p = policy()
    with setup_transport(lambda _: httpx.Response(200, content=body)):
        with pytest.raises(PolicyError):
            decide(p)
    assert p.last_response_id is None
    assert p.last_request_manifest["http"]["declared_mime"] == "missing"
    assert p.last_request_manifest["http"]["parsed_format"] == "unverified"
    assert p.last_request_manifest["body_diagnostic"]["framing"] == framing
    assert "private" not in json.dumps(p.last_request_manifest)


def test_unknown_stream_event_type_is_recorded_and_rejected_without_payload():
    p = policy()
    body = sse({"type": "response.created"}, {"type": "rate_limits.updated", "message": "private secret@example.invalid"}, done())
    with setup_transport(lambda _: httpx.Response(200, content=body.encode())):
        with pytest.raises(PolicyError, match="unsupported stream event: rate_limits.updated"):
            decide(p)
    assert p.last_request_manifest["observed_event_types"] == ["response.created", "rate_limits.updated"]
    assert "private" not in json.dumps(p.last_request_manifest)
    assert p.last_response_id is None


@pytest.mark.parametrize("kind", ["private secret@example.invalid", "X" * 200, None, {"private": "secret"}])
def test_invalid_event_types_are_hashed_not_echoed(kind):
    import hashlib
    p = policy()
    with setup_transport(lambda _: httpx.Response(200, content=sse({"type": kind}, done()).encode())):
        with pytest.raises(PolicyError) as exc:
            decide(p)
    assert p.last_request_manifest["observed_event_types"] == ["invalid"]
    assert p.last_request_manifest["invalid_event_type_sha256"] == [hashlib.sha256(json.dumps(kind, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()]
    assert "private" not in str(exc.value) and "private" not in json.dumps(p.last_request_manifest)


def test_normal_event_types_are_deduplicated_bounded_and_contain_no_payload():
    p = policy()
    events = [{"type": "response.output_text.delta", "delta": "private-text"}] * 3
    events += [{"type": f"response.test_{i}", "message": "private-message"} for i in range(70)]
    events += [done()]
    with setup_transport(lambda _: httpx.Response(200, content=sse(*events).encode())):
        decide(p)
    observed = p.last_request_manifest["observed_event_types"]
    assert len(observed) == 64 and len(set(observed)) == 64
    assert observed[0] == "response.output_text.delta"
    assert p.last_request_manifest["event_type_list_truncated"] is True
    assert "private" not in json.dumps(p.last_request_manifest)



@pytest.mark.parametrize("events", [
    [{"type": "keepalive"}, done()],
    [{"type": "response.created"}, {"type": "keepalive"}, {"type": "response.output_text.delta", "delta": "preview"}, {"type": "keepalive"}, done()],
    [done(), {"type": "keepalive"}],
    [done(), {"type": "keepalive"}, "[DONE]", {"type": "keepalive"}],
])
def test_observed_keepalive_is_ignored_before_during_and_after_terminal(events):
    p = policy()
    with setup_transport(lambda _: httpx.Response(200, content=sse(*events).encode())):
        assert decide(p) == ACTION
    assert p.last_request_manifest["observed_event_types"].count("keepalive") == 1
    assert p.last_response_id == "resp-offline"


@pytest.mark.parametrize("events", [
    [{"type": "keepalive"}],
    [{"type": "keepalive"}, {"type": "response.output_text.delta", "delta": json.dumps(ACTION)}, {"type": "keepalive"}],
    [{"type": "keepalive"}, done(), {"type": "keepalive"}, done()],
    [{"type": "keepalive"}, {"type": "response.function_call_arguments.delta", "delta": "{}"}, done()],
    [{"type": "keepalive"}, {"type": "ping"}, done()],
    [done(), "[DONE]", {"type": "keepalive"}, "[DONE]"],
])
def test_keepalive_does_not_validate_partial_tools_duplicate_terminal_or_unknown(events):
    p = policy()
    with setup_transport(lambda _: httpx.Response(200, content=sse(*events).encode())):
        with pytest.raises(PolicyError):
            decide(p)
    assert p.last_response_id is None
    assert "keepalive" in p.last_request_manifest["observed_event_types"]


def test_keepalive_does_not_extend_overall_deadline():
    p = policy(timeout_seconds=0.03)
    class HeartbeatStream(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(100):
                yield sse({"type": "keepalive"}).encode()
                time.sleep(0.005)
            yield sse(done()).encode()
    try:
        with setup_transport(lambda _: httpx.Response(200, stream=HeartbeatStream())):
            started = time.monotonic()
            with pytest.raises(PolicyError) as exc:
                decide(p)
            assert exc.value.category == "timeout"
            assert time.monotonic() - started < 0.3
        assert "keepalive" in p.last_request_manifest["observed_event_types"]
        assert p.last_response_id is None
    finally:
        p._worker.join(1)
