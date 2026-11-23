"""Minimal Ollama HTTP client (/api/chat, /api/tags). No SDK needed."""

from __future__ import annotations

from typing import Any

import httpx


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, host: str, timeout_s: float = 300, keep_alive: str = "10m",
                 transport: httpx.BaseTransport | None = None):
        self.host = host.rstrip("/")
        self.keep_alive = keep_alive
        self._http = httpx.Client(base_url=self.host, timeout=timeout_s, transport=transport)

    def chat(self, model: str, messages: list[dict[str, Any]], *,
             tools: list[dict[str, Any]] | None = None,
             options: dict[str, Any] | None = None) -> dict[str, Any]:
        """One non-streaming chat turn. Returns the assistant message dict."""
        opts = dict(options or {})
        think = opts.pop("think", None)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": opts,
        }
        if think is not None:
            payload["think"] = think
        if tools:
            payload["tools"] = tools
        try:
            r = self._http.post("/api/chat", json=payload)
        except httpx.ConnectError as e:
            raise OllamaError(f"Cannot reach Ollama at {self.host}. Is it running? (systemctl status ollama)") from e
        if r.status_code == 404:
            raise OllamaError(f"Model '{model}' not found. Run: ollama pull {model}")
        if r.status_code >= 400:
            raise OllamaError(f"Ollama error {r.status_code}: {r.text[:300]}")
        return r.json().get("message", {})

    def list_models(self) -> list[str]:
        try:
            r = self._http.get("/api/tags")
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise OllamaError(f"Cannot reach Ollama at {self.host}: {e}") from e
        return [m["name"] for m in r.json().get("models", [])]

    def close(self) -> None:
        self._http.close()
