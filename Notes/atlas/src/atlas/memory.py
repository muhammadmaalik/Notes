"""SQLite storage: conversations, messages, deadlines, and a tool audit log."""

from __future__ import annotations

import sqlite3
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


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Memory:
    def __init__(self, db_path: str | Path):
        db_path = Path(db_path)
        if str(db_path) != ":memory:":
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- conversations -------------------------------------------------
    def new_conversation(self, title: str | None = None) -> int:
        cur = self.conn.execute("INSERT INTO conversations (started_at, title) VALUES (?, ?)", (now(), title))
        self.conn.commit()
        return int(cur.lastrowid)

    def add_message(self, conversation_id: int, role: str, content: str,
                    model: str | None = None, route_reason: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO messages (conversation_id, role, content, model, route_reason, created_at) VALUES (?,?,?,?,?,?)",
            (conversation_id, role, content, model, route_reason, now()),
        )
        self.conn.commit()

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

    # ---- deadlines -----------------------------------------------------
    def add_deadline(self, title: str, due: str, course: str | None = None) -> int:
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
        cur = self.conn.execute("UPDATE deadlines SET done=1 WHERE id=?", (deadline_id,))
        self.conn.commit()
        return cur.rowcount > 0

    # ---- audit ---------------------------------------------------------
    def log_tool(self, tool: str, args: str, tier: str, allowed: bool, result: str | None) -> None:
        self.conn.execute(
            "INSERT INTO tool_log (tool, args, tier, allowed, result, created_at) VALUES (?,?,?,?,?,?)",
            (tool, args, tier, int(allowed), (result or "")[:2000], now()),
        )
        self.conn.commit()
