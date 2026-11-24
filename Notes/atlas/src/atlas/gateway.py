"""FastAPI gateway (localhost by default).

Over HTTP there is no one to answer y/N, so CHANGE-tier tools are denied here.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .agent import Atlas
from .config import Config, load_config
from .memory import Memory
from .ollama_client import ClientPool, OllamaClient, OllamaError
from .tools.builtin import build_registry
from .tools.registry import deny_all


class ChatIn(BaseModel):
    message: str
    conversation_id: int | None = None
    role: str | None = None   # fast | reasoning | deep | research | None (auto)


class ChatOut(BaseModel):
    conversation_id: int
    reply: str
    role: str
    model: str
    route_reason: str
    tool_calls: list[str]
    report_path: str | None = None


def create_app(cfg: Config | None = None, client: OllamaClient | None = None,
               memory: Memory | None = None, pool: ClientPool | None = None) -> FastAPI:
    cfg = cfg or load_config()
    pool = pool or (ClientPool.single(cfg, client) if client else ClientPool(cfg))
    memory = memory or Memory(cfg.db_path)
    atlas = Atlas(cfg, pool, memory, build_registry(memory, cfg.workspace, confirm=deny_all))
    app = FastAPI(title="Atlas", version="0.2.0")

    @app.get("/health")
    def health() -> dict:
        hosts = {}
        installed: list[str] = []
        for host in sorted(set(cfg.hosts.values()) | {cfg.ollama_host}):
            try:
                models = pool.get(host).list_models()
                hosts[host] = True
                installed += models
            except OllamaError:
                hosts[host] = False
        return {"ok": all(hosts.values()), "profile": cfg.profile, "models": cfg.models,
                "hosts": hosts, "installed": sorted(set(installed))}

    @app.post("/chat", response_model=ChatOut)
    def chat(body: ChatIn) -> ChatOut:
        if body.role not in (None, "fast", "reasoning", "deep", "research"):
            raise HTTPException(400, "role must be fast, reasoning, deep, research or omitted")
        cid = body.conversation_id or memory.new_conversation()
        try:
            r = atlas.ask(cid, body.message, force_role=body.role)
        except OllamaError as e:
            raise HTTPException(503, str(e)) from e
        return ChatOut(conversation_id=cid, reply=r.text, role=r.role, model=r.model,
                       route_reason=r.route_reason, tool_calls=r.tool_calls, report_path=r.report_path)

    @app.get("/deadlines")
    def deadlines(include_done: bool = False) -> list[dict]:
        return memory.list_deadlines(include_done=include_done)

    @app.get("/memory")
    def memories() -> list[dict]:
        return memory.list_facts()

    return app
