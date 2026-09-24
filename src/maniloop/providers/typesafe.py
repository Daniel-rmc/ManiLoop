"""TypeSafe's native Choice API, without redirects, retries or credential reuse.

Contract checked against https://docs.typesafe.ai/api on 2026-09-21.
Only sanitized protocol metadata leaves this module; never provider error bodies.
"""
import http.client
import json
import math
import os
import re
import time
from .responses import PolicyError

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-1.13.0"
MAX_RESPONSE_BYTES = 512 * 1024


def finite(value, lower, upper):
    return type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def validate_choice(response, candidates, requested_model):
    try:
        model = response["model"]
        answer = response["answers"]["action"]
        probabilities = answer["probabilities"]
        if not isinstance(model, str) or not re.fullmatch(r"jev-[a-zA-Z0-9.-]{1,64}", model):
            raise ValueError()
        if requested_model not in {"jev-latest", "jev-preview"} and model != requested_model:
            raise ValueError()
        if set(response["answers"]) != {"action"} or answer["type"] != "choice":
            raise ValueError()
        if set(probabilities) != set(candidates) or not all(finite(p, 0, 1) for p in probabilities.values()):
            raise ValueError()
        if not math.isclose(sum(probabilities.values()), 1, abs_tol=1e-3):
            raise ValueError()
        choice = answer["choice"]
        if choice not in candidates or probabilities[choice] + 1e-6 < max(probabilities.values()):
            raise ValueError()
        if not finite(answer["confidence"], 0, 1):
            raise ValueError()
        usage = {key: response["usage"][key] for key in ("input_tokens", "output_tokens")}
        if any(type(v) is not int or v < 0 for v in usage.values()):
            raise ValueError()
        return {"model": model, "choice": choice, "probabilities": dict(probabilities),
                "confidence": answer["confidence"], "usage": usage}
    except (KeyError, TypeError, ValueError, AttributeError):
        raise PolicyError("Jev 返回的候选/概率/模型版本不符合协议；未执行动作。") from None


def normalize_api_key(value):
    """Validate without a request; never include the supplied value in an error."""
    if not isinstance(value, str) or not value.strip():
        raise PolicyError("尚未配置 TypeSafe API Key；请填写 Jev 专用密钥或设置 TYPESAFE_API_KEY。", category="configuration")
    key = value.strip()
    if len(key) > 1000 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise PolicyError("TypeSafe API Key 格式无效。", category="configuration")
    return key


class TypeSafeClient:
    def __init__(self, api_key=None, model=DEFAULT_MODEL, timeout=30):
        key = api_key if api_key is not None else os.environ.get("TYPESAFE_API_KEY", "")
        key = normalize_api_key(key)
        if not isinstance(model, str) or not re.fullmatch(r"jev-[a-zA-Z0-9.-]{1,64}", model):
            raise PolicyError("Jev 模型名称无效。", category="configuration")
        if not finite(timeout, 1, 120):
            raise PolicyError("Jev 请求超时须为 1–120 秒。", category="configuration")
        self._key, self.model, self.timeout = key.strip(), model, float(timeout)
        self.last_latency, self.last_usage = 0.0, {}

    def _post(self, payload):
        connection = http.client.HTTPSConnection("api.typesafe.ai", timeout=self.timeout)
        try:
            connection.request("POST", "/v1/systemone", body=payload,
                headers={"Authorization": "Bearer " + self._key, "Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status != 200:
                messages = {401: "TypeSafe 认证失败", 403: "TypeSafe 无访问权限", 429: "TypeSafe 额度或限流", 529: "TypeSafe 服务繁忙"}
                raise PolicyError(messages.get(response.status, "TypeSafe 拒绝请求") + f"（HTTP {response.status}）；没有自动重试。",
                                  category="typesafe_http", http_status=response.status)
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise PolicyError("Jev 响应超过大小限制。")
            try:
                result = json.loads(raw, object_pairs_hook=unique_object,
                                    parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            except (ValueError, UnicodeError, RecursionError):
                raise PolicyError("Jev 返回无效 JSON；未执行动作。") from None
            return result
        except PolicyError:
            raise
        except TimeoutError:
            raise PolicyError("Jev 请求超时；未执行动作，没有自动重试。", category="timeout") from None
        except Exception:
            raise PolicyError("无法连接 TypeSafe；请检查网络和专用密钥。", category="connection") from None
        finally:
            connection.close()

    def choose(self, state, criteria, instructions):
        self.last_usage, self.last_latency = {"jev_requests": 1}, 0.0
        payload = json.dumps({"model": self.model, "state": state, "questions": {
            "action": {"type": "choice", "instructions": instructions, "criteria": criteria}
        }}, ensure_ascii=False, allow_nan=False).encode()
        started = time.monotonic()
        try:
            result = validate_choice(self._post(payload), criteria, self.model)
            self.last_usage.update(result["usage"])
            return result
        finally:
            self.last_latency = time.monotonic() - started

    def close(self):
        self._key = ""
