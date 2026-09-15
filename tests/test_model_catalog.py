"""Model discovery contracts using fake credentials and offline transports."""

import os
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI as SDKOpenAI,
    RateLimitError,
)

from arx5_demo.model_catalog import ModelCatalogError, fetch_models


class ModelCatalogTests(unittest.TestCase):
    def setUp(self):
        factory_patch = patch("arx5_demo.model_catalog.OpenAI")
        self.factory = factory_patch.start()
        self.addCleanup(factory_patch.stop)
        self.client = MagicMock()
        self.factory.return_value = self.client

    def fetch(self):
        return fetch_models("offline-catalog-key", "https://selected.example/proxy/v1")

    def test_models_are_sorted_unique_filtered_and_not_classified(self):
        self.client.models.list.return_value = SimpleNamespace(data=[
            SimpleNamespace(id="gpt-audio"), {"id": "custom-text-only"}, {"id": "gpt-audio"},
            {"id": ""}, {"id": "   "}, {"id": None}, {"id": 23}, {"id": "x" * 121}, {},
        ])
        self.assertEqual(self.fetch(), ["custom-text-only", "gpt-audio"])
        self.factory.assert_called_once_with(api_key="offline-catalog-key", base_url="https://selected.example/proxy/v1",
                                             timeout=10, max_retries=0)
        self.client.models.list.assert_called_once_with()
        self.client.close.assert_called_once_with()

    def test_reads_only_received_page_and_caps_results(self):
        page = MagicMock()
        page.data = [{"id": f"model-{i:04d}"} for i in range(1100)]
        page.__iter__.side_effect = AssertionError("must not auto-paginate")
        self.client.models.list.return_value = page
        models = self.fetch()
        self.assertEqual(len(models), 1000)
        self.assertEqual(models, [f"model-{i:04d}" for i in range(1000)])
        page.__iter__.assert_not_called()
        page.get_next_page.assert_not_called()
        self.client.models.list.assert_called_once()
        self.client.close.assert_called_once()

    def test_missing_credentials_or_endpoint_do_not_use_environment(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "unrelated-test-key", "OPENAI_BASE_URL": "https://unrelated.example/v1"}):
            for key, url in (("", "https://selected.example/v1"), ("test-key", ""), (None, None)):
                with self.subTest(key=key, url=url), self.assertRaises(ModelCatalogError):
                    fetch_models(key, url)
        self.factory.assert_not_called()

    def test_bad_response_is_sanitized_and_client_closed(self):
        self.client.models.list.return_value = SimpleNamespace(data="offline-catalog-key private-body")
        with self.assertRaises(ModelCatalogError) as error:
            self.fetch()
        self.assertNotIn("offline-catalog-key", str(error.exception))
        self.assertNotIn("private-body", str(error.exception))
        self.client.close.assert_called_once()

    def test_all_request_failures_are_sanitized_and_client_closed(self):
        request = SimpleNamespace(method="GET", url="https://selected.example/proxy/v1/models")
        secret = "offline-catalog-key private-provider-body"
        errors = [
            AuthenticationError(secret, response=SimpleNamespace(status_code=401, request=request, headers={}), body={"message": secret}),
            RateLimitError(secret, response=SimpleNamespace(status_code=429, request=request, headers={}), body={"message": secret}),
            APIStatusError(secret, response=SimpleNamespace(status_code=404, request=request, headers={}), body={"message": secret}),
            APIConnectionError(message=secret, request=request),
            APITimeoutError(request=request),
            RuntimeError(secret),
        ]
        for failure in errors:
            with self.subTest(type=type(failure)):
                self.client.reset_mock()
                self.client.models.list.side_effect = failure
                with self.assertRaises(ModelCatalogError) as error:
                    self.fetch()
                self.assertNotIn("offline-catalog-key", str(error.exception))
                self.assertNotIn("private-provider-body", str(error.exception))
                self.assertTrue(error.exception.__suppress_context__)
                self.client.models.list.assert_called_once()
                self.client.close.assert_called_once()

    def test_initialization_error_is_sanitized(self):
        self.factory.side_effect = ValueError("offline-catalog-key private-provider-body")
        with self.assertRaises(ModelCatalogError) as error:
            self.fetch()
        self.assertNotIn("offline-catalog-key", str(error.exception))
        self.assertTrue(error.exception.__suppress_context__)

    def test_close_error_cannot_replace_sanitized_failure(self):
        self.client.models.list.side_effect = RuntimeError("offline-catalog-key")
        self.client.close.side_effect = RuntimeError("offline-catalog-key")
        with self.assertRaises(ModelCatalogError) as error:
            self.fetch()
        self.assertNotIn("offline-catalog-key", str(error.exception))
        self.client.close.assert_called_once()

    def test_sdk_request_targets_selected_endpoint_and_does_not_paginate(self):
        try:
            import httpx2 as transport_http
        except ImportError:
            import httpx as transport_http
        requests = []
        clients = []

        def serve(request):
            requests.append(request)
            return transport_http.Response(200, json={
                "object": "list", "data": [{"id": "provider-model", "object": "model", "created": 0, "owned_by": "provider"}],
                "has_more": True, "next_page": "https://unrelated.example/v1/models?page=2",
            })

        def make_client(**kwargs):
            client = SDKOpenAI(**kwargs, http_client=transport_http.Client(transport=transport_http.MockTransport(serve)))
            clients.append(client)
            return client

        self.factory.side_effect = make_client
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://unrelated.example/v1"}):
            self.assertEqual(self.fetch(), ["provider-model"])
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.host, "selected.example")
        self.assertEqual(requests[0].url.path, "/proxy/v1/models")
        self.assertEqual(requests[0].headers["authorization"], "Bearer offline-catalog-key")
        self.assertTrue(clients[0].is_closed())

    def test_sdk_unsupported_endpoint_does_not_leak_provider_body(self):
        try:
            import httpx2 as transport_http
        except ImportError:
            import httpx as transport_http
        requests = []
        clients = []

        def serve(request):
            requests.append(request)
            return transport_http.Response(404, json={"error": {"message": "offline-catalog-key private-provider-body"}})

        def make_client(**kwargs):
            client = SDKOpenAI(**kwargs, http_client=transport_http.Client(transport=transport_http.MockTransport(serve)))
            clients.append(client)
            return client

        self.factory.side_effect = make_client
        with self.assertRaises(ModelCatalogError) as error:
            self.fetch()
        self.assertNotIn("offline-catalog-key", str(error.exception))
        self.assertNotIn("private-provider-body", str(error.exception))
        self.assertTrue(error.exception.__suppress_context__)
        self.assertEqual(len(requests), 1)
        self.assertTrue(clients[0].is_closed())


if __name__ == "__main__":
    unittest.main()
