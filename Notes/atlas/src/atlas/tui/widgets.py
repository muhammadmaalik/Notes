"""Widgets and screens for the Atlas TUI."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Collapsible,
    Footer,
    Input,
    Label,
    Markdown,
    MarkdownViewer,
    ProgressBar,
    Static,
)

COMMANDS = ["/fast", "/reason", "/deep", "/auto", "/research", "/remember", "/forget", "/memory",
            "/new", "/help", "/thinking"]

HELP_MD = """\
**Commands** (Tab completes, ↑/↓ history)

| | |
|---|---|
| `/fast` `/reason` `/deep` `/auto` | switch mode (or prefix one message: `/deep <msg>`) |
| `/research <topic>` | multi-source cited report → `data/reports/` |
| `/remember <fact>` · `/forget <id or text>` · `/memory` | long-term memory |
| `/new` | start a new conversation |
| `/thinking` | expand/collapse thinking by default |

**Keys**: `F2` side panel · `ctrl+t` cycle mode · `ctrl+n` new chat · `ctrl+r` reports · `ctrl+q` quit
"""

ROLE_LABEL = {"fast": "fast", "reasoning": "reason", "deep": "deep", "research": "research"}


class HistoryInput(Input):
    """Input with ↑/↓ history and Tab completion of slash commands."""

    BINDINGS = [
        Binding("up", "history(-1)", "History", show=False),
        Binding("down", "history(1)", "History", show=False),
        Binding("tab", "complete", "Complete", show=False, priority=True),
    ]

    def __init__(self, *args, commands: list[str] | None = None, **kw):
        super().__init__(*args, **kw)
        self.commands = commands or COMMANDS
        self.history: list[str] = []
        self._pos = 0
        self._draft = ""

    def remember(self, text: str) -> None:
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
        self._pos = len(self.history)

    def action_history(self, step: int) -> None:
        if not self.history:
            return
        if self._pos == len(self.history):
            self._draft = self.value
        self._pos = max(0, min(len(self.history), self._pos + step))
        self.value = self.history[self._pos] if self._pos < len(self.history) else self._draft
        self.cursor_position = len(self.value)

    def completions(self) -> list[str]:
        v = self.value
        if not v.startswith("/") or " " in v:
            return []
        return [c for c in self.commands if c.startswith(v.lower())]

    def action_complete(self) -> None:
        matches = self.completions()
        if not matches:
            self.app.action_focus_next()
            return
        if self.value in matches and len(matches) > 1:      # cycle through candidates
            matches = matches[matches.index(self.value) + 1:] + matches[:matches.index(self.value) + 1]
        self.value = matches[0] + ("" if matches[0] in ("/new", "/help", "/memory", "/thinking", "/fast",
                                                         "/reason", "/deep", "/auto") else " ")
        self.cursor_position = len(self.value)


class UserMessage(Static):
    def __init__(self, text: str, name: str = "you"):
        super().__init__(f"[b $accent]{escape(name)}[/]\u00a0\u00a0{escape(text)}", classes="user-msg")


class AssistantMessage(Vertical):
    """One Atlas reply: meta line (model + route reason), collapsible thinking, research progress, Markdown."""

    def __init__(self, text: str = "", meta: str = "", expand_thinking: bool = False):
        super().__init__(classes="atlas-msg")
        self._initial, self._meta = text, meta
        self.expand_thinking = expand_thinking
        self.thinking_text = ""
        self.answer_text = text
        self.research = False
        self.tools: list[str] = []
        self.searches = 0
        self.report_chars = 0
        self.route: tuple[str, str, str] = ("", "", "")

    def compose(self) -> ComposeResult:
        yield Static(self._meta or "[dim]Atlas · routing…[/]", classes="meta")
        with Collapsible(title="Thinking", collapsed=not self.expand_thinking, classes="thinking"):
            yield Static("", classes="thinking-text")
        with Vertical(classes="progress"):
            yield Label("", classes="progress-label")
            yield ProgressBar(total=None, show_eta=False, classes="progress-bar")
        yield Markdown(self._initial, classes="answer")

    def on_mount(self) -> None:
        self.query_one(".thinking").display = False
        self.query_one(".progress").display = False

    # ----------------------------------------------------------- streaming
    def set_meta(self, text: str) -> None:
        self.query_one(".meta", Static).update(text)

    def add_thinking(self, chunk: str) -> None:
        self.thinking_text += chunk
        box = self.query_one(".thinking", Collapsible)
        box.display = True
        box.title = f"Thinking ({len(self.thinking_text):,} chars)"
        self.query_one(".thinking-text", Static).update(escape(self.thinking_text))

    def add_tokens(self, chunk: str):
        if self.research:                      # the full report goes to a file; just count it here
            self.report_chars += len(chunk)
            self._progress(f"writing report… {self.report_chars:,} chars")
            return None
        self.answer_text += chunk
        return self.query_one(".answer", Markdown).append(chunk)

    def _progress(self, label: str, total: float | None = None, progress: float | None = None,
                  advance: float = 0) -> None:
        box = self.query_one(".progress")
        box.display = True
        self.query_one(".progress-label", Label).update(escape(label))
        bar = self.query_one(".progress-bar", ProgressBar)
        if total is not None or progress is not None:
            bar.update(total=total, progress=progress)
        if advance:
            bar.advance(advance)

    def event(self, line: str) -> None:
        """Progress lines emitted by the agent / researcher."""
        s = line.strip()
        if s.startswith("route:"):
            parts = [p.strip() for p in s[6:].split("·")]
            if parts and parts[0] == "research":
                self.research = True
                self._progress("planning searches…")
            role, model = (parts + ["", ""])[:2]
            self.route = (role, model, " · ".join(parts[2:]))
            self.set_meta(meta_line(*self.route))
        elif s.startswith("tool:"):
            self.tools.append(s[5:].strip().split(" ")[0])
            self.set_meta(meta_line(*self.route, tools=self.tools) + "  [dim]running tool…[/]")
        elif s == "planning searches":
            self._progress("planning searches…")
        elif s.startswith("search:"):
            self.searches += 1
            self._progress(f"searching ({self.searches}): {s[7:].strip()}")
        elif m := re.match(r"reading (\d+) sources", s):
            self._progress(f"reading 0/{m.group(1)}", total=int(m.group(1)), progress=0)
        elif m := re.match(r"read \[(\d+)\]\s*(.*)", s):
            bar = self.query_one(".progress-bar", ProgressBar)
            done = int(bar.progress or 0) + 1
            self._progress(f"reading {done}/{int(bar.total or done)}: {m.group(2)}", advance=1)
        elif s.startswith("writing report"):
            self._progress(s + "…", total=None)
        elif s:
            self._progress(s)

    def finish(self, text: str, meta: str, *, replace: bool) -> None:
        self.set_meta(meta)
        if self.research:
            self.query_one(".progress-label", Label).update("done")
            self.query_one(".progress").display = False
        if replace or not self.answer_text.strip():
            self.answer_text = text
            self.query_one(".answer", Markdown).update(text)


def meta_line(role: str, model: str, reason: str = "", tools: list[str] | None = None) -> str:
    label = ROLE_LABEL.get(role, role or "atlas")
    bits = [f"[b $primary]Atlas[/] [reverse $secondary] {escape(label)} [/]"]
    if model:
        bits.append(f"[$text-muted]{escape(model)}[/]")
    if reason:
        bits.append(f"[dim]{escape(reason)}[/]")
    if tools:
        bits.append(f"[dim]⚙ {escape(', '.join(tools))}[/]")
    return "  ".join(bits)


class ConfirmScreen(ModalScreen[bool]):
    """y/N confirmation for tools that change files."""

    BINDINGS = [Binding("y", "answer(True)", "Allow"), Binding("n", "answer(False)", "Deny"),
                Binding("escape", "answer(False)", "Deny")]

    def __init__(self, name: str, args: dict[str, Any]):
        super().__init__()
        self.tool_name, self.args = name, args

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(f"[b $warning]Atlas wants to run[/] [b]{escape(self.tool_name)}[/]")
            yield Static(escape(json.dumps(self.args, indent=2, default=str)[:3000]), id="confirm-args")
            with Horizontal(id="confirm-buttons"):
                yield Button("Allow (y)", variant="warning", id="allow")
                yield Button("Deny (N)", variant="primary", id="deny")

    def on_mount(self) -> None:
        self.query_one("#deny", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "allow")

    def action_answer(self, ok: bool) -> None:
        self.dismiss(ok)


class ReportScreen(Screen):
    """Full-screen Markdown viewer for a saved research report."""

    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back"),
                Binding("t", "toggle_toc", "Contents")]

    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    def compose(self) -> ComposeResult:
        yield Label(f" [b]{escape(self.path.name)}[/]  [dim]{escape(str(self.path.parent))}[/]", id="report-title")
        try:
            text = self.path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            text = f"Could not open report: {e}"
        yield MarkdownViewer(text, show_table_of_contents=False, id="report-viewer")
        yield Footer()

    def action_toggle_toc(self) -> None:
        v = self.query_one(MarkdownViewer)
        v.show_table_of_contents = not v.show_table_of_contents
