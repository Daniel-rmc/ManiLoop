"""Shared sensor request encoding and credential-free provenance.

This describes client-submitted data, not hidden provider instructions or actual
reasoning compute. Image hashes preserve order and identify exact source bytes.
"""
import base64
import hashlib
import json


def _hash(value):
    data = json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def build_policy_request(*, model, instructions, task, observation, history,
                         geometry_results, images, schema, max_output_tokens,
                         reasoning_effort):
    content = [{"type": "input_text", "text": json.dumps(
        {"task": task, "observation": observation, "history": history[-12:],
         "geometry_results": geometry_results[-8:]}, ensure_ascii=False,
        allow_nan=False, separators=(",", ":"))}]
    for camera, data in images.items():
        mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
        content.extend([
            {"type": "input_text", "text": f"Camera: {camera}. This labels the input image, not the action camera field."},
            {"type": "input_image", "image_url": f"data:{mime};base64," + base64.b64encode(data).decode("ascii"), "detail": "high"},
        ])
    request = {"model": model, "instructions": instructions,
               "input": [{"role": "user", "content": content}],
               "text": {"format": {"type": "json_schema", "name": "robot_action",
                                    "strict": True, "schema": schema}}, "store": False}
    if max_output_tokens is not None:
        request["max_output_tokens"] = max_output_tokens
    if reasoning_effort is not None:
        request["reasoning"] = {"effort": reasoning_effort}
    return request


def request_manifest(request, *, transport, requested=None, unsupported=None):
    """No keys, account identifiers, image data, task text, or provider URLs."""
    sensor = {key: request[key] for key in ("instructions", "input", "text") if key in request}
    images = []
    for message in request.get("input", []):
        for part in message.get("content", []):
            if part.get("type") == "input_image":
                uri = part["image_url"]
                header, data = uri.split(",", 1)
                images.append({"sha256": hashlib.sha256(base64.b64decode(data, validate=True)).hexdigest(),
                               "mime": header.split(";")[0].removeprefix("data:"),
                               "detail": part.get("detail")})
    return {"version": "policy_request_v1", "transport": transport,
            "model_requested": request.get("model"),
            "sensor_request_sha256": _hash(sensor),
            "instructions_sha256": _hash(request.get("instructions", "")),
            "input_sha256": _hash(request.get("input", [])),
            "schema_sha256": _hash(request.get("text", {})), "images": images,
            "requested": dict(requested or {}),
            "sent": {key: request[key] for key in ("reasoning", "max_output_tokens", "store", "stream") if key in request},
            "unsupported": list(unsupported or []),
            "scope": "client_submitted_request; not provider internals or equal compute"}
