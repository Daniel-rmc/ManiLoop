"""Offline contract tests; no API calls or credentials are needed."""

import base64
import copy
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from openai import APITimeoutError, AuthenticationError, OpenAI as SDKOpenAI

from arx5_demo.policy import ACTION_SCHEMA, DEFAULT_MODEL, GPTPolicy, PolicyError


def action(**changes):
    result = {
        "observation_id": "observation-17", "kind": "move",
        "delta_position": [0.01, 0, 0], "delta_rotation": [0, 0, 0],
        "gripper_opening": 0, "pixel": [0, 0], "camera": "",
        "explanation": "根据当前图像向目标移动一小步。",
    }
    result.update(changes)
    return result


def response(payload=None, **changes):
    message = SimpleNamespace(type="message", role="assistant", status="completed", content=[
        SimpleNamespace(type="output_text", text=json.dumps(payload if payload is not None else action()))
    ])
    result = dict(id="resp_offline_test", status="completed", error=None, incomplete_details=None,
                  output=[message], usage=SimpleNamespace(input_tokens=100, output_tokens=30, total_tokens=130))
    result.update(changes)
    return SimpleNamespace(**result)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test-key"}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.factory_patch = patch("arx5_demo.policy.OpenAI")
        self.factory = self.factory_patch.start()
        self.addCleanup(self.factory_patch.stop)
        self.client = MagicMock()
        self.client.responses.create.return_value = response()
        self.factory.return_value = self.client
        self.policy = GPTPolicy()
        self.observation = {"observation_id": "observation-17", "frame_id": "base", "tcp_position": [0.3, 0.0, 0.2]}
        self.images = {"external": b"fake-jpeg-external", "wrist": b"fake-jpeg-wrist"}

    def decide(self, **kwargs):
        inputs = dict(task="把红色方块放到绿色区域", observation=self.observation,
                      images=self.images, history=[], geometry_results=[])
        inputs.update(kwargs)
        return self.policy.decide(**inputs)

    def test_multimodal_structured_request_and_metadata(self):
        self.assertEqual(self.decide(), action())
        self.factory.assert_called_once_with(api_key="offline-test-key", timeout=45.0, max_retries=0)
        request = self.client.responses.create.call_args.kwargs
        self.assertEqual(request["model"], DEFAULT_MODEL)
        self.assertFalse(request["store"])
        self.assertEqual(request["text"]["format"], {"type": "json_schema", "name": "robot_action", "strict": True, "schema": ACTION_SCHEMA})
        content = request["input"][0]["content"]
        self.assertEqual(json.loads(content[0]["text"])["observation"], self.observation)
        image_parts = [c for c in content if c["type"] == "input_image"]
        self.assertEqual(len(image_parts), 2)
        for part, original in zip(image_parts, self.images.values()):
            self.assertEqual(part["detail"], "high")
            self.assertEqual(base64.b64decode(part["image_url"].split(",", 1)[1]), original)
        self.assertEqual(self.policy.last_usage, {"input_tokens": 100, "output_tokens": 30, "total_tokens": 130})
        self.assertEqual(self.policy.last_response_id, "resp_offline_test")
        self.assertGreaterEqual(self.policy.last_latency, 0)

    def test_environment_override_and_missing_key(self):
        with patch.dict(os.environ, {"OPENAI_MODEL": "gpt-4o", "OPENAI_TIMEOUT_SECONDS": "12", "OPENAI_MAX_OUTPUT_TOKENS": "3000"}):
            policy = GPTPolicy()
        self.assertEqual(policy.model, "gpt-4o")
        self.assertEqual(policy.timeout, 12)
        self.assertIsNone(policy.reasoning_effort)
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(PolicyError, "not configured"):
            GPTPolicy()

    def test_explicit_endpoint_and_key_are_passed_together(self):
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://unrelated.example/v1"}):
            GPTPolicy(model="provider-model", api_key="offline-profile-key", base_url="https://selected.example/custom/v1")
        self.factory.assert_called_with(api_key="offline-profile-key", base_url="https://selected.example/custom/v1",
                                        timeout=45.0, max_retries=0)

    def test_client_initialization_error_does_not_echo_secret(self):
        self.factory.side_effect = ValueError("offline-profile-key from broken provider config")
        with self.assertRaises(PolicyError) as error:
            GPTPolicy(api_key="offline-profile-key", base_url="https://selected.example/v1")
        self.assertNotIn("offline-profile-key", str(error.exception))
        self.assertTrue(error.exception.__suppress_context__)

    def test_refusal_never_becomes_an_action(self):
        denied = SimpleNamespace(type="refusal", refusal="This is a refusal")
        self.client.responses.create.return_value = response(output=[SimpleNamespace(type="message", role="assistant", status="completed", content=[denied])])
        with self.assertRaisesRegex(PolicyError, "declined"):
            self.decide()

    def test_timeout_has_no_retry_and_sanitizes_exception(self):
        self.client.responses.create.side_effect = APITimeoutError(request=SimpleNamespace(method="POST", url="https://api.openai.com/v1/responses"))
        with self.assertRaisesRegex(PolicyError, "timed out"):
            self.decide()
        self.assertEqual(self.client.responses.create.call_count, 1)
        self.assertEqual(self.policy.last_usage, {})
        self.assertIsNone(self.policy.last_response_id)

    def test_authentication_error_does_not_echo_secret(self):
        req = SimpleNamespace(method="POST", url="https://api.openai.com/v1/responses")
        self.client.responses.create.side_effect = AuthenticationError("bad offline-test-key", response=SimpleNamespace(status_code=401, request=req, headers={}), body={"key": "offline-test-key"})
        with self.assertRaises(PolicyError) as error:
            self.decide()
        self.assertNotIn("offline-test-key", str(error.exception))
        self.assertTrue(error.exception.__suppress_context__)

    def test_nonfinite_values_and_bool_are_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf"), True, "0.01"):
            with self.subTest(value=value):
                self.client.responses.create.return_value = response(action(delta_position=[value, 0, 0]))
                with self.assertRaises(PolicyError):
                    self.decide()

    def test_wrong_schema_and_observation_id(self):
        bad_actions = [action(observation_id="stale"), action(kind="execute_python"), action(extra="field"),
                       action(delta_position=[0, 0]), action(gripper_opening=1.5), action(pixel=[False, 0]),
                       action(kind="wait"), action(camera="external")]
        missing = action()
        missing.pop("pixel")
        bad_actions.append(missing)
        for payload in bad_actions:
            with self.subTest(payload=payload):
                self.client.responses.create.return_value = response(payload)
                with self.assertRaises(PolicyError):
                    self.decide()

    def test_invalid_or_duplicate_json(self):
        for text in ("```json\n{}\n```", '{"kind":"wait","kind":"done"}', "[1,2]", ""):
            self.client.responses.create.return_value = response()
            self.client.responses.create.return_value.output[0].content[0].text = text
            with self.subTest(text=text), self.assertRaises(PolicyError):
                self.decide()

    def test_incomplete_missing_or_invalid_response(self):
        for changes in ({"status": "incomplete"}, {"incomplete_details": {"reason": "max_output_tokens"}},
                        {"error": {"code": "server_error"}}, {"output": []}, {"id": None}, {"id": ""},
                        {"id": "   "}, {"id": 17}, {"id": "x" * 257}):
            self.client.responses.create.return_value = response(**changes)
            with self.subTest(changes=changes), self.assertRaises(PolicyError):
                self.decide()

    def test_compatible_provider_response_id_is_opaque(self):
        self.client.responses.create.return_value = response(id="provider-response-17")
        self.assertEqual(self.decide(), action())
        self.assertEqual(self.policy.last_response_id, "provider-response-17")

    def test_completed_gateway_empty_error_placeholders(self):
        for error, detail in (({}, {}), ({'code':'','message':''}, {'reason':''}),
                              (SimpleNamespace(code='',message=''), SimpleNamespace(reason=''))):
            with self.subTest(error=error):
                self.client.responses.create.return_value = response(error=error, incomplete_details=detail)
                self.assertEqual(self.decide(), action())

    def test_gateway_placeholders_do_not_hide_errors_or_partial_outputs(self):
        for changes in ({'error':{'code':'','message':'failed'}},
                        {'error':{'code':'','message':'','unexpected':'failure'}},
                        {'incomplete_details':{'reason':'content_filter'}},
                        {'incomplete_details':{'reason':False}},
                        {'status':'incomplete','error':{},'incomplete_details':{}}):
            with self.subTest(changes=changes), self.assertRaises(PolicyError):
                self.client.responses.create.return_value = response(**changes)
                self.decide()
        self.client.responses.create.return_value = response(error={}, incomplete_details={})
        self.client.responses.create.return_value.output[0].status = 'in_progress'
        with self.assertRaises(PolicyError):
            self.decide()

    def test_output_limit_error_is_actionable_and_does_not_echo_provider_text(self):
        self.client.responses.create.return_value = response(status='incomplete', incomplete_details={'reason':'max_output_tokens'}, error={'message':'offline-test-key'})
        with self.assertRaisesRegex(PolicyError, 'OPENAI_MAX_OUTPUT_TOKENS') as error:
            self.decide()
        self.assertNotIn('offline-test-key',str(error.exception))

    def test_depth_query_is_sensor_only(self):
        query = action(kind="query_depth", delta_position=[0, 0, 0], camera="external", pixel=[123, 88])
        self.client.responses.create.return_value = response(query)
        self.assertEqual(self.decide(), query)
        self.client.responses.create.return_value = response(dict(query, camera="wrist"))
        with self.assertRaisesRegex(PolicyError, "external"):
            self.decide()

    def test_private_observation_fields_never_reach_api(self):
        for private in ("object_pose", "contacts", "evaluation", "qpos", "ground_truth"):
            with self.subTest(private=private), self.assertRaisesRegex(PolicyError, "public sensor"):
                self.decide(observation=dict(self.observation, **{private: [1, 2, 3]}))
        self.client.responses.create.assert_not_called()

    def test_invalid_sensor_data_never_reaches_api(self):
        with self.assertRaises(PolicyError):
            self.decide(observation=dict(self.observation, tcp_position=[float("nan"), 0, 0]))
        with self.assertRaises(PolicyError):
            self.decide(images={})
        self.client.responses.create.assert_not_called()

    def test_recent_history_is_bounded_without_mutating_input(self):
        history = [{"step": i} for i in range(20)]
        original = copy.deepcopy(history)
        geometry = [{"pixel": [i, i]} for i in range(10)]
        self.decide(history=history, geometry_results=geometry)
        serialized = json.loads(self.client.responses.create.call_args.kwargs["input"][0]["content"][0]["text"])
        self.assertEqual(serialized["history"], history[-12:])
        self.assertEqual(serialized["geometry_results"], geometry[-8:])
        self.assertEqual(history, original)

    def test_installed_sdk_serializes_and_parses_without_network(self):
        # OpenAI SDK 3.x uses httpx2; 1.x/2.x use httpx.
        try:
            import httpx2 as transport_http
        except ImportError:
            import httpx as transport_http
        wire_requests = []

        def serve(request):
            wire_requests.append(json.loads(request.content))
            return transport_http.Response(200, json={
                "id": "resp_sdk_offline", "object": "response", "created_at": 0,
                "model": DEFAULT_MODEL, "status": "completed", "error": None,
                "incomplete_details": None, "output": [{
                    "id": "msg_sdk_offline", "type": "message", "role": "assistant",
                    "status": "completed", "content": [{
                        "type": "output_text", "text": json.dumps(action()), "annotations": [],
                    }],
                }], "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            })

        client = SDKOpenAI(api_key="offline-sdk-test", max_retries=0,
                           http_client=transport_http.Client(transport=transport_http.MockTransport(serve)))
        self.addCleanup(client.close)
        self.policy.client = client
        self.assertEqual(self.decide(), action())
        self.assertEqual(len(wire_requests), 1)
        self.assertFalse(wire_requests[0]["store"])
        self.assertTrue(wire_requests[0]["text"]["format"]["strict"])
        self.assertEqual(self.policy.last_response_id, "resp_sdk_offline")

    def test_sdk_added_defaults_do_not_turn_empty_gateway_error_into_failure(self):
        try:
            import httpx2 as transport_http
        except ImportError:
            import httpx as transport_http
        gateway_error = {"code": "", "message": ""}
        def serve(request):
            return transport_http.Response(200, json={
                "id": "response-gateway", "object": "response", "created_at": 0,
                "model": "provider-model", "status": "completed", "error": dict(gateway_error),
                "incomplete_details": {"reason": ""}, "output": [{
                    "id": "message-gateway", "type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": json.dumps(action()), "annotations": []}],
                }], "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            })
        client = SDKOpenAI(api_key="offline-sdk-test", max_retries=0,
            http_client=transport_http.Client(transport=transport_http.MockTransport(serve)))
        self.addCleanup(client.close)
        self.policy.client = client
        self.assertEqual(self.decide(), action())
        # Only defaults absent from the wire are ignored. Supplied extra fields,
        # nonempty errors and unfinished output must remain rejected.
        for changes in ({"message": "failed"}, {"misalignment": {"reason": "blocked"}}, {"unknown": None}):
            gateway_error.clear()
            gateway_error.update({"code": "", "message": "", **changes})
            with self.subTest(changes=changes), self.assertRaises(PolicyError):
                self.decide()

    def test_installed_sdk_uses_selected_endpoint_without_network(self):
        try:
            import httpx2 as transport_http
        except ImportError:
            import httpx as transport_http
        wire_requests = []

        def serve(request):
            wire_requests.append(request)
            return transport_http.Response(200, json={
                "id": "opaque-provider-id", "object": "response", "created_at": 0,
                "model": "provider-model", "status": "completed", "error": None,
                "incomplete_details": None, "output": [{
                    "id": "message-provider-id", "type": "message", "role": "assistant",
                    "status": "completed", "content": [{
                        "type": "output_text", "text": json.dumps(action()), "annotations": [],
                    }],
                }], "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            })

        def make_client(**kwargs):
            client = SDKOpenAI(**kwargs, http_client=transport_http.Client(transport=transport_http.MockTransport(serve)))
            self.addCleanup(client.close)
            return client

        self.factory.side_effect = make_client
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://unrelated.example/v1"}):
            self.policy = GPTPolicy(model="provider-model", api_key="offline-profile-key",
                                    base_url="https://selected.example/proxy/v1")
            self.assertEqual(self.decide(), action())
        self.assertEqual(len(wire_requests), 1)
        self.assertEqual(wire_requests[0].url.host, "selected.example")
        self.assertEqual(wire_requests[0].url.path, "/proxy/v1/responses")
        self.assertEqual(wire_requests[0].headers["authorization"], "Bearer offline-profile-key")
        self.assertEqual(self.policy.last_response_id, "opaque-provider-id")


    def test_explicit_request_settings_and_timeout_classification(self):
        self.policy = GPTPolicy(request_options={"timeout_seconds": 120, "reasoning_effort": "low"})
        assert self.policy.request_options == {"timeout_seconds": 120.0, "reasoning_effort": "low", "max_output_tokens": 4096, "max_retries": 0}
        self.client.responses.create.side_effect = APITimeoutError(request=SimpleNamespace(method="POST", url="https://example.test"))
        with self.assertRaises(PolicyError) as caught:
            self.decide()
        assert caught.exception.category == "timeout"
        assert "120" in str(caught.exception)
        assert self.policy.last_latency >= 0 and self.policy.last_usage == {}
        assert self.client.responses.create.call_count == 1

    def test_three_diagnostic_stages_and_payload_boundaries(self):
        text_response = response()
        text_response.output[0].content[0].text = "READY"
        self.client.responses.create.return_value = text_response
        for stage, image_count in (("text", 0), ("vision", 1)):
            result = self.policy.diagnose(stage, "unused task", self.observation, self.images)
            assert result["output"] == "READY" and result["executed"] is False
            request = self.client.responses.create.call_args.kwargs
            assert sum(p["type"] == "input_image" for p in request["input"][0]["content"]) == image_count
            assert "text" not in request  # schema support is tested separately
        self.client.responses.create.return_value = response()
        result = self.policy.diagnose("action", "unused task", self.observation, self.images)
        assert result["action"] == action() and result["executed"] is False
        assert self.client.responses.create.call_args.kwargs["text"]["format"]["strict"]
        assert self.client.responses.create.call_count == 3

    def test_bad_request_options_fail_before_client_creation(self):
        for options in ({"timeout_seconds": 0}, {"timeout_seconds": 601},
                        {"timeout_seconds": True}, {"timeout_seconds": None},
                        {"unexpected": "value"}, {"reasoning_effort": "none"}):
            with self.subTest(options=options), self.assertRaises(PolicyError):
                GPTPolicy(request_options=options)
        assert self.factory.call_count == 1


if __name__ == "__main__":
    unittest.main()
