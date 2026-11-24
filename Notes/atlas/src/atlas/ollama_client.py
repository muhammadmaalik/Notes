"""Minimal Ollama HTTP client: chat (blocking or streaming), embed, tags, unload."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, host: str, timeout_s: float = 300, keep_alive: str = "10m",
                 transport: httpx.BaseTransport | None = None):
        self.host = host.rstrip("/")
        self.keep_alive = keep_alive
        self._http = httpx.Client(base_url=self.host, timeout=httpx.Timeout(timeout_s, connect=10),
                                  transport=transport)

    # ---------------------------------------------------------------- helpers
    def _payload(self, model: str, messages: list[dict[str, Any]], tools, options, stream: bool,
                 fmt: Any = None) -> dict[str, Any]:
        opts = dict(options or {})
        think = opts.pop("think", None)
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": stream,
                                   "keep_alive": self.keep_alive, "options": opts}
        if think is not None:
            payload["think"] = think
        if tools:
            payload["tools"] = tools
        if fmt is not None:
            payload["format"] = fmt
        return payload

    def _check(self, r: httpx.Response, model: str) -> None:
        if r.status_code == 404:
            raise OllamaError(f"Model '{model}' not found on {self.host}. Run: ollama pull {model}")
        if r.status_code >= 400:
            r.read()
            raise OllamaError(f"Ollama error {r.status_code} on {self.host}: {r.text[:300]}")

    # ---------------------------------------------------------------- chat
    def chat(self, model: str, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None,
             options: dict[str, Any] | None = None, fmt: Any = None) -> dict[str, Any]:
        """One non-streaming chat turn. Returns the assistant message dict."""
        try:
            r = self._http.post("/api/chat", json=self._payload(model, messages, tools, options, False, fmt))
        except httpx.ConnectError as e:
            raise OllamaError(f"Cannot reach Ollama at {self.host}. Is it running? (systemctl status ollama)") from e
        self._check(r, model)
        return r.json().get("message", {})

    def chat_stream(self, model: str, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None,
                    options: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        """Yield message chunks: {'content'?, 'thinking'?, 'tool_calls'?}."""
        try:
            with self._http.stream("POST", "/api/chat",
                                   json=self._payload(model, messages, tools, options, True)) as r:
                self._check(r, model)
                for line in r.iter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if "error" in data:
                        raise OllamaError(str(data["error"]))
                    yield data.get("message", {})
                    if data.get("done"):
                        break
        except httpx.ConnectError as e:
            raise OllamaError(f"Cannot reach Ollama at {self.host}. Is it running? (systemctl status ollama)") from e

    def chat_collect(self, model: str, messages: list[dict[str, Any]], *, tools=None, options=None,
                     on_token: Callable[[str], None] | None = None,
                     on_thinking: Callable[[str], None] | None = None) -> dict[str, Any]:
        """Stream, call the callbacks, and return the merged assistant message."""
        content, thinking, calls = [], [], []
        for chunk in self.chat_stream(model, messages, tools=tools, options=options):
            if chunk.get("thinking"):
                thinking.append(chunk["thinking"])
                if on_thinking:
                    on_thinking(chunk["thinking"])
            if chunk.get("content"):
                content.append(chunk["content"])
                if on_token:
                    on_token(chunk["content"])
            if chunk.get("tool_calls"):
                calls.extend(chunk["tool_calls"])
        msg: dict[str, Any] = {"role": "assistant", "content": "".join(content)}
        if thinking:
            msg["thinking"] = "".join(thinking)
        if calls:
            msg["tool_calls"] = calls
        return msg

    # ---------------------------------------------------------------- other endpoints
    def embed(self, model: str, inputs: list[str]) -> list[list[float]]:
        try:
            r = self._http.post("/api/embed", json={"model": model, "input": inputs, "keep_alive": self.keep_alive})
        except httpx.ConnectError as e:
            raise OllamaError(f"Cannot reach Ollama at {self.host}") from e
        self._check(r, model)
        return r.json().get("embeddings", [])

    def unload(self, model: str) -> None:
        """Ask Ollama to free a model's VRAM now."""
        try:
            self._http.post("/api/generate", json={"model": model, "keep_alive": 0}, timeout=30)
        except httpx.HTTPError:
            pass

    def list_models(self) -> list[str]:
        try:
            r = self._http.get("/api/tags")
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise OllamaError(f"Cannot reach Ollama at {self.host}: {e}") from e
        return [m["name"] for m in r.json().get("models", [])]

    def ps(self) -> list[dict[str, Any]]:
        """Models currently loaded (name, size, size_vram, expires_at)."""
        try:
            r = self._http.get("/api/ps", timeout=5)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise OllamaError(f"Cannot reach Ollama at {self.host}: {e}") from e
        return r.json().get("models", [])

    def close(self) -> None:
        self._http.close()


class ClientPool:
    """One OllamaClient per host, so each role can live on its own GPU instance."""

    def __init__(self, cfg, factory: Callable[[str], OllamaClient] | None = None):
        self.cfg = cfg
        self._factory = factory or (lambda host: OllamaClient(host, cfg.timeout_s, cfg.keep_alive))
        self._clients: dict[str, OllamaClient] = {}

    @classmethod
    def single(cls, cfg, client: OllamaClient) -> ClientPool:
        """Every role goes to the same client (tests, simple setups)."""
        return cls(cfg, factory=lambda _host: client)

    def get(self, host: str) -> OllamaClient:
        if host not in self._clients:
            self._clients[host] = self._factory(host)
        return self._clients[host]

    def for_role(self, role: str) -> OllamaClient:
        return self.get(self.cfg.host_for(role))
