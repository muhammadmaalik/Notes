"""Starter tools: web search, read file, list dir, write file (confirm), deadlines."""

from __future__ import annotations

from pathlib import Path

from ..dates import parse_due
from ..memory import Memory
from .registry import Tier, Tool, ToolRegistry

MAX_READ_BYTES = 20_000


def web_search(query: str, max_results: int = 5) -> str:
    """DuckDuckGo search via the `ddgs` package (no API key)."""
    from .. import web
    try:
        results = web.search(query, max_results)
    except ImportError:
        return "ERROR: ddgs not installed (uv sync)."
    except Exception as e:  # rate limits, offline, backend changes
        return f"Search failed ({e.__class__.__name__}: {e}). Try again or rephrase."
    if not results:
        return "No results."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', '')}\n   {r.get('href', '')}\n   {r.get('body', '')[:300]}")
    return "\n".join(lines)


def fetch_url(url: str, max_chars: int = 8000) -> str:
    """Read a web page's main text."""
    from .. import web
    if not url.startswith(("http://", "https://")):
        return "ERROR: url must start with http:// or https://"
    try:
        return web.fetch_text(url, max(500, min(int(max_chars), 20000)))
    except Exception as e:
        return f"ERROR: could not fetch {url}: {e.__class__.__name__}: {e}"


def read_file(path: str) -> str:
    p = Path(path).expanduser()
    if not p.is_file():
        return f"ERROR: not a file: {p}"
    data = p.read_bytes()[:MAX_READ_BYTES]
    text = data.decode("utf-8", errors="replace")
    suffix = "\n...[truncated]" if p.stat().st_size > MAX_READ_BYTES else ""
    return text + suffix


def list_dir(path: str = ".") -> str:
    p = Path(path).expanduser()
    if not p.is_dir():
        return f"ERROR: not a directory: {p}"
    entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))[:200]
    return "\n".join(f"{'[dir] ' if e.is_dir() else '      '}{e.name}" for e in entries) or "(empty)"


def make_write_file(workspace: Path):
    def write_file(path: str, content: str) -> str:
        """Write a text file inside the Atlas workspace only. Never overwrites."""
        ws = workspace.expanduser().resolve()
        target = (ws / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
        if ws != target and ws not in target.parents:
            return f"ERROR: write_file only writes inside {ws}"
        if target.exists():
            return f"ERROR: {target} already exists; v0 never overwrites files."
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"Wrote {len(content)} chars to {target}"
    return write_file


def make_deadline_tools(mem: Memory):
    def deadlines_list(include_done: bool = False) -> str:
        rows = mem.list_deadlines(include_done=include_done)
        if not rows:
            return "No deadlines."
        return "\n".join(
            f"#{r['id']} {'[done] ' if r['done'] else ''}{r['due']}  {r['title']}" + (f"  ({r['course']})" if r["course"] else "")
            for r in rows)

    def deadlines_add(title: str, due: str, course: str | None = None) -> str:
        due_norm = parse_due(due)
        new_id = mem.add_deadline(title, due_norm, course)
        return f"Added deadline #{new_id}: {title} due {due_norm}"

    return deadlines_list, deadlines_add


def build_registry(mem: Memory, workspace: Path, confirm=None) -> ToolRegistry:
    reg = ToolRegistry(audit=mem.log_tool) if confirm is None else ToolRegistry(confirm=confirm, audit=mem.log_tool)
    deadlines_list, deadlines_add = make_deadline_tools(mem)
    reg.register(Tool("web_search", "Search the web (DuckDuckGo). Returns titles, URLs and snippets.",
                      {"type": "object", "properties": {"query": {"type": "string"},
                                                        "max_results": {"type": "integer"}},
                       "required": ["query"]}, web_search, Tier.READ))
    reg.register(Tool("fetch_url", "Download a web page and return its main text, to actually read a source.",
                      {"type": "object", "properties": {"url": {"type": "string"},
                                                        "max_chars": {"type": "integer"}},
                       "required": ["url"]}, fetch_url, Tier.READ))
    reg.register(Tool("read_file", "Read a UTF-8 text file (first 20 KB).",
                      {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
                      read_file, Tier.READ))
    reg.register(Tool("list_dir", "List files in a directory.",
                      {"type": "object", "properties": {"path": {"type": "string"}}},
                      list_dir, Tier.READ))
    reg.register(Tool("write_file", f"Create a NEW text file inside the Atlas workspace ({workspace}). Needs user approval.",
                      {"type": "object", "properties": {"path": {"type": "string", "description": "path relative to the workspace"},
                                                        "content": {"type": "string"}},
                       "required": ["path", "content"]}, make_write_file(workspace), Tier.CHANGE))
    reg.register(Tool("deadlines_list", "List upcoming deadlines/tasks.",
                      {"type": "object", "properties": {"include_done": {"type": "boolean"}}},
                      deadlines_list, Tier.READ))
    reg.register(Tool("deadlines_add", "Add a deadline. due: YYYY-MM-DD [HH:MM], today, tomorrow, +3d, or a weekday. Needs user approval.",
                      {"type": "object", "properties": {"title": {"type": "string"}, "due": {"type": "string"},
                                                        "course": {"type": "string"}},
                       "required": ["title", "due"]}, deadlines_add, Tier.CHANGE))
    return reg
