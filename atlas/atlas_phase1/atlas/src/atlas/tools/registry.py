"""Tool registry with permission tiers.

READ    -> runs automatically (still logged)
CHANGE  -> asks y/N through a confirm callback before running
FORBIDDEN -> can never be registered (deletes, sudo, sending messages, payments)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

FORBIDDEN_NAME_PARTS = ("delete", "remove", "rm", "sudo", "format", "kill", "send", "pay", "purchase")


class Tier(str, Enum):
    READ = "read"
    CHANGE = "change"
    FORBIDDEN = "forbidden"


ConfirmFn = Callable[[str, dict[str, Any]], bool]


def deny_all(_name: str, _args: dict[str, Any]) -> bool:
    return False


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]          # JSON schema for the arguments
    func: Callable[..., str]
    tier: Tier = Tier.READ

    def schema(self) -> dict[str, Any]:
        """Ollama / OpenAI tool-calling format."""
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.parameters}}


class PermissionDenied(Exception):
    pass


class ToolRegistry:
    def __init__(self, confirm: ConfirmFn = deny_all, audit: Callable[..., None] | None = None):
        self._tools: dict[str, Tool] = {}
        self.confirm = confirm
        self.audit = audit

    def register(self, tool: Tool) -> None:
        if tool.tier == Tier.FORBIDDEN:
            raise PermissionDenied(f"Tool '{tool.name}' is FORBIDDEN tier and cannot be registered in v0.")
        parts = tool.name.lower().replace("-", "_").split("_")
        if any(p in FORBIDDEN_NAME_PARTS for p in parts):
            raise PermissionDenied(f"Tool name '{tool.name}' looks destructive; v0 does not allow it.")
        self._tools[tool.name] = tool

    def names(self) -> list[str]:
        return sorted(self._tools)

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    def call(self, name: str, args: dict[str, Any] | str | None) -> str:
        if isinstance(args, str):
            args = json.loads(args or "{}")
        args = args or {}
        if name not in self._tools:
            return f"ERROR: unknown tool '{name}'. Available: {', '.join(self.names())}"
        tool = self._tools[name]
        allowed = tool.tier == Tier.READ or (tool.tier == Tier.CHANGE and self.confirm(name, args))
        if not allowed:
            result = f"DENIED: the user did not approve '{name}'. Do not retry; tell the user what you wanted to do."
        else:
            try:
                result = tool.func(**args)
            except TypeError as e:
                result = f"ERROR: bad arguments for {name}: {e}"
            except Exception as e:  # tools must never crash the chat loop
                result = f"ERROR: {e.__class__.__name__}: {e}"
        if self.audit:
            self.audit(name, json.dumps(args, default=str), tool.tier.value, allowed, result)
        return result
