"""Atlas terminal UI (Textual). Works over SSH: `atlas tui` (or just `atlas`)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.suggester import SuggestFromList
from textual.theme import Theme
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from ..agent import Atlas, Callbacks, Reply
from ..config import Config
from ..dates import parse_due
from ..memory import Memory
from ..ollama_client import ClientPool
from ..system import gpu_stats, ollama_status
from ..tools.builtin import build_registry
from .widgets import (
    COMMANDS,
    HELP_MD,
    AssistantMessage,
    ConfirmScreen,
    HistoryInput,
    ReportScreen,
    UserMessage,
    meta_line,
)

ATLAS_THEME = Theme(
    name="atlas", dark=True,
    primary="#5AA9E6", secondary="#7F7EFF", accent="#F4B860", warning="#F4B860", error="#FF6B6B",
    success="#6BCB77", foreground="#E6EDF3", background="#0D1117", surface="#151B23", panel="#1F2733",
)

MODES = [("auto", "auto"), ("fast", "fast"), ("reason", "reasoning"), ("deep", "deep")]
MODE_CMDS = {"/auto": "auto", "/fast": "fast", "/reason": "reasoning", "/deep": "deep"}

CSS = """
Screen { background: $background; }
#banner { display: none; height: auto; padding: 0 1; background: $error 35%; color: $text; text-style: bold; }
#banner.show { display: block; }
#body { height: 1fr; }
#main { width: 1fr; }
#chat { height: 1fr; padding: 0 1 1 1; scrollbar-size-vertical: 1; }
#welcome { color: $text-muted; padding: 1 2; }
.user-msg { margin: 1 0 0 0; padding: 0 1; background: $surface; border-left: thick $accent; height: auto; }
.atlas-msg { height: auto; margin: 1 0 0 0; padding: 0 0 0 1; border-left: thick $primary; }
.atlas-msg .meta { height: auto; }
.atlas-msg .answer { margin: 0; padding: 0; background: transparent; }
.atlas-msg .thinking { margin: 0; padding: 0; border: none; background: transparent; }
.atlas-msg .thinking Contents { padding: 0 0 0 2; }
.thinking-text { color: $text-muted; text-style: italic; }
.progress { height: auto; }
.progress-label { color: $accent; }
#prompt { margin: 0 1; border: tall $primary 60%; }
#prompt:focus { border: tall $primary; }
#side { width: 56; border-left: vkey $panel; background: $surface; }
#side.hidden { display: none; }
#side ContentSwitcher { height: 1fr; }
#side TabPane { height: 1fr; }
#side TabPane { padding: 0 1; }
#side DataTable { height: 1fr; }
#side ListView { height: 1fr; background: transparent; }
.row { height: auto; margin: 1 0 0 0; }
.row Input { width: 1fr; }
.row Button { min-width: 10; }
.hint { color: $text-muted; height: auto; }
#sys-ollama, #sys-models, #sys-gpu-msg { height: auto; margin: 0 0 1 0; }
#gpu-table { height: auto; margin: 0 0 1 0; }
#statusbar { height: 1; background: $panel; padding: 0 1; }
#statusbar Label { width: auto; padding: 0 1 0 0; }
#mode { width: 16; }
#status-text { width: 1fr; color: $text-muted; text-align: right; }
ConfirmScreen { align: center middle; }
#confirm-box { width: 72; height: auto; max-height: 80%; padding: 1 2; border: thick $warning; background: $surface; }
#confirm-args { margin: 1 0; padding: 0 1; background: $background; max-height: 20; overflow-y: auto; }
#confirm-buttons { height: auto; align-horizontal: right; }
#confirm-buttons Button { margin: 0 0 0 2; }
#report-title { height: 1; background: $panel; width: 1fr; }
"""


def _mb(x: float | None) -> str:
    return "?" if x is None else f"{x / 1024:.1f}G"


class AtlasApp(App):
    TITLE = "Atlas"
    CSS = CSS
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("f2", "toggle_side", "Panel", priority=True),
        Binding("ctrl+t", "cycle_mode", "Mode", priority=True),
        Binding("ctrl+n", "new_chat", "New chat", priority=True),
        Binding("ctrl+r", "show_tab('tab-reports')", "Reports", priority=True),
        Binding("ctrl+d", "show_tab('tab-deadlines')", "Deadlines", priority=True),
        Binding("ctrl+s", "show_tab('tab-system')", "System", priority=True),
        Binding("f1", "help", "Help", priority=True),
        Binding("escape", "focus_input", "Input", show=False),
    ]

    def __init__(self, cfg: Config, pool: ClientPool, memory: Memory, *, atlas: Atlas | None = None,
                 gpu_probe: Callable[[], list[dict[str, Any]] | None] | None = None,
                 status_probe: Callable[[], list[dict[str, Any]]] | None = None,
                 poll_seconds: float = 2.0, conversation_id: int | None = None):
        super().__init__()
        self.cfg, self.pool, self.memory = cfg, pool, memory
        self.atlas = atlas or Atlas(cfg, pool, memory, build_registry(memory, cfg.workspace, confirm=self.confirm_tool))
        self.gpu_probe = gpu_probe or gpu_stats
        self.status_probe = status_probe or (lambda: ollama_status(cfg, pool))
        self.poll_seconds = poll_seconds
        self.cid = conversation_id
        self.mode = "auto"
        self.busy = False
        self.expand_thinking = False
        self._reports: list[Path] = []
        self.last_status: list[dict[str, Any]] = []
        self.last_gpus: list[dict[str, Any]] | None = None

    # ------------------------------------------------------------------ layout
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, icon="◆")
        yield Static("", id="banner")
        with Horizontal(id="body"):
            with Vertical(id="main"):
                yield VerticalScroll(id="chat")
                yield HistoryInput(placeholder="Message Atlas…   (/ + Tab for commands, ↑ history)", id="prompt",
                                   commands=COMMANDS, suggester=SuggestFromList(COMMANDS))
            with TabbedContent(id="side", initial="tab-chats"):
                with TabPane("Chats", id="tab-chats"):
                    yield ListView(id="chats-list")
                    with Horizontal(classes="row"):
                        yield Button("New chat", id="chat-new", variant="primary")
                        yield Label("  Enter to resume", classes="hint")
                with TabPane("Deadlines", id="tab-deadlines"):
                    yield DataTable(id="dl-table", cursor_type="row", zebra_stripes=True)
                    with Horizontal(classes="row"):
                        yield Input(placeholder="title", id="dl-title")
                        yield Input(placeholder="due: fri 5pm", id="dl-due")
                    with Horizontal(classes="row"):
                        yield Button("Add", id="dl-add", variant="primary")
                        yield Button("Mark done", id="dl-done", variant="success")
                with TabPane("Memory", id="tab-memory"):
                    yield DataTable(id="mem-table", cursor_type="row", zebra_stripes=True)
                    with Horizontal(classes="row"):
                        yield Input(placeholder="remember…", id="mem-input")
                        yield Button("Save", id="mem-add", variant="primary")
                    with Horizontal(classes="row"):
                        yield Button("Forget selected", id="mem-forget", variant="error")
                with TabPane("Reports", id="tab-reports"):
                    yield ListView(id="reports-list")
                    yield Label("Enter opens a report · esc closes it", classes="hint")
                with TabPane("System", id="tab-system"):
                    yield Static("checking Ollama…", id="sys-ollama")
                    yield Static("", id="sys-gpu-msg")
                    yield DataTable(id="gpu-table", show_cursor=False)
                    yield Static("", id="sys-models")
        with Horizontal(id="statusbar"):
            yield Label("[b]Mode[/]")
            yield Select(MODES, value="auto", allow_blank=False, compact=True, id="mode")
            yield Static("", id="status-text")
        yield Footer()

    def on_mount(self) -> None:
        self.register_theme(ATLAS_THEME)
        self.theme = "atlas"
        call_me = self.atlas.call_me
        self.sub_title = f"{self.cfg.profile} · {call_me}"
        self.query_one("#dl-table", DataTable).add_columns("id", "due", "title")
        self.query_one("#mem-table", DataTable).add_columns("id", "fact")
        g = self.query_one("#gpu-table", DataTable)
        g.add_columns("gpu", "name", "util", "vram", "temp", "power")
        self.refresh_side()
        if self.cid is not None:
            self.load_conversation(self.cid)
        else:
            self.welcome()
        self.poll_system()
        if self.poll_seconds > 0:
            self.set_interval(self.poll_seconds, self.poll_system)
        self.query_one("#prompt").focus()
        self.update_status()

    def welcome(self) -> None:
        chat = self.query_one("#chat", VerticalScroll)
        chat.mount(Static(f"[b $primary]◆ Atlas[/]  ready, {escape(self.atlas.call_me)}. "
                          "Ask anything, or try [b]/research[/] <topic>.  [dim]F1 help · F2 panel[/]",
                          id="welcome"))

    def update_status(self) -> None:
        conv = f"chat #{self.cid}" if self.cid else "new chat"
        busy = "  [b $accent]● working[/]" if self.busy else ""
        model = self.cfg.model_for(self.mode) if self.mode != "auto" else "router"
        self.query_one("#status-text", Static).update(f"{conv} · {escape(model)}{busy}")

    # ------------------------------------------------------------------ side panel data
    def refresh_side(self) -> None:
        self.refresh_chats()
        self.refresh_deadlines()
        self.refresh_memory()
        self.refresh_reports()

    def refresh_chats(self) -> None:
        lv = self.query_one("#chats-list", ListView)
        lv.clear()
        for c in self.memory.recent_conversations(limit=50):
            title = (c.get("first") or c.get("title") or "(empty)").replace("\n", " ")
            mark = "▶ " if c["id"] == self.cid else ""
            lv.append(ListItem(Label(f"{mark}[b]#{c['id']}[/] {escape(title[:38])}\n"
                                     f"[dim]{escape(str(c.get('started_at', ''))[:16])} · {c.get('n', '?')} msgs[/]"),
                               name=f"conv-{c['id']}"))

    def refresh_deadlines(self) -> None:
        t = self.query_one("#dl-table", DataTable)
        t.clear()
        for d in self.memory.list_deadlines():
            t.add_row(str(d["id"]), d["due"][:16].replace("T", " "), d["title"], key=str(d["id"]))

    def refresh_memory(self) -> None:
        t = self.query_one("#mem-table", DataTable)
        t.clear()
        for f in self.memory.list_facts():
            t.add_row(str(f["id"]), f["text"], key=str(f["id"]))

    def refresh_reports(self) -> None:
        d = Path(self.cfg.reports_dir)
        self._reports = sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True) if d.exists() else []
        lv = self.query_one("#reports-list", ListView)
        lv.clear()
        if not self._reports:
            lv.append(ListItem(Label("[dim]No reports yet. Try /research <topic>[/]")))
        for p in self._reports:
            lv.append(ListItem(Label(f"{escape(p.stem)}\n[dim]{time.strftime('%Y-%m-%d %H:%M', time.localtime(p.stat().st_mtime))}"
                                     f" · {p.stat().st_size // 1024 + 1} KB[/]")))

    # ------------------------------------------------------------------ system polling
    @work(thread=True, exclusive=True, group="probe")
    def poll_system(self) -> None:
        gpus = self.gpu_probe()
        status = self.status_probe()
        self.call_from_thread(self.apply_system, gpus, status)

    def apply_system(self, gpus: list[dict[str, Any]] | None, status: list[dict[str, Any]]) -> None:
        self.last_gpus, self.last_status = gpus, status
        down = [s for s in status if not s["ok"]]
        banner = self.query_one("#banner", Static)
        if down:
            hosts = ", ".join(s["host"] for s in down)
            banner.update(f"⚠ Ollama not reachable at {escape(hosts)}. Start it: "
                          "sudo systemctl start ollama (or `ollama serve`), then `atlas doctor`.")
            banner.add_class("show")
        else:
            banner.remove_class("show")
        lines = []
        for s in status:
            dot = "[$success]●[/]" if s["ok"] else "[$error]●[/]"
            lines.append(f"{dot} {escape(s['host'])}  [dim]{escape(', '.join(s['roles']))}[/]")
        self.query_one("#sys-ollama", Static).update("[b]Ollama[/]\n" + "\n".join(lines))
        t = self.query_one("#gpu-table", DataTable)
        t.clear()
        msg = self.query_one("#sys-gpu-msg", Static)
        if gpus is None:
            msg.update("[b]GPUs[/]\n[dim]nvidia-smi not found or failed. Install the NVIDIA driver "
                       "(akmod-nvidia) to see GPU stats.[/]")
            t.display = False
        else:
            msg.update("[b]GPUs[/]  [dim]every %gs[/]" % self.poll_seconds if self.poll_seconds else "[b]GPUs[/]")
            t.display = True
            t.styles.height = len(gpus) + 1
            for g in gpus:
                t.add_row(g["index"], g["name"][:16], f"{g['util'] or 0:.0f}%",
                          f"{_mb(g['mem_used'])}/{_mb(g['mem_total'])}",
                          f"{g['temp'] or 0:.0f}°C", "" if g.get("power") is None else f"{g['power']:.0f}W")
        loaded = []
        for s in status:
            for m in s.get("loaded", []):
                vram = m.get("size_vram") or 0
                size = m.get("size") or vram or 1
                where = "GPU" if vram >= size else f"{100 * vram / size:.0f}% GPU"
                loaded.append(f"  {escape(m.get('name', '?'))}  [dim]{vram / 1e9:.1f} GB · {where} · "
                              f"{escape(s['host'].rsplit(':', 1)[-1])}[/]")
        self.query_one("#sys-models", Static).update(
            "[b]Loaded models[/]\n" + ("\n".join(loaded) if loaded else "[dim]  none loaded[/]"))

    # ------------------------------------------------------------------ tool confirmation (worker thread)
    def confirm_tool(self, name: str, args: dict[str, Any]) -> bool:
        """Called from the agent's worker thread: show a modal and block that thread until answered."""
        if threading.current_thread() is threading.main_thread():
            return False   # never block the UI thread; deny instead
        done = threading.Event()
        answer = {"ok": False}

        def show() -> None:
            def got(ok: bool | None) -> None:
                answer["ok"] = bool(ok)
                done.set()
            self.push_screen(ConfirmScreen(name, args), got)

        self.call_from_thread(show)
        done.wait()
        return answer["ok"]

    # ------------------------------------------------------------------ chat
    @on(Input.Submitted, "#prompt")
    def submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        prompt = self.query_one("#prompt", HistoryInput)
        prompt.value = ""
        if not text:
            return
        prompt.remember(text)
        self.handle_text(text)

    def handle_text(self, text: str) -> None:
        low = text.lower()
        if low in ("/exit", "/quit"):
            self.exit()
            return
        if low == "/new":
            self.action_new_chat()
            return
        if low == "/help":
            self.action_help()
            return
        if low == "/thinking":
            self.expand_thinking = not self.expand_thinking
            self.notify(f"Thinking {'expanded' if self.expand_thinking else 'collapsed'} by default")
            return
        if low in MODE_CMDS:
            self.set_mode(MODE_CMDS[low])
            return
        if self.busy:
            self.notify("Atlas is still working on the last message.", severity="warning")
            return
        if self.cid is None:
            self.cid = self.memory.new_conversation()
        chat = self.query_one("#chat", VerticalScroll)
        for w in chat.query("#welcome"):
            w.remove()
        block = AssistantMessage(expand_thinking=self.expand_thinking)
        chat.mount(UserMessage(text))
        chat.mount(block)
        chat.scroll_end(animate=False)
        self.busy = True
        self.update_status()
        self.ask_worker(text, block)

    @work(thread=True, group="ask")
    def ask_worker(self, text: str, block: AssistantMessage) -> None:
        buf = {"tok": [], "think": []}
        last = [0.0]
        lock = threading.Lock()

        def flush(force: bool = False) -> None:
            now = time.monotonic()
            if not force and now - last[0] < 0.06:
                return
            last[0] = now
            with lock:
                tok, think = "".join(buf["tok"]), "".join(buf["think"])
                buf["tok"].clear()
                buf["think"].clear()
            if think:
                self.call_from_thread(block.add_thinking, think)
            if tok:
                self.call_from_thread(self._append_answer, block, tok)

        def on_token(t: str) -> None:
            with lock:
                buf["tok"].append(t)
            flush()

        def on_thinking(t: str) -> None:
            with lock:
                buf["think"].append(t)
            flush()

        def on_event(line: str) -> None:
            flush(force=True)
            self.call_from_thread(block.event, line)

        force = None if self.mode == "auto" else self.mode
        try:
            reply = self.atlas.ask(self.cid, text, force_role=force,
                                   cb=Callbacks(on_token=on_token, on_thinking=on_thinking, on_event=on_event))
            flush(force=True)
            self.call_from_thread(self.finish_reply, block, reply)
        except Exception as e:  # noqa: BLE001 - show any failure in the chat instead of crashing
            flush(force=True)
            self.call_from_thread(self.fail_reply, block, e)

    async def _append_answer(self, block: AssistantMessage, chunk: str) -> None:
        aw = block.add_tokens(chunk)
        if aw is not None:
            await aw
        self.query_one("#chat", VerticalScroll).scroll_end(animate=False)

    def finish_reply(self, block: AssistantMessage, reply: Reply) -> None:
        block.finish(reply.text, meta_line(reply.role, reply.model, reply.route_reason, reply.tool_calls),
                     replace=bool(reply.report_path) or not reply.streamed)
        self.busy = False
        self.update_status()
        self.query_one("#chat", VerticalScroll).scroll_end(animate=False)
        self.refresh_chats()
        if reply.report_path:
            self.refresh_reports()
            self.notify(f"Report saved: {Path(reply.report_path).name}", title="Research done")
        if reply.role == "memory":
            self.refresh_memory()
        if reply.tool_calls:
            self.refresh_deadlines()
        self.set_timer(3, self.refresh_memory)   # background fact extraction lands a moment later

    def fail_reply(self, block: AssistantMessage, err: Exception) -> None:
        block.finish(f"**Error:** {err}\n\nIs Ollama running? Check the System tab (ctrl+s) or run `atlas doctor`.",
                     meta_line("error", "", err.__class__.__name__), replace=True)
        self.busy = False
        self.update_status()
        self.poll_system()

    # ------------------------------------------------------------------ conversations
    def load_conversation(self, cid: int) -> None:
        self.cid = cid
        chat = self.query_one("#chat", VerticalScroll)
        chat.remove_children()
        widgets = []
        for m in self.memory.messages(cid):
            if m["role"] == "user":
                widgets.append(UserMessage(m["content"]))
            elif m["role"] == "assistant":
                widgets.append(AssistantMessage(m["content"], meta_line(m.get("route") or "", m.get("model") or "",
                                                                      m.get("route_reason") or "")))
        if widgets:
            chat.mount_all(widgets)
        else:
            self.welcome()
        chat.scroll_end(animate=False)
        self.update_status()
        self.refresh_chats()

    @on(ListView.Selected, "#chats-list")
    def chat_selected(self, event: ListView.Selected) -> None:
        if event.item.name and event.item.name.startswith("conv-"):
            if self.busy:
                self.notify("Wait for the current answer first.", severity="warning")
                return
            self.load_conversation(int(event.item.name[5:]))
            self.query_one("#prompt").focus()

    def action_new_chat(self) -> None:
        if self.busy:
            self.notify("Wait for the current answer first.", severity="warning")
            return
        self.cid = None
        chat = self.query_one("#chat", VerticalScroll)
        chat.remove_children()
        self.welcome()
        self.update_status()
        self.refresh_chats()

    # ------------------------------------------------------------------ deadlines / memory / reports
    @on(Button.Pressed, "#chat-new")
    def _new_btn(self) -> None:
        self.action_new_chat()

    @on(Button.Pressed, "#dl-add")
    @on(Input.Submitted, "#dl-due")
    def add_deadline(self) -> None:
        title = self.query_one("#dl-title", Input).value.strip()
        due_text = self.query_one("#dl-due", Input).value.strip()
        if not title or not due_text:
            self.notify("Need a title and a due date (e.g. 'fri 5pm', '2026-12-04').", severity="warning")
            return
        try:
            due = parse_due(due_text)
        except ValueError as e:
            self.notify(str(e), severity="error")
            return
        did = self.memory.add_deadline(title, due)
        self.query_one("#dl-title", Input).value = ""
        self.query_one("#dl-due", Input).value = ""
        self.refresh_deadlines()
        self.notify(f"Deadline #{did} added")

    def _selected_key(self, table_id: str) -> int | None:
        t = self.query_one(table_id, DataTable)
        if not t.row_count:
            return None
        key = t.coordinate_to_cell_key(t.cursor_coordinate).row_key
        return int(key.value) if key and key.value else None

    @on(Button.Pressed, "#dl-done")
    def mark_done(self) -> None:
        did = self._selected_key("#dl-table")
        if did is None:
            self.notify("Select a deadline first.", severity="warning")
            return
        self.memory.complete_deadline(did)
        self.refresh_deadlines()
        self.notify(f"Deadline #{did} done ✓")

    @on(Button.Pressed, "#mem-add")
    @on(Input.Submitted, "#mem-input")
    def remember(self) -> None:
        inp = self.query_one("#mem-input", Input)
        text = inp.value.strip()
        if text:
            inp.value = ""
            self._remember_worker(text)

    @work(thread=True)
    def _remember_worker(self, text: str) -> None:
        fid = self.atlas.facts.remember(text, source="user")
        self.call_from_thread(self.notify, f"Remembered #{fid}" if fid else "Not saved (sensitive or duplicate)")
        self.call_from_thread(self.refresh_memory)

    @on(Button.Pressed, "#mem-forget")
    def forget(self) -> None:
        fid = self._selected_key("#mem-table")
        if fid is None:
            self.notify("Select a memory first.", severity="warning")
            return
        self.memory.forget_fact(fid)
        self.refresh_memory()
        self.notify(f"Forgot #{fid}")

    @on(ListView.Selected, "#reports-list")
    def open_report(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is not None and idx < len(self._reports):
            self.push_screen(ReportScreen(self._reports[idx]))

    # ------------------------------------------------------------------ mode + misc actions
    def set_mode(self, mode: str) -> None:
        self.mode = mode
        sel = self.query_one("#mode", Select)
        if sel.value != mode:
            sel.value = mode
        self.update_status()

    @on(Select.Changed, "#mode")
    def mode_changed(self, event: Select.Changed) -> None:
        if event.value is not Select.BLANK:
            self.mode = str(event.value)
            self.update_status()

    def action_cycle_mode(self) -> None:
        order = [v for _, v in MODES]
        self.set_mode(order[(order.index(self.mode) + 1) % len(order)])
        self.notify(f"Mode: {self.mode}", timeout=1.5)

    def action_toggle_side(self) -> None:
        self.query_one("#side").toggle_class("hidden")

    def action_show_tab(self, tab: str) -> None:
        side = self.query_one("#side", TabbedContent)
        side.remove_class("hidden")
        side.active = tab
        if tab == "tab-reports":
            self.refresh_reports()

    def action_focus_input(self) -> None:
        self.query_one("#prompt").focus()

    def action_help(self) -> None:
        chat = self.query_one("#chat", VerticalScroll)
        chat.mount(AssistantMessage(HELP_MD, meta_line("help", "", "")))
        chat.scroll_end(animate=False)

    def on_unmount(self) -> None:
        try:
            self.atlas.wait_background(timeout=20)
        except Exception:  # noqa: BLE001
            pass


def run_tui(cfg: Config, pool: ClientPool, memory: Memory, conversation_id: int | None = None) -> None:
    AtlasApp(cfg, pool, memory, conversation_id=conversation_id).run()
