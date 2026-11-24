import hashlib
import json
import math
from pathlib import Path

import httpx
import pytest

from atlas.config import load_config
from atlas.memory import Memory
from atlas.ollama_client import ClientPool, OllamaClient


PROFILE_FIXTURE = Path(__file__).parent / "fixtures" / "profile.yaml"


def fake_embedding(text: str, dim: int = 64) -> list[float]:
    """Deterministic bag-of-words vector, so similar sentences get similar vectors."""
    v = [0.0] * dim
    for w in text.lower().replace(".", " ").replace(",", " ").split():
        h = int(hashlib.md5(w.encode()).hexdigest(), 16)
        v[h % dim] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class FakeOllama:
    """Scripted stand-in for the Ollama HTTP API (chat, streaming chat, embed, tags, generate).

    `replies` items are message dicts or callables(body) -> message dict.
    `responder`, if set, answers every chat request instead of `replies`.
    """

    def __init__(self, replies=None, models=("qwen3.5:4b", "qwen3.5:9b", "qwen3-embedding:0.6b"), responder=None):
        self.replies = list(replies or [])
        self.models = list(models)
        self.responder = responder
        self.requests: list[dict] = []
        self.embed_requests: list[dict] = []
        self.generate_requests: list[dict] = []
        self.loaded: list[dict] = []          # what /api/ps reports as loaded

    def _next(self, body):
        if self.responder:
            return self.responder(body)
        r = self.replies.pop(0) if self.replies else {"role": "assistant", "content": "ok"}
        return r(body) if callable(r) else r

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": m} for m in self.models]})
        if path == "/api/ps":
            return httpx.Response(200, json={"models": self.loaded})
        body = json.loads(request.content or b"{}")
        if path == "/api/embed":
            self.embed_requests.append(body)
            inputs = body["input"] if isinstance(body["input"], list) else [body["input"]]
            return httpx.Response(200, json={"embeddings": [fake_embedding(t) for t in inputs]})
        if path == "/api/generate":
            self.generate_requests.append(body)
            return httpx.Response(200, json={"done": True})
        if path == "/api/chat":
            self.requests.append(body)
            msg = dict(self._next(body))
            msg.setdefault("role", "assistant")
            if not body.get("stream"):
                return httpx.Response(200, json={"model": body["model"], "message": msg, "done": True})
            lines = []
            if msg.get("thinking"):
                for part in [msg["thinking"][i:i + 7] for i in range(0, len(msg["thinking"]), 7)]:
                    lines.append({"message": {"role": "assistant", "content": "", "thinking": part}, "done": False})
            content = msg.get("content", "")
            for part in [content[i:i + 5] for i in range(0, len(content), 5)]:
                lines.append({"message": {"role": "assistant", "content": part}, "done": False})
            if msg.get("tool_calls"):
                lines.append({"message": {"role": "assistant", "content": "", "tool_calls": msg["tool_calls"]},
                              "done": False})
            lines.append({"message": {"role": "assistant", "content": ""}, "done": True})
            return httpx.Response(200, content="\n".join(json.dumps(x) for x in lines).encode(),
                                  headers={"content-type": "application/x-ndjson"})
        return httpx.Response(404, json={"error": "not found"})

    def client(self) -> OllamaClient:
        return OllamaClient("http://fake:11434", transport=httpx.MockTransport(self.handler))

    def pool(self, cfg) -> ClientPool:
        return ClientPool.single(cfg, self.client())

    def system_prompt(self, i: int = 0) -> str:
        return self.requests[i]["messages"][0]["content"]


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ATLAS_DB", str(tmp_path / "atlas.db"))
    monkeypatch.setenv("ATLAS_REPORTS", str(tmp_path / "reports"))
    c = load_config("laptop")
    c.workspace = tmp_path / "ws"
    c.profile_path = PROFILE_FIXTURE     # tests don't depend on your edited configs/profile.yaml
    c.memory["extract"] = False          # tests opt in to background extraction explicitly
    c.research["formats"] = ["md"]
    return c


@pytest.fixture
def mem(cfg):
    return Memory(cfg.db_path)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ("OLLAMA_HOST_URL", "ATLAS_PROFILE", "ATLAS_USER_PROFILE"):
        monkeypatch.delenv(var, raising=False)
