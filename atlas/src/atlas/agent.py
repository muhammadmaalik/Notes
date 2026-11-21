"""Atlas agent: route -> chat with tools -> store in memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .config import Config
from .memory import Memory
from .ollama_client import OllamaClient
from .router import Route, route
from .tools.registry import ToolRegistry


@dataclass
class Reply:
    text: str
    role: str
    model: str
    route_reason: str
    tool_calls: list[str] = field(default_factory=list)


class Atlas:
    def __init__(self, cfg: Config, client: OllamaClient, memory: Memory, tools: ToolRegistry):
        self.cfg, self.client, self.memory, self.tools = cfg, client, memory, tools

    def _system(self) -> dict[str, str]:
        stamp = datetime.now().strftime("%A %Y-%m-%d %H:%M")
        return {"role": "system", "content": f"{self.cfg.system_prompt}\nCurrent local time: {stamp}."}

    def ask(self, conversation_id: int, text: str, force_role: str | None = None) -> Reply:
        r = Route(force_role, "forced by user", 0) if force_role else route(text, self.cfg, self.client)
        model = self.cfg.model_for(r.role)
        options = self.cfg.options_for(r.role)

        messages = [self._system(), *self.memory.history(conversation_id, limit=20),
                    {"role": "user", "content": text}]
        self.memory.add_message(conversation_id, "user", text)

        called: list[str] = []
        final = ""
        for _ in range(self.cfg.max_tool_steps + 1):
            msg = self.client.chat(model, messages, tools=self.tools.schemas(), options=options)
            calls = msg.get("tool_calls") or []
            if not calls:
                final = (msg.get("content") or "").strip()
                break
            messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": calls})
            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                result = self.tools.call(name, fn.get("arguments") or {})
                called.append(name)
                messages.append({"role": "tool", "tool_name": name, "content": result})
        else:
            final = "I hit the tool-step limit before finishing. Try a narrower request."

        self.memory.add_message(conversation_id, "assistant", final, model=model, route_reason=r.reason)
        return Reply(final, r.role, model, r.reason, called)
