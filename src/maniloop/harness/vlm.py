"""Shared JSON-in/JSON-out VLM transport for harness roles.

Reuses the executor policy's authenticated OpenAI-compatible client instead of
holding credentials of its own. Responses are parsed leniently: a reply cut
off mid-sentence is repaired by closing the brackets it left hanging (the
fields that matter come first; truncation lands in the trailing prose).
"""

from __future__ import annotations

import base64
import json
import re
import time
from typing import Any


class HarnessVLMError(RuntimeError):
    """The role's model never produced a parseable JSON reply."""


def _close_truncated_json(cleaned: str) -> str:
    out: list[str] = []
    stack: list[str] = []
    in_string = False
    escaped = False
    for char in cleaned:
        out.append(char)
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append("}" if char == "{" else "]")
        elif char in "}]" and stack:
            stack.pop()
    if in_string:
        out.append('"')
    text = "".join(out).rstrip()
    text = re.sub(r",\s*$", "", text)
    text = re.sub(r',\s*"[^"]*"?\s*:?\s*$', "", text)
    return text + "".join(reversed(stack))


def parse_json_object(raw: str) -> dict | None:
    """First {...} block of the reply, repaired if the output was truncated."""
    if not isinstance(raw, str):
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0:
        return None
    cleaned = raw[start : end + 1] if end > start else raw[start:]
    try:
        value = json.loads(cleaned)
    except (ValueError, RecursionError):
        try:
            value = json.loads(_close_truncated_json(cleaned))
        except (ValueError, RecursionError):
            return None
    return value if isinstance(value, dict) else None


class HarnessVLM:
    """One Responses-API JSON query channel bound to a role's model."""

    def __init__(self, client, model: str, *, max_output_tokens: int = 4096):
        self.client = client
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.last_usage: dict = {}
        self.last_latency = 0.0

    def query_json(
        self,
        instructions: str,
        payload: dict,
        images: dict[str, bytes] | None = None,
    ) -> dict:
        self.last_usage = {}
        self.last_latency = 0.0
        content: list[dict] = [
            {"type": "input_text", "text": json.dumps(payload, ensure_ascii=False, default=str)}
        ]
        for name, data in (images or {}).items():
            if not isinstance(data, (bytes, bytearray)) or not data:
                continue
            mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
            content.append({"type": "input_text", "text": f"Camera: {name}."})
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{mime};base64,"
                    + base64.b64encode(bytes(data)).decode("ascii"),
                    "detail": "high",
                }
            )
        request = {
            "model": self.model,
            "instructions": instructions,
            "input": [{"role": "user", "content": content}],
            "store": False,
            "max_output_tokens": self.max_output_tokens,
        }
        started = time.monotonic()
        try:
            response = self.client.responses.create(**request)
        except Exception as exc:
            raise HarnessVLMError(f"{self.model}: 请求失败（{type(exc).__name__}）") from None
        finally:
            self.last_latency = time.monotonic() - started
        usage = getattr(response, "usage", None)
        if usage is not None:
            for field_name in ("input_tokens", "output_tokens", "total_tokens"):
                count = getattr(usage, field_name, None)
                if type(count) is int and count >= 0:
                    self.last_usage[field_name] = count
        texts: list[str] = []
        for item in getattr(response, "output", None) or []:
            if getattr(item, "type", None) != "message":
                continue
            for part in getattr(item, "content", None) or []:
                if getattr(part, "type", None) == "output_text":
                    texts.append(getattr(part, "text", ""))
        parsed = parse_json_object("\n".join(texts))
        if parsed is None:
            raise HarnessVLMError(f"{self.model}: 响应不是可解析的 JSON")
        return parsed
