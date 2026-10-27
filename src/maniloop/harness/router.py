"""Role -> model routing. Defaults to the connected model for every role."""

from __future__ import annotations

ROLES = ("planner", "verifier", "reflector")


class RoleRouter:
    """Per-role model overrides, e.g. a cheaper model for verification."""

    def __init__(self, default_model: str, overrides: dict | None = None):
        self.default_model = default_model
        clean = {}
        for role, model in (overrides or {}).items():
            if role in ROLES and isinstance(model, str) and model.strip():
                clean[role] = model.strip()[:120]
        self.overrides = clean

    def model_for(self, role: str) -> str:
        return self.overrides.get(role, self.default_model)
