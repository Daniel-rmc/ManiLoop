"""Offline regression for RGB-only Responses schemas; never uses real credentials."""
import copy
import json
from unittest.mock import MagicMock

import pytest
from maniloop.providers import responses


def payload(**changes):
    result = dict(observation_id="snapshot-1", kind="move", delta_position=[0, 0, .005],
                  delta_rotation=[0, 0, 0], gripper_opening=0,
                  camera="", pixel=[0, 0], explanation="Small visible motion.")
    return dict(result, **changes)


@pytest.fixture
def policy(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(responses, "OpenAI", lambda **_: client)
    value = responses.GPTPolicy(api_key="offline-test-key")
    def provide(action):
        client.responses.create.return_value = dict(
            id="offline-response", status="completed", error=None, incomplete_details=None,
            output=[dict(type="message", role="assistant", status="completed",
                         content=[dict(type="output_text", text=json.dumps(action))])])
    provide(payload())
    return value, client, provide


def decide(policy, depth=False, cameras=None):
    observation = dict(observation_id="snapshot-1", frame_id="world",
                       tcp_position=[0, 0, 1], geometry_queries={"depth_available": depth})
    return policy.decide("Lift the cube", observation,
                         cameras if cameras is not None else {"external": b"fake-rgb", "wrist": b"fake-rgb"}, [], [])


def test_rgb_schema_constrains_unused_camera_fields(policy):
    value, client, _ = policy
    assert decide(value) == payload()
    schema = client.responses.create.call_args.kwargs["text"]["format"]["schema"]
    assert "query_depth" not in schema["properties"]["kind"]["enum"]
    assert schema["properties"]["camera"]["enum"] == [""]
    assert schema["properties"]["pixel"]["items"]["enum"] == [0]
    assert schema["properties"]["pixel"]["minItems"] == 2
    assert schema["properties"]["pixel"]["maxItems"] == 2


@pytest.mark.parametrize("changes", [dict(camera="external"), dict(pixel=[128, 128])])
def test_bad_gateway_output_is_still_rejected_without_retry(policy, changes):
    value, client, provide = policy
    provide(payload(**changes))
    with pytest.raises(responses.PolicyError, match="camera/pixel"):
        decide(value)
    assert client.responses.create.call_count == 1


def test_rgb_depth_query_rejected_even_when_provider_ignores_schema(policy):
    value, client, provide = policy
    provide(payload(kind="query_depth", delta_position=[0, 0, 0], camera="external", pixel=[12, 8]))
    with pytest.raises(responses.PolicyError, match="depth|深度"):
        decide(value)
    assert client.responses.create.call_count == 1


def test_depth_capable_request_preserves_query_and_does_not_mutate_global_schema(policy):
    value, client, provide = policy
    original = copy.deepcopy(responses.ACTION_SCHEMA)
    decide(value)
    query = payload(kind="query_depth", delta_position=[0, 0, 0], camera="external", pixel=[12, 8])
    provide(query)
    assert decide(value, depth=True) == query
    schema = client.responses.create.call_args.kwargs["text"]["format"]["schema"]
    assert "query_depth" in schema["properties"]["kind"]["enum"]
    assert "enum" not in schema["properties"]["pixel"]["items"]
    assert responses.ACTION_SCHEMA == original


@pytest.mark.parametrize("depth", [False, None, "true", 1])
def test_only_explicit_depth_capability_enables_query(policy, depth):
    value, client, _ = policy
    decide(value, depth=depth)
    schema = client.responses.create.call_args.kwargs["text"]["format"]["schema"]
    assert "query_depth" not in schema["properties"]["kind"]["enum"]


def test_previous_or_wrist_image_does_not_enable_depth_query(policy):
    value, client, _ = policy
    decide(value, depth=True, cameras={"previous/external": b"fake", "wrist": b"fake"})
    schema = client.responses.create.call_args.kwargs["text"]["format"]["schema"]
    assert "query_depth" not in schema["properties"]["kind"]["enum"]


def test_action_diagnostic_returns_wait_without_running_physics(policy):
    value, client, provide = policy
    provide(payload(kind="wait", delta_position=[0, 0, 0]))
    result = value.diagnose("action", "unused", dict(observation_id="snapshot-1",
                            geometry_queries={"depth_available": False}), {"external": b"fake-rgb"})
    assert result["executed"] is False and result["action"]["kind"] == "wait"
    assert client.responses.create.call_count == 1
    schema = client.responses.create.call_args.kwargs["text"]["format"]["schema"]
    assert schema["properties"]["camera"]["enum"] == [""]


def test_imported_toml_plus_key_and_installed_sdk_wire_schema(monkeypatch):
    from maniloop.providers.credentials import load_toml_config
    from openai import OpenAI
    try:
        import httpx2 as http
    except ImportError:
        import httpx as http
    seen = []
    toml = '''model = "gpt-6-astra"
model_provider = "fixture"
[model_providers.fixture]
base_url = "https://selected.example/v1"
wire_api = "responses"
'''
    config = load_toml_config(toml, api_key="offline-imported-key", name="fixture.toml")
    def serve(request):
        assert str(request.url) == "https://selected.example/v1/responses"
        assert request.headers["authorization"] == "Bearer offline-imported-key"
        seen.append(json.loads(request.content))
        return http.Response(200, json=dict(id="offline-wire-response", object="response",
            created_at=0, model=config.model, status="completed", error=None, incomplete_details=None,
            output=[dict(id="message-1", type="message", role="assistant", status="completed",
                         content=[dict(type="output_text", text=json.dumps(payload()), annotations=[])])]))
    client = OpenAI(api_key=config.api_key, base_url=config.base_url, max_retries=0,
                    http_client=http.Client(transport=http.MockTransport(serve)))
    monkeypatch.setattr(responses, "OpenAI", lambda **_: client)
    policy = responses.GPTPolicy(model=config.model, api_key=config.api_key, base_url=config.base_url)
    try:
        assert decide(policy) == payload()
        assert len(seen) == 1
        schema = seen[0]["text"]["format"]["schema"]
        assert seen[0]["text"]["format"]["strict"] is True
        assert schema["properties"]["camera"]["enum"] == [""]
        assert schema["properties"]["pixel"]["items"]["enum"] == [0]
        assert "offline-imported-key" not in json.dumps(seen)
    finally:
        policy.close()
