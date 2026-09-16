"""Text-only API diagnostics. No environment, tools, actions or persistent chats."""

import hashlib
import json
import os
import re
import threading
import time

from openai import APIConnectionError, APIStatusError, APITimeoutError
from maniloop.providers.credentials import (
    ConfigError, _make, discover_configs, load_local_config, load_toml_config,
)
from maniloop.providers.catalog import fetch_models
from maniloop.providers.responses import DEFAULT_MODEL, GPTPolicy, PolicyError, _empty_response_detail


def redact(value, key):
    """Only selected response fields reach the UI; never return a raw response."""
    if isinstance(value, str):
        value = value.replace(key, "[REDACTED]") if key else value
        value = re.sub(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", value)
        value = re.sub(r"sk-[A-Za-z0-9_-]{12,}", "[REDACTED]", value)
        return value[:24000]
    if isinstance(value, dict):
        return {k: redact(v, key) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, key) for v in value]
    return value


def response_summary(body, protocol):
    """Retain visible text even for failed/partial responses, clearly marked."""
    if not isinstance(body, dict):
        return {"complete": False, "reply": "", "category": "invalid_json_shape"}
    details = {"response_id": body.get("id"), "returned_model": body.get("model"),
               "status": body.get("status"), "error": None, "incomplete_reason": None}
    error = body.get("error")
    if isinstance(error, dict):
        details["error"] = {k: error.get(k) for k in ("code", "type", "message")}
    elif error is not None:
        details["error"] = str(error)[:2000]
    incomplete = body.get("incomplete_details")
    details["incomplete_reason"] = incomplete.get("reason") if isinstance(incomplete, dict) else incomplete
    usage = body.get("usage")
    details["usage"] = {k: v for k, v in usage.items() if k in {
        "input_tokens", "output_tokens", "prompt_tokens", "completion_tokens", "total_tokens"
    } and type(v) is int and v >= 0} if isinstance(usage, dict) else None
    texts, refusals = [], []
    valid = True
    if protocol == "responses":
        output = body.get("output")
        valid = isinstance(output, list) and bool(output)
        details["output_items"] = []
        for item in output if isinstance(output, list) else []:
            if not isinstance(item, dict):
                valid = False
                continue
            details["output_items"].append({k: item.get(k) for k in ("type", "status", "role")})
            if item.get("type") == "reasoning":
                continue  # Internal reasoning is not a chat response.
            valid &= item.get("type") == "message" and item.get("role") == "assistant" and item.get("status") == "completed"
            for part in item.get("content", []) if isinstance(item.get("content"), list) else []:
                if not isinstance(part, dict):
                    valid = False
                elif part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    texts.append(part["text"])
                elif part.get("type") == "refusal":
                    refusals.append(str(part.get("refusal", "请求被拒绝")))
                else:
                    valid = False
        valid &= body.get("status") == "completed"
        valid &= _empty_response_detail(error, {"code", "message"})
        valid &= _empty_response_detail(incomplete, {"reason"})
        if not isinstance(output, list) and "choices" in body:
            details["protocol_hint"] = "Responses 地址返回了 Chat Completions 格式，请核对供应商协议。"
    else:
        choices = body.get("choices")
        valid = isinstance(choices, list) and len(choices) == 1
        first = choices[0] if valid and isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        details["finish_reason"] = first.get("finish_reason")
        if isinstance(message.get("content"), str):
            texts.append(message["content"])
        if message.get("refusal"):
            refusals.append(str(message["refusal"]))
        valid &= first.get("finish_reason") == "stop" and message.get("role") == "assistant"
        valid &= _empty_response_detail(error, {"code", "message"})
        if not isinstance(choices, list) and "output" in body:
            details["protocol_hint"] = "Chat Completions 地址返回了 Responses 格式，请核对供应商协议。"
    reply = "\n".join(texts)
    complete = bool(valid and reply.strip() and not refusals)
    return {**details, "reply": reply, "refusal": "\n".join(refusals),
            "complete": complete, "category": "completed" if complete else "incomplete_or_invalid_response"}


class ChatService:
    """Each send re-reads credentials. One request, no retries or protocol fallback."""

    def __init__(self, default_model=None):
        self.default_model = default_model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
        self.lock = threading.Lock()

    def options(self, *, discover=False):
        configs = discover_configs() if discover else []
        return {"ok": True, "configs": configs, "default_model": self.default_model}

    def resolve(self, payload, allow_missing_key=False):
        source = payload.get("credential_source", "manual")
        key = payload.get("api_key") or None
        if source == "file":
            return load_local_config(payload.get("config_path"), api_key=key, allow_missing_key=allow_missing_key, allowed_transports=("responses", "chat", "chat_completions"))
        if source == "upload":
            return load_toml_config(payload.get("config_toml"), api_key=key, allow_missing_key=allow_missing_key, allowed_transports=("responses", "chat", "chat_completions"))
        if source != "manual":
            raise ConfigError("请选择手动配置、本地配置或导入 TOML")
        return _make(key or os.environ.get("OPENAI_API_KEY"),
                     payload.get("base_url") or os.environ.get("OPENAI_BASE_URL"),
                     payload.get("model") or self.default_model, "手动配置", "",
                     allow_missing_key=allow_missing_key)

    def handle(self, name, payload):
        config = self.resolve(payload, allow_missing_key=name == "preview")
        if name == "preview":
            return {"ok": True, "config": config.public()}
        if name == "models":
            return redact({"ok": True, "models": fetch_models(config.api_key, config.base_url),
                           "config": config.public()}, config.api_key)
        if name != "send":
            raise ConfigError("未知聊天操作")
        protocol = payload.get("protocol", "responses")
        if protocol not in {"responses", "chat_completions"}:
            raise ConfigError("请选择 Responses 或 Chat Completions")
        model = payload.get("model") or config.model or self.default_model
        if not isinstance(model, str) or not model.strip() or len(model) > 120:
            raise ConfigError("请输入有效的模型名称")
        messages = payload.get("messages")
        if not isinstance(messages, list) or not 1 <= len(messages) <= 41 or len(messages) % 2 != 1:
            raise ConfigError("对话最多保留 20 轮，请清空后继续")
        for i, msg in enumerate(messages):
            if (not isinstance(msg, dict) or set(msg) != {"role", "content"}
                or msg["role"] != ("user" if i % 2 == 0 else "assistant")
                or not isinstance(msg["content"], str) or not msg["content"].strip()
                or len(msg["content"]) > 24000):
                raise ConfigError("消息必须为非空文字，且按用户／助手交替排列")
        if sum(len(m["content"]) for m in messages) > 64000:
            raise ConfigError("对话过长，请清空对话后继续")
        connection_id = hashlib.sha256(json.dumps([config.fingerprint, model, protocol]).encode()).hexdigest()
        if len(messages) > 1 and payload.get("connection_id") != connection_id:
            raise ConfigError("供应商、密钥、协议或模型已变化，请清空对话再发送，避免将旧对话发送到新服务")
        if not self.lock.acquire(blocking=False):
            raise ConfigError("已有聊天请求正在处理，请等待结果后再发送")
        policy = None
        started = time.monotonic()
        result = {"ok": True, "transport_ok": False, "complete": False, "reply": "",
                  "protocol": protocol, "model": model, "endpoint": config.base_url,
                  "connection_id": connection_id, "http_status": None}
        try:
            supplied = payload.get("request_options", {})
            if not isinstance(supplied, dict):
                raise ConfigError("请求设置格式无效")
            options = {"timeout_seconds": 120, "max_output_tokens": 4096, **supplied}
            policy = GPTPolicy(model=model, api_key=config.api_key, base_url=config.base_url, request_options=options)
            result["request_options"] = policy.request_options
            common = {"model": model, "store": False}
            if protocol == "responses":
                common.update(input=messages, max_output_tokens=policy.max_output_tokens)
                if policy.reasoning_effort:
                    common["reasoning"] = {"effort": policy.reasoning_effort}
                raw = policy.client.responses.with_raw_response.create(**common)
            else:
                common.update(messages=messages, max_completion_tokens=policy.max_output_tokens)
                if policy.reasoning_effort:
                    common["reasoning_effort"] = policy.reasoning_effort
                raw = policy.client.chat.completions.with_raw_response.create(**common)
            result["http_status"] = raw.status_code
            result["transport_ok"] = 200 <= raw.status_code < 300
            try:
                body = raw.http_response.json()
            except (ValueError, UnicodeError):
                result.update(category="invalid_json", error="服务返回非 JSON 内容，请检查 API 地址和所选协议")
            else:
                result.update(response_summary(body, protocol))
        except APITimeoutError:
            result.update(category="timeout", error="请求超时；无法确认供应商是否已生成回复或计费。可增加超时后手动重试。")
        except APIConnectionError:
            result.update(category="connection", error="无法连接服务，请检查 API 地址和网络")
        except APIStatusError as exc:
            body = exc.body if isinstance(exc.body, dict) else {}
            err = body.get("error", body)
            result.update(category="http_error", http_status=exc.status_code,
                          error={k: err.get(k) for k in ("code", "type", "message")} if isinstance(err, dict) else "供应商拒绝请求")
        except ConfigError:
            raise
        except PolicyError as exc:
            raise ConfigError(str(exc)) from None
        except Exception:
            result.update(category="request_error", error="请求或响应解析失败；请检查协议与请求设置")
        finally:
            result["latency_seconds"] = round(time.monotonic() - started, 3)
            if policy is not None:
                try:
                    policy.close()
                except Exception:
                    pass
            self.lock.release()
        return redact(result, config.api_key)
