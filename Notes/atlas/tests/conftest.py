import json
from pathlib import Path

import httpx
import pytest

from atlas.config import load_config
from atlas.memory import Memory
from atlas.ollama_client import OllamaClient


class FakeOllama:
    """Scripted stand-in for the Ollama HTTP API."""

    def __init__(self, replies=None, models=("qwen3.5:4b", "qwen3.5:9b", "qwen3-embedding:0.6b")):
        self.replies = list(replies or [])
        self.models = list(models)
        self.requests: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": m} for m in self.models]})
        if request.url.path == "/api/chat":
            body = json.loads(request.content)
            self.requests.append(body)
            msg = self.replies.pop(0) if self.replies else {"role": "assistant", "content": "ok"}
            return httpx.Response(200, json={"model": body["model"], "message": msg, "done": True})
        return httpx.Response(404, json={"error": "not found"})

    def client(self) -> OllamaClient:
        return OllamaClient("http://fake:11434", transport=httpx.MockTransport(self.handler))


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ATLAS_DB", str(tmp_path / "atlas.db"))
    c = load_config("laptop")
    c.workspace = tmp_path / "ws"
    return c


@pytest.fixture
def mem(cfg):
    return Memory(cfg.db_path)
