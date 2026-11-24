"""`atlas` command line: chat, ask, research, memory, deadlines, doctor, history, serve."""

from __future__ import annotations

import json
import sys
from typing import Any

import os
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule
from rich.table import Table

from .agent import Atlas, Callbacks, Reply
from .config import load_config
from .dates import parse_due
from .facts import FactMemory
from .memory import Memory
from .ollama_client import ClientPool, OllamaError
from .tools.builtin import build_registry

app = typer.Typer(help="Atlas: local multi-model assistant. Run with no command to open the TUI.",
                  invoke_without_command=True)
deadlines_app = typer.Typer(help="Track deadlines and tasks", no_args_is_help=True)
memory_app = typer.Typer(help="Long-term memory about you", no_args_is_help=True)
app.add_typer(deadlines_app, name="deadlines")
app.add_typer(memory_app, name="memory")
console = Console()

ProfileOpt = typer.Option(None, "--profile", "-p", help="Config profile (laptop, homepc). Default: $ATLAS_PROFILE or laptop")

HELP = """[dim]Commands:
  /fast /reason /deep /auto     switch mode for the session (or prefix one message: /deep <msg>)
  /research <topic>             multi-source research report (also triggered by "research ..." / "look into ...")
  /remember <fact>  /forget <id|text>  /memory
  /thinking                     toggle showing the model's reasoning stream
  /new  /help  /exit[/]"""


def confirm_tty(name: str, args: dict[str, Any]) -> bool:
    console.print(f"\n[bold yellow]Atlas wants to run[/] [bold]{name}[/] with:")
    console.print_json(json.dumps(args, default=str))
    return typer.confirm("Allow?", default=False)


@app.callback()
def _main(ctx: typer.Context,
          profile: str | None = ProfileOpt,
          resume: int | None = typer.Option(None, "--resume", "-r", help="Open conversation #id"),
          last: bool = typer.Option(False, "--last", help="Resume the most recent conversation")) -> None:
    """With no subcommand, open the terminal UI. `atlas --profile homepc` works before or after a command."""
    if profile:
        os.environ["ATLAS_PROFILE"] = profile  # subcommands without their own --profile inherit this
    if ctx.invoked_subcommand is None:
        tui(profile=profile, resume=resume, last=last)


@app.command()
def tui(profile: str | None = ProfileOpt,
        resume: int | None = typer.Option(None, "--resume", "-r", help="Open conversation #id"),
        last: bool = typer.Option(False, "--last", help="Resume the most recent conversation")) -> None:
    """Full-screen terminal UI (Textual): chat, deadlines, memory, reports, GPU/Ollama status."""
    from .tui import run_tui  # imported lazily so the plain CLI stays fast

    cfg = load_config(profile)
    pool = ClientPool(cfg)
    mem = Memory(cfg.db_path)
    if last and resume is None:
        recent = mem.recent_conversations(limit=1)
        resume = recent[0]["id"] if recent else None
    run_tui(cfg, pool, mem, conversation_id=resume)


def _build(profile: str | None):
    cfg = load_config(profile)
    pool = ClientPool(cfg)
    mem = Memory(cfg.db_path)
    atlas = Atlas(cfg, pool, mem, build_registry(mem, cfg.workspace, confirm=confirm_tty))
    return cfg, pool, mem, atlas


class StreamPrinter:
    """Prints tokens as they arrive; shows thinking either live (dim) or as a compact progress line."""

    def __init__(self, show_thinking: bool = False, verbose: bool = False):
        self.show_thinking, self.verbose = show_thinking, verbose
        self.thinking_chars = 0
        self.in_thinking = False
        self.dimmed = False
        self.wrote_answer = False

    def _end_thinking(self) -> None:
        if self.in_thinking:
            sys.stdout.write("\n" if self.show_thinking else f" ({self.thinking_chars} chars)\n")
            sys.stdout.flush()
            self.in_thinking = False

    def thinking(self, chunk: str) -> None:
        if not self.in_thinking:
            self.in_thinking = True
            self.dimmed = True
            sys.stdout.write("\033[2m· thinking" + (":\n" if self.show_thinking else ""))
        self.thinking_chars += len(chunk)
        if self.show_thinking:
            sys.stdout.write(chunk)
        elif self.thinking_chars // 400 != (self.thinking_chars - len(chunk)) // 400:
            sys.stdout.write(".")
        sys.stdout.flush()

    def token(self, chunk: str) -> None:
        if self.in_thinking:
            self._end_thinking()
        if self.dimmed:
            sys.stdout.write("\033[0m")
            self.dimmed = False
        self.wrote_answer = True
        sys.stdout.write(chunk)
        sys.stdout.flush()

    def event(self, line: str) -> None:
        if line.startswith("route:") and not self.verbose:
            return
        self._end_thinking()
        console.print(f"[dim]{line}[/]")

    def callbacks(self) -> Callbacks:
        return Callbacks(on_token=self.token, on_thinking=self.thinking, on_event=self.event)

    def finish(self, r: Reply) -> None:
        self._end_thinking()
        if self.dimmed:
            sys.stdout.write("\033[0m")
            self.dimmed = False
        if self.wrote_answer:
            sys.stdout.write("\n")
        if r.role == "research":
            console.print(Rule(style="dim"))
            console.print(Markdown(r.text))
        elif not r.streamed:
            console.print(Markdown(r.text or "_(empty reply)_"))
        tag = f"{r.role}" + (f" · {r.model}" if r.model else "")
        if r.tool_calls:
            tag += f" · tools: {', '.join(r.tool_calls)}"
        if self.verbose:
            tag += f" · {r.route_reason}"
        console.print(f"[dim]{tag}[/]")


def _run(atlas: Atlas, cid: int, text: str, role: str | None, show_thinking: bool, verbose: bool) -> None:
    sp = StreamPrinter(show_thinking, verbose)
    try:
        r = atlas.ask(cid, text, force_role=role, cb=sp.callbacks())
    except OllamaError as e:
        sp._end_thinking()
        console.print(f"\n[red]{e}[/]")
        return
    except RuntimeError as e:
        sp._end_thinking()
        console.print(f"\n[red]{e}[/]")
        return
    sp.finish(r)


@app.command()
def chat(profile: str | None = ProfileOpt,
         role: str | None = typer.Option(None, help="Start in fast | reasoning | deep mode"),
         thinking: bool = typer.Option(False, "--thinking", help="Stream the model's reasoning"),
         verbose: bool = typer.Option(False, "-v", help="Show routing decisions")) -> None:
    """Interactive chat with streaming output."""
    cfg, _pool, mem, atlas = _build(profile)
    cid = mem.new_conversation()
    console.print(f"[bold]Atlas[/] · {cfg.profile} · hi {atlas.call_me} · fast={cfg.models.get('fast')} · "
                  f"reasoning={cfg.models.get('reasoning')} · deep={cfg.models.get('deep', '-')}")
    console.print("[dim]/help for commands[/]")
    modes = {"/fast": "fast", "/reason": "reasoning", "/deep": "deep", "/auto": None}
    try:
        while True:
            try:
                text = console.input("[bold green]you>[/] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print()
                break
            if not text:
                continue
            low = text.lower()
            if low in ("/exit", "/quit"):
                break
            if low == "/help":
                console.print(HELP)
                continue
            if low in modes:
                role = modes[low]
                console.print(f"[dim]mode: {role or 'auto'}[/]")
                continue
            if low == "/thinking":
                thinking = not thinking
                console.print(f"[dim]show thinking: {'on' if thinking else 'off'}[/]")
                continue
            if low == "/new":
                cid = mem.new_conversation()
                console.print("[dim]new conversation[/]")
                continue
            _run(atlas, cid, text, role, thinking, verbose)
    finally:
        with console.status("saving memories..."):
            atlas.wait_background(30)


@app.command()
def ask(question: str, profile: str | None = ProfileOpt,
        role: str | None = typer.Option(None, help="fast | reasoning | deep | research"),
        thinking: bool = typer.Option(False, "--thinking"),
        verbose: bool = typer.Option(False, "-v")) -> None:
    """One-shot question (streams)."""
    _cfg, _pool, mem, atlas = _build(profile)
    _run(atlas, mem.new_conversation(), question, role, thinking, verbose)
    atlas.wait_background(30)


@app.command()
def research(topic: str, profile: str | None = ProfileOpt,
             docx: bool = typer.Option(False, "--docx", help="Also export .docx (pandoc)"),
             pdf: bool = typer.Option(False, "--pdf", help="Also export .pdf (pandoc + typst/LaTeX)"),
             verbose: bool = typer.Option(False, "-v")) -> None:
    """Deep research: plan searches, read sources, write a cited report to data/reports/."""
    cfg, _pool, mem, atlas = _build(profile)
    fmts = list(cfg.research.get("formats", ["md"]))
    fmts += [f for f, on in (("docx", docx), ("pdf", pdf)) if on and f not in fmts]
    cfg.research["formats"] = fmts
    _run(atlas, mem.new_conversation(), f"/research {topic}", None, False, verbose)
    atlas.wait_background(30)


@app.command()
def doctor(profile: str | None = ProfileOpt) -> None:
    """Check each Ollama host is reachable and has its models."""
    cfg = load_config(profile)
    pool = ClientPool(cfg)
    console.print(f"profile: [cyan]{cfg.profile}[/]  db: {cfg.db_path}  user profile: {cfg.profile_path}")
    bad = False
    cache: dict[str, set[str] | None] = {}
    for role_name, model in cfg.models.items():
        host = cfg.host_for(role_name)
        if host not in cache:
            try:
                cache[host] = set(pool.get(host).list_models())
                console.print(f"[green]✓ Ollama reachable at {host}[/]")
            except OllamaError as e:
                cache[host] = None
                console.print(f"[red]✗ {e}[/]")
        installed = cache[host]
        have = installed is not None and (model in installed or f"{model}:latest" in installed)
        console.print(f"  {'[green]✓' if have else '[red]✗'} {role_name:<10} {model:<24} @ {host}[/]")
        bad = bad or not have
    if bad:
        console.print("Fix: start the Ollama instance(s), then `ollama pull <model>` "
                      "(for a pinned instance: OLLAMA_HOST=127.0.0.1:11435 ollama pull <model>).")
        raise typer.Exit(1)


@app.command()
def history(profile: str | None = ProfileOpt, limit: int = 10) -> None:
    """Show recent conversations."""
    mem = Memory(load_config(profile).db_path)
    t = Table("id", "started", "msgs", "first message")
    for c in mem.recent_conversations(limit):
        t.add_row(str(c["id"]), c["started_at"], str(c["n"]), (c["first"] or "")[:60])
    console.print(t)


@app.command()
def serve(profile: str | None = ProfileOpt, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the FastAPI gateway (localhost only by default)."""
    import uvicorn

    from .gateway import create_app
    uvicorn.run(create_app(load_config(profile)), host=host, port=port)


@app.command()
def voice(profile: str | None = ProfileOpt) -> None:
    """Voice mode (phase 2 placeholder)."""
    from .voice import get_voice
    v = get_voice(load_config(profile))
    if not getattr(v, "enabled", False):
        console.print("Voice is phase 2 (wake word + Parakeet STT + Kokoro TTS). The hook is in src/atlas/voice.py.")


# ---------------------------------------------------------------- memory
def _facts(profile: str | None) -> FactMemory:
    cfg = load_config(profile)
    return FactMemory(cfg, ClientPool(cfg), Memory(cfg.db_path))


@memory_app.command("list")
def memory_list(profile: str | None = ProfileOpt) -> None:
    """Show what Atlas remembers about you."""
    mem = Memory(load_config(profile).db_path)
    facts = mem.list_facts()
    if not facts:
        console.print("No memories yet. Chat a bit, or: atlas memory add \"I prefer SI units\"")
        return
    t = Table("id", "fact", "source", "saved")
    for f in facts:
        t.add_row(str(f["id"]), f["text"], f["source"], f["created_at"])
    console.print(t)


@memory_app.command("add")
def memory_add(fact: str, profile: str | None = ProfileOpt) -> None:
    """Teach Atlas a fact about you."""
    fid = _facts(profile).remember(fact, source="user")
    console.print(f"[green]Saved #{fid}[/]" if fid else "[yellow]Already known (or not allowed).[/]")


@memory_app.command("forget")
def memory_forget(what: str, profile: str | None = ProfileOpt) -> None:
    """Forget a memory by id or matching text."""
    gone = _facts(profile).forget(what)
    if gone:
        for g in gone:
            console.print(f"[green]Forgot:[/] {g}")
    else:
        console.print("[red]No matching memory.[/]")
        raise typer.Exit(1)


# ---------------------------------------------------------------- deadlines
@deadlines_app.command("add")
def deadlines_add(title: str, due: str = typer.Option(..., "--due", "-d", help="YYYY-MM-DD [HH:MM], today, tomorrow, +3d, friday"),
                  course: str | None = typer.Option(None, "--course", "-c"),
                  profile: str | None = ProfileOpt) -> None:
    """Add a deadline (you typed it, so no confirmation needed)."""
    mem = Memory(load_config(profile).db_path)
    try:
        due_norm = parse_due(due)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)
    new_id = mem.add_deadline(title, due_norm, course)
    console.print(f"[green]Added #{new_id}[/] {title} · due {due_norm}" + (f" · {course}" if course else ""))


@deadlines_app.command("list")
def deadlines_list(all: bool = typer.Option(False, "--all", help="Include completed"),
                   profile: str | None = ProfileOpt) -> None:
    """List deadlines, soonest first."""
    mem = Memory(load_config(profile).db_path)
    rows = mem.list_deadlines(include_done=all)
    if not rows:
        console.print("No deadlines. Add one: atlas deadlines add \"PHY 251 lab report\" --due friday")
        return
    t = Table("id", "due", "title", "course", "done")
    for r in rows:
        t.add_row(str(r["id"]), r["due"], r["title"], r["course"] or "", "✓" if r["done"] else "")
    console.print(t)


@deadlines_app.command("done")
def deadlines_done(deadline_id: int, profile: str | None = ProfileOpt) -> None:
    """Mark a deadline as done (it is kept, never deleted)."""
    mem = Memory(load_config(profile).db_path)
    if mem.complete_deadline(deadline_id):
        console.print(f"[green]Marked #{deadline_id} done[/]")
    else:
        console.print(f"[red]No deadline #{deadline_id}[/]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
