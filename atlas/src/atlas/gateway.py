"""FastAPI gateway. Binds to localhost by default.

Over HTTP there is no one to answer y/N, so CHANGE-tier tools are denied here.
Use the CLI for actions that need approval.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .agent import Atlas
from .config import Config, load_config
from .memory import Memory
from .ollama_client import OllamaClient, OllamaError
from .tools.builtin import build_registry
from .tools.registry import deny_all


class ChatIn(BaseModel):
    message: str
    conversation_id: int | None = None
    role: str | None = None   # "fast" | "reasoning" | None (auto)


class ChatOut(BaseModel):
    conversation_id: int
    reply: str
    role: str
    model: str
    route_reason: str
    tool_calls: list[str]


def create_app(cfg: Config | None = None, client: OllamaClient | None = None,
               memory: Memory | None = None) -> FastAPI:
    cfg = cfg or load_config()
    client = client or OllamaClient(cfg.ollama_host, cfg.timeout_s, cfg.keep_alive)
    memory = memory or Memory(cfg.db_path)
    atlas = Atlas(cfg, client, memory, build_registry(memory, cfg.workspace, confirm=deny_all))
    app = FastAPI(title="Atlas", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        try:
            models = client.list_models()
            ok = True
        except OllamaError:
            models, ok = [], False
        return {"ok": ok, "profile": cfg.profile, "models": cfg.models, "installed": models}

    @app.post("/chat", response_model=ChatOut)
    def chat(body: ChatIn) -> ChatOut:
        if body.role not in (None, "fast", "reasoning"):
            raise HTTPException(400, "role must be fast, reasoning or omitted")
        cid = body.conversation_id or memory.new_conversation()
        try:
            r = atlas.ask(cid, body.message, force_role=body.role)
        except OllamaError as e:
            raise HTTPException(503, str(e)) from e
        return ChatOut(conversation_id=cid, reply=r.text, role=r.role, model=r.model,
                       route_reason=r.route_reason, tool_calls=r.tool_calls)

    @app.get("/deadlines")
    def deadlines(include_done: bool = False) -> list[dict]:
        return memory.list_deadlines(include_done=include_done)

    return app
