"""Long-term memory: extract durable facts after each turn, embed them, retrieve the relevant ones."""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config
    from .memory import Memory
    from .ollama_client import ClientPool

EXTRACT_PROMPT = """You maintain long-term memory for a personal assistant.
From the exchange below, extract DURABLE facts about the USER that will still be true and useful
in future conversations: identity, preferences, goals, projects, courses, schedule, people, tools they use.
Rules:
- Only facts stated or clearly implied by the USER. Ignore the assistant's claims and general knowledge.
- Skip one-off requests, small talk, and anything temporary ("is tired today").
- Never store passwords, ID numbers, financial, medical, immigration or citizenship details.
- Each fact is one short third-person sentence, e.g. "Maalik prefers metric units."
- Do not repeat facts already known (listed below).
Return JSON: {"facts": ["...", "..."]}  (empty list if nothing new).

Already known:
{known}

USER: {user}
ASSISTANT: {assistant}"""

BLOCKED_WORDS = ("password", "ssn", "social security", "passport", "visa", "citizenship", "immigration",
                 "green card", "bank account", "credit card")


class FactMemory:
    def __init__(self, cfg: Config, pool: ClientPool, memory: Memory):
        self.cfg, self.pool, self.memory = cfg, pool, memory
        self._threads: list[threading.Thread] = []

    # ---------------------------------------------------------------- embeddings
    def embed(self, texts: list[str]) -> list[list[float]] | None:
        if "embed" not in self.cfg.models:
            return None
        try:
            return self.pool.for_role("embed").embed(self.cfg.model_for("embed"), texts)
        except Exception:
            return None   # memory still works (keyword fallback) if the embed model is missing

    # ---------------------------------------------------------------- write
    def remember(self, text: str, source: str = "user") -> int | None:
        if any(w in text.lower() for w in BLOCKED_WORDS):
            return None
        vecs = self.embed([text])
        return self.memory.add_fact(text, vecs[0] if vecs else None, source=source)

    def extract(self, user_text: str, assistant_text: str) -> list[str]:
        """Run the fast model to pull out durable facts; store them. Returns the new facts."""
        known = "\n".join(f"- {f['text']}" for f in self.memory.list_facts()[-40:]) or "(none)"
        prompt = EXTRACT_PROMPT.replace("{known}", known).replace("{user}", user_text[:3000]) \
                               .replace("{assistant}", assistant_text[:1500])
        try:
            msg = self.pool.for_role("fast").chat(
                self.cfg.model_for("fast"), [{"role": "user", "content": prompt}],
                options={"think": False, "temperature": 0, "num_ctx": 4096}, fmt="json")
            data = json.loads(msg.get("content") or "{}")
            facts = [str(f).strip() for f in data.get("facts", []) if str(f).strip()]
        except Exception:
            return []
        saved = []
        for f in facts[:5]:
            if self.remember(f, source="auto") is not None:
                saved.append(f)
        return saved

    def extract_async(self, user_text: str, assistant_text: str) -> threading.Thread:
        t = threading.Thread(target=self.extract, args=(user_text, assistant_text), daemon=True)
        t.start()
        self._threads.append(t)
        return t

    def wait(self, timeout: float = 60) -> None:
        for t in self._threads:
            t.join(timeout)
        self._threads = [t for t in self._threads if t.is_alive()]

    # ---------------------------------------------------------------- read
    def relevant(self, query: str) -> list[str]:
        k = int(self.cfg.memory.get("top_k", 6))
        vecs = self.embed([query])
        hits = self.memory.search_facts(vecs[0] if vecs else None, k=k,
                                        min_similarity=float(self.cfg.memory.get("min_similarity", 0.35)),
                                        query_text=query)
        return [h["text"] for h in hits]

    def forget(self, what: str) -> list[str]:
        """Forget by id ('12') or by best text match. Returns the forgotten fact texts."""
        what = what.strip().lstrip("#")
        if what.isdigit():
            facts = {f["id"]: f["text"] for f in self.memory.list_facts()}
            fid = int(what)
            return [facts[fid]] if fid in facts and self.memory.forget_fact(fid) else []
        low = what.lower()
        matches = [f for f in self.memory.list_facts() if low in f["text"].lower()]
        if not matches:
            vecs = self.embed([what])
            if vecs:
                hits = self.memory.search_facts(vecs[0], k=1, min_similarity=0.6)
                matches = [{"id": h["id"], "text": h["text"]} for h in hits]
        out = []
        for m in matches[:3]:
            if self.memory.forget_fact(m["id"]):
                out.append(m["text"])
        return out
