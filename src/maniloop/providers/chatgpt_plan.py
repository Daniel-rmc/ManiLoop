"""Direct official ChatGPT-plan Responses transport, without a Codex process.

Only the app's dedicated OAuth store supplies tokens. No API-key fallback, custom
endpoint, organization headers or hidden conversation continuation is supported.
"""
from __future__ import annotations

import codecs
import json
import math
import socket
import threading
import time

import httpx

from .policy_request import request_manifest
from .responses import DEFAULT_MODEL, GPTPolicy, PolicyError, _reject_constant, _unique_object

API_BASE = "https://api.openai.com/v1"
MAX_STREAM_BYTES = 4 * 1024 * 1024
_ALLOWED_OPTIONS = {"timeout_seconds", "reasoning_effort", "client_max_response_chars"}
_ALLOWED_REQUEST = {"model", "instructions", "input", "text", "store", "reasoning"}
_UNSUPPORTED = ["max_output_tokens", "temperature", "previous_response_id"]


# Exact documented codes only; free-form error text and unknown codes never enter logs.
# https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery
_PLAN_ERRORS = {
    "subscription_sharing_user_not_eligible": ("plan_not_eligible", "ChatGPT plan usage is unavailable for this account, workspace or policy. Check eligibility; repeated sign-in will not resolve this restriction."),
    "subscription_sharing_usage_limit_exceeded": ("rate_limit", "The ChatGPT plan usage allowance for this app or account has been reached. Pause requests and check ChatGPT Settings > Usage; no reset time is inferred."),
    "subscription_sharing_usage_unavailable": ("service_unavailable", "ChatGPT usage availability could not be checked. Keep the saved authorization and retry later."),
    "subscription_sharing_unsupported_capability": ("unsupported_capability", "This ChatGPT plan route does not support a requested capability. Check the model, input, tools and execution settings before retrying."),
    "subscription_sharing_route_not_supported": ("route_not_supported", "This ChatGPT plan route is not supported. Verify POST /v1/responses and the integration configuration."),
    "subscription_sharing_invalid_user": ("authentication", "The subscriber context could not be validated. Check the selected account and granted permissions; sign in again only after confirmed revocation or a terminal refresh failure."),
    "chatpass_v2_scope_not_authorized": ("authorization", "The signed grant does not authorize this operation. Check the client and granted scopes before retrying."),
    "chatpass_v2_invalid_authorization_context": ("authorization", "The signed permission context is invalid for this operation. Check the client and grant configuration before retrying."),
    "subscription_sharing_user_unavailable": ("service_unavailable", "ChatGPT account or workspace information is temporarily unavailable. Keep the saved authorization and retry later."),
}
for _legacy_quota in ("rate_limit_exceeded", "usage_limit_reached", "insufficient_quota", "quota_exceeded"):
    _PLAN_ERRORS[_legacy_quota] = ("rate_limit", "ChatGPT usage or rate limits prevented this request. Pause new requests and check the account's usage status.")
_SAFE_ERROR_PARAMS = frozenset({"model", "input", "tools", "tool_choice", "service_tier", "stream", "store", "instructions", "text", "reasoning", "reasoning.effort", "max_output_tokens", "temperature", "previous_response_id"})


def _plan_error(code=None, *, status=None, param=None):
    safe_code = code if type(code) is str and code in _PLAN_ERRORS else None
    if safe_code:
        category, message = _PLAN_ERRORS[safe_code]
    elif status == 401:
        category, message = "authentication", "ChatGPT did not accept the signed identity or direct-use permission. Check the selected account and granted scopes."
    elif status == 403:
        category, message = "authorization", "A ChatGPT policy or permission check prevented admission. Check account permissions, serving-region restrictions and integration configuration."
    elif status == 503:
        category, message = "service_unavailable", "ChatGPT direct routing is unavailable or not enabled. Keep the saved authorization and retry later."
    elif status == 429:
        category, message = "rate_limit", "ChatGPT rejected the request because of a usage or rate limit. Pause requests and check usage."
    else:
        category = "http_error" if status is not None else "invalid_response"
        message = "ChatGPT returned a failed or incomplete response."
    if status is not None:
        message += f" (HTTP {status})"
    error = PolicyError(message + " No action was executed.", category=category, http_status=status, code=safe_code)
    error.param = param if type(param) is str and param in _SAFE_ERROR_PARAMS else None
    return error


def _error_fields(value):
    if not isinstance(value, dict):
        return None, None
    error = value.get("error")
    if not isinstance(error, dict):
        error = value
    return error.get("code"), error.get("param")


def _http_error(response):
    # Read a bounded body only to identify allowlisted structured fields. Admission
    # `detail` strings are diagnostic prose and are intentionally not interpreted.
    raw = bytearray()
    try:
        for chunk in response.iter_bytes():
            if len(raw) + len(chunk) > 65536:
                break
            raw.extend(chunk)
        value = json.loads(raw)
    except Exception:
        value = None
    code, param = _error_fields(value)
    return _plan_error(code, status=response.status_code, param=param)


def _token(auth_store, account_id):
    try:
        value = auth_store.access_token(account_id)
    except Exception as exc:
        category = getattr(exc, "category", "authentication")
        if category in {"connection", "timeout"}:
            raise PolicyError("ChatGPT authorization service is temporarily unavailable; check the connection and retry.", category=category) from None
        if category == "configuration":
            raise PolicyError("ChatGPT authorization is not configured for the selected account.", category="configuration") from None
        raise PolicyError("ChatGPT authorization is unavailable; sign in again.", category="authentication") from None
    if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 for c in value):
        raise PolicyError("ChatGPT authorization is unavailable; sign in again.", category="authentication")
    return value


def list_plan_models(auth_store, account_id=None):
    """Only explicitly listed, visible slugs; no guesses from API-key catalogs."""
    token = _token(auth_store, account_id)
    try:
        # trust_env permits standard network proxies, never changes this URL or headers.
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            response = client.get(API_BASE + "/models", headers={"Authorization": "Bearer " + token})
            if response.status_code != 200:
                raise _http_error(response)
            if len(response.content) > MAX_STREAM_BYTES:
                raise PolicyError("ChatGPT model catalog exceeded the size limit.")
            data = response.json()
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            raise PolicyError("ChatGPT returned an unsupported model catalog.")
        result = []
        for item in models:
            if not isinstance(item, dict) or item.get("visibility") != "list":
                continue
            slug = item.get("slug")
            if isinstance(slug, str) and slug.strip() == slug and 0 < len(slug) <= 120 and not any(ord(c) < 32 for c in slug):
                if slug not in result:
                    result.append(slug)
        return result
    except PolicyError:
        raise
    except httpx.TimeoutException:
        raise PolicyError("ChatGPT model catalog request timed out.", category="timeout") from None
    except Exception:
        raise PolicyError("ChatGPT model catalog request failed.", category="connection") from None


class ChatGPTPlanPolicy(GPTPolicy):
    def __init__(self, model=None, *, auth_store, account_id=None, request_options=None):
        self.model = model or DEFAULT_MODEL
        if not isinstance(self.model, str) or not self.model.strip() or len(self.model) > 120 or any(ord(c) < 32 for c in self.model):
            raise PolicyError("Invalid ChatGPT model name.", category="configuration")
        if request_options is not None and type(request_options) is not dict:
            raise PolicyError("Invalid ChatGPT request options.", category="configuration")
        options = dict(request_options or {})
        self._requested_options = dict(options)
        if "max_output_tokens" in options or "server_max_output_tokens" in options:
            raise PolicyError("ChatGPT plan inference does not support a server token cap; use the separate client response-size limit.", category="configuration")
        if set(options) - _ALLOWED_OPTIONS:
            raise PolicyError("Unsupported ChatGPT request option.", category="configuration")
        self.timeout = options.get("timeout_seconds", 120)
        self.reasoning_effort = options.get("reasoning_effort", "low")
        if self.reasoning_effort in (None, "auto"):
            self.reasoning_effort = "low"
        self.client_max_response_chars = options.get("client_max_response_chars", 65536)
        if (type(self.timeout) not in (int, float) or not math.isfinite(self.timeout)
                or not 0 < self.timeout <= 600 or type(self.reasoning_effort) is not str or self.reasoning_effort not in {"low", "medium", "high", "xhigh", "max"}
                or type(self.client_max_response_chars) is not int or not 256 <= self.client_max_response_chars <= 524288):
            raise PolicyError("Invalid ChatGPT request options.", category="configuration")
        self.max_output_tokens = None  # Intentionally omitted by the common encoder.
        self.auth_store, self.account_id = auth_store, account_id
        self.last_usage, self.last_latency, self.last_response_id = {}, 0.0, None
        self.last_request_manifest = None
        self._lock = threading.Lock()
        self._cancelled = threading.Event()
        self._deadline_reached = threading.Event()
        self._deadline_at = None
        self._response = None
        self._client = None
        self._worker = None

    @property
    def transport_busy(self):
        """True until the I/O worker exits, including after caller cancellation.

        Owners must retain the policy and block replacement requests while this
        is true; a returned timeout does not prove the transport has stopped.
        """
        worker = self._worker
        return worker is not None and worker.is_alive()

    @property
    def request_options(self):
        return {"transport": "chatgpt_plan_responses_v1", "timeout_seconds": self.timeout,
                "reasoning_effort": self.reasoning_effort,
                "client_max_response_chars": self.client_max_response_chars,
                "server_max_output_tokens": None, "policy_retries": 0, "transport_retries": 0,
                "stream": True, "store": False, "harness": "maniloop", "codex_process": False}

    def reset(self, seed=0):
        if self.transport_busy:
            raise PolicyError("The previous ChatGPT request is still stopping.", category="connection")
        self._cancelled.clear()

    def _check_interrupted(self):
        if self._cancelled.is_set():
            raise PolicyError("ChatGPT request was cancelled; no action was executed.", category="interrupted")
        if self._deadline_reached.is_set() or (self._deadline_at is not None and time.monotonic() >= self._deadline_at):
            self._deadline_reached.set()
            raise PolicyError("ChatGPT request exceeded its deadline; no action was executed.", category="timeout")

    def _abort_transport(self):
        with self._lock:
            response, client = self._response, self._client
        def close_resources():
            # Shutdown interrupts a blocked socket read when the transport exposes it.
            if response is not None:
                try:
                    stream = response.extensions.get("network_stream")
                    sock = stream.get_extra_info("socket") if stream else None
                    if sock is not None:
                        sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
            for resource in (response, client):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception:
                        pass
        # Transport close can itself contend with a connect; never block the UI or
        # caller's cancellation/deadline on that operation.
        threading.Thread(target=close_resources, daemon=True, name="plan-transport-close").start()

    def cancel(self):
        self._cancelled.set()
        self._abort_transport()

    def close(self):
        self.cancel()

    def _request_text(self, request):
        if self.transport_busy:
            raise PolicyError("The previous ChatGPT request is still stopping; no new request was started.", category="connection")
        self.last_usage, self.last_response_id = {}, None
        self.last_response_model = None
        self._deadline_reached.clear()
        self._check_interrupted()
        if set(request) - _ALLOWED_REQUEST or not isinstance(request.get("input"), list):
            raise PolicyError("Unsupported ChatGPT plan request fields.", category="configuration")
        request = dict(request)
        # Text/vision diagnostics also use an explicit instruction, never an implicit session.
        request.setdefault("instructions", "Answer only the explicit diagnostic request using the supplied observations.")
        request.update(store=False, stream=True)
        self.last_request_manifest = request_manifest(request, transport="chatgpt_plan_responses_v1",
                                                      requested=self._requested_options, unsupported=_UNSUPPORTED)
        self.last_request_manifest["client_controls"] = {"deadline_seconds": self.timeout,
                                                              "max_response_chars": self.client_max_response_chars,
                                                              "policy_retries": 0, "transport_retries": 0}
        started = time.monotonic()
        self._deadline_at = started + self.timeout
        finished = threading.Event()
        result = {}
        self._worker = threading.Thread(target=self._perform_request, args=(request, result, finished),
                                        daemon=True, name="plan-response")
        try:
            self._worker.start()
            # Unlike a socket read timeout this bounds the whole request, including
            # OAuth refresh, connect and headers. Late worker results are discarded.
            while not finished.wait(min(0.05, max(0.001, self._deadline_at - time.monotonic()))):
                self._check_interrupted()
            self._check_interrupted()
            if "error" in result:
                raise result["error"]
            text = self._parse_response(result["response"])
            if len(text) > self.client_max_response_chars:
                raise PolicyError("ChatGPT final response exceeded the client size limit.")
            self._check_interrupted()
            return text
        except PolicyError as exc:
            if isinstance(self.last_request_manifest, dict):
                self.last_request_manifest["error"] = {"category": exc.category, "http_status": exc.http_status,
                                                       "code": exc.code, "param": getattr(exc, "param", None)}
            if self._cancelled.is_set() or self._deadline_reached.is_set():
                self._abort_transport()
            raise
        except Exception:
            raise PolicyError("ChatGPT returned an invalid response; no action was executed.") from None
        finally:
            self._deadline_at = None
            self.last_latency = time.monotonic() - started

    def _perform_request(self, request, result, finished):
        try:
            self._check_interrupted()
            token = _token(self.auth_store, self.account_id)
            self._check_interrupted()
            with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                with self._lock:
                    self._client = client
                self._check_interrupted()
                with client.stream("POST", API_BASE + "/responses", json=request,
                                   headers={"Authorization": "Bearer " + token, "Accept": "text/event-stream"}) as response:
                    with self._lock:
                        self._response = response
                    self._check_interrupted()
                    if response.status_code != 200:
                        raise _http_error(response)
                    if "text/event-stream" not in response.headers.get("content-type", "").lower():
                        raise PolicyError("ChatGPT did not return an event stream.")
                    result["response"] = self._read_stream(response)
        except PolicyError as exc:
            result["error"] = exc
        except httpx.TimeoutException:
            result["error"] = PolicyError("ChatGPT request timed out; no action was executed.", category="timeout")
        except Exception:
            result["error"] = PolicyError("ChatGPT response stream failed; no action was executed.", category="connection")
        finally:
            with self._lock:
                self._response = self._client = None
            finished.set()

    def _read_stream(self, response):
        completed = None
        data_lines = []
        saw_done = False

        def dispatch():
            nonlocal completed, saw_done
            if not data_lines:
                return
            payload = "\n".join(data_lines)
            data_lines.clear()
            if payload == "[DONE]":
                if completed is None or saw_done:
                    raise PolicyError("ChatGPT stream ended without one completed response.")
                saw_done = True
                return
            if completed is not None or saw_done:
                raise PolicyError("ChatGPT returned events after its terminal response.")
            try:
                event = json.loads(payload, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
            except (ValueError, TypeError):
                raise PolicyError("ChatGPT returned invalid stream data.") from None
            if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                raise PolicyError("ChatGPT returned invalid stream data.")
            kind = event["type"]
            if kind in {"response.output_item.added", "response.output_item.done"}:
                item = event.get("item")
                if not isinstance(item, dict) or item.get("type") not in {"message", "reasoning"}:
                    raise PolicyError("ChatGPT returned a tool or unsupported output item.")
            if kind.startswith(("response.function_call", "response.mcp", "response.web_search", "response.file_search", "response.code_interpreter")):
                raise PolicyError("ChatGPT returned an unsupported tool event.")
            if kind in {"error", "response.failed", "response.incomplete"}:
                source = event.get("response") if isinstance(event.get("response"), dict) else event
                code, param = _error_fields(source)
                raise _plan_error(code, param=param)
            if kind == "response.completed":
                completed = event.get("response")
                if not isinstance(completed, dict):
                    raise PolicyError("ChatGPT returned an invalid terminal response.")
            elif not kind.startswith("response."):
                raise PolicyError("ChatGPT returned an unsupported stream event.")

        for line in self._stream_lines(response):
            self._check_interrupted()
            if line == "":
                dispatch()
            elif line.startswith("data:"):
                data_lines.append(line[5:].removeprefix(" "))
            elif line.startswith((":", "event:", "id:", "retry:")):
                continue
            else:
                raise PolicyError("ChatGPT returned invalid SSE framing.")
        dispatch()
        self._check_interrupted()
        if completed is None:
            raise PolicyError("ChatGPT stream disconnected before response.completed; no action was executed.")
        return completed

    def _stream_lines(self, response):
        # Bound raw bytes before buffering lines, including streams without newlines.
        decoder = codecs.getincrementaldecoder("utf-8")("strict")
        buffered, size = "", 0
        for chunk in response.iter_bytes():
            self._check_interrupted()
            size += len(chunk)
            if size > MAX_STREAM_BYTES:
                raise PolicyError("ChatGPT response stream exceeded the size limit.")
            buffered += decoder.decode(chunk)
            while "\n" in buffered:
                line, buffered = buffered.split("\n", 1)
                yield line.removesuffix("\r")
        buffered += decoder.decode(b"", final=True)
        if buffered:
            yield buffered.removesuffix("\r")
