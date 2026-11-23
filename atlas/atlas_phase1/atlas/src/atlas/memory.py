"""SQLite storage: conversations, messages, deadlines, and a tool audit log."""

from __future__ import annotations

import json
import math
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    title TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    model TEXT,
    route_reason TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    due TEXT NOT NULL,
    course TEXT,
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    embedding TEXT,
    source TEXT NOT NULL DEFAULT 'auto',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tool_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool TEXT NOT NULL,
    args TEXT NOT NULL,
    tier TEXT NOT NULL,
    allowed INTEGER NOT NULL,
    result TEXT,
    created_at TEXT NOT NULL
);
"""


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Memory:
    def __init__(self, db_path: str | Path):
        db_path = Path(db_path)
        if str(db_path) != ":memory:":
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()   # background fact extraction writes from another thread
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(messages)")}
        if "route" not in cols:
            self.conn.execute("ALTER TABLE messages ADD COLUMN route TEXT")
        if "topic" not in cols:
            self.conn.execute("ALTER TABLE messages ADD COLUMN topic TEXT")

    # ---- conversations -------------------------------------------------
    def new_conversation(self, title: str | None = None) -> int:
        with self.lock:
            cur = self.conn.execute("INSERT INTO conversations (started_at, title) VALUES (?, ?)", (now(), title))
            self.conn.commit()
            return int(cur.lastrowid)

    def add_message(self, conversation_id: int, role: str, content: str, model: str | None = None,
                    route_reason: str | None = None, route: str | None = None, topic: str | None = None) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO messages (conversation_id, role, content, model, route_reason, route, topic, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (conversation_id, role, content, model, route_reason, route, topic, now()),
            )
            self.conn.commit()

    def last_assistant(self, conversation_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT route, topic, content FROM messages WHERE conversation_id=? AND role='assistant'"
            " ORDER BY id DESC LIMIT 1", (conversation_id,)).fetchone()
        return dict(row) if row else None

    def last_topic(self, conversation_id: int) -> str | None:
        """Most recent topic: a research topic or the last substantive (non-follow-up) user message."""
        from .router import is_followup, parse_command
        rows = self.conn.execute(
            "SELECT content, topic FROM messages WHERE conversation_id=? AND role='user' ORDER BY id DESC LIMIT 8",
            (conversation_id,)).fetchall()
        for r in rows:
            if r["topic"]:
                return r["topic"]
            _cmd, content = parse_command(r["content"])
            if not is_followup(content) and len(content.split()) >= 3:
                return content[:300]
        return None

    def history(self, conversation_id: int, limit: int = 20) -> list[dict[str, str]]:
        rows = self.conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def recent_conversations(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT c.id, c.started_at, COUNT(m.id) AS n,
                      (SELECT content FROM messages WHERE conversation_id=c.id AND role='user' ORDER BY id LIMIT 1) AS first
               FROM conversations c LEFT JOIN messages m ON m.conversation_id=c.id
               GROUP BY c.id ORDER BY c.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- facts (long-term memory) ------------------------------------
    def add_fact(self, text: str, embedding: list[float] | None = None, source: str = "auto",
                 dedupe_threshold: float = 0.9) -> int | None:
        """Store a fact unless an (almost) identical active one exists. Returns id or None."""
        text = text.strip()
        if not text:
            return None
        with self.lock:
            for f in self._active_facts():
                if f["text"].lower() == text.lower():
                    return None
                if embedding and f["embedding"] and cosine(embedding, f["embedding"]) >= dedupe_threshold:
                    return None
            cur = self.conn.execute(
                "INSERT INTO facts (text, embedding, source, created_at) VALUES (?,?,?,?)",
                (text, json.dumps(embedding) if embedding else None, source, now()))
            self.conn.commit()
            return int(cur.lastrowid)

    def _active_facts(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute("SELECT id, text, embedding, source, created_at FROM facts WHERE active=1"
                                     " ORDER BY id").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["embedding"] = json.loads(d["embedding"]) if d["embedding"] else None
            out.append(d)
        return out

    def list_facts(self) -> list[dict[str, Any]]:
        return [{k: v for k, v in f.items() if k != "embedding"} for f in self._active_facts()]

    def forget_fact(self, fact_id: int) -> bool:
        """Soft-forget: hidden from Atlas, kept in the DB file (sqlite3 can purge it)."""
        with self.lock:
            cur = self.conn.execute("UPDATE facts SET active=0 WHERE id=? AND active=1", (fact_id,))
            self.conn.commit()
            return cur.rowcount > 0

    def search_facts(self, query_embedding: list[float] | None, k: int = 6, min_similarity: float = 0.35,
                     query_text: str = "") -> list[dict[str, Any]]:
        """Top-k facts by cosine similarity; falls back to keyword overlap + recency without embeddings."""
        facts = self._active_facts()
        if not facts:
            return []
        if query_embedding:
            scored = [(cosine(query_embedding, f["embedding"]) if f["embedding"] else 0.0, f) for f in facts]
            hits = [f | {"score": s} for s, f in sorted(scored, key=lambda x: -x[0]) if s >= min_similarity]
            return hits[:k]
        words = {w for w in query_text.lower().split() if len(w) > 3}
        scored = [(len(words & set(f["text"].lower().split())), f["id"], f) for f in facts]
        scored.sort(key=lambda x: (-x[0], -x[1]))
        return [f | {"score": float(s)} for s, _i, f in scored[:k]]

    # ---- deadlines -----------------------------------------------------
    def add_deadline(self, title: str, due: str, course: str | None = None) -> int:
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO deadlines (title, due, course, created_at) VALUES (?,?,?,?)",
                (title, due, course, now()),
            )
            self.conn.commit()
            return int(cur.lastrowid)

    def list_deadlines(self, include_done: bool = False) -> list[dict[str, Any]]:
        q = "SELECT * FROM deadlines" + ("" if include_done else " WHERE done=0") + " ORDER BY due ASC"
        return [dict(r) for r in self.conn.execute(q).fetchall()]

    def complete_deadline(self, deadline_id: int) -> bool:
        with self.lock:
            cur = self.conn.execute("UPDATE deadlines SET done=1 WHERE id=?", (deadline_id,))
            self.conn.commit()
            return cur.rowcount > 0

    # ---- audit ---------------------------------------------------------
    def log_tool(self, tool: str, args: str, tier: str, allowed: bool, result: str | None) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO tool_log (tool, args, tier, allowed, result, created_at) VALUES (?,?,?,?,?,?)",
                (tool, args, tier, int(allowed), (result or "")[:2000], now()),
            )
            self.conn.commit()
