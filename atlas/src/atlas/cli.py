"""`atlas` command line: chat, ask, deadlines, doctor, history, serve."""

from __future__ import annotations

import json
from typing import Any, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from .agent import Atlas
from .config import load_config
from .dates import parse_due
from .memory import Memory
from .ollama_client import OllamaClient, OllamaError
from .tools.builtin import build_registry

app = typer.Typer(help="Atlas v0: local multi-model assistant", no_args_is_help=True)
deadlines_app = typer.Typer(help="Track deadlines and tasks", no_args_is_help=True)
app.add_typer(deadlines_app, name="deadlines")
console = Console()

ProfileOpt = typer.Option(None, "--profile", "-p", help="Config profile (laptop, homepc). Default: $ATLAS_PROFILE or laptop")


def confirm_tty(name: str, args: dict[str, Any]) -> bool:
    console.print(f"\n[bold yellow]Atlas wants to run[/] [bold]{name}[/] with:")
    console.print_json(json.dumps(args, default=str))
    return typer.confirm("Allow?", default=False)


def _build(profile: str | None):
    cfg = load_config(profile)
    client = OllamaClient(cfg.ollama_host, cfg.timeout_s, cfg.keep_alive)
    mem = Memory(cfg.db_path)
    atlas = Atlas(cfg, client, mem, build_registry(mem, cfg.workspace, confirm=confirm_tty))
    return cfg, client, mem, atlas


def _print_reply(r, verbose: bool) -> None:
    tag = f"[dim]{r.role} · {r.model}" + (f" · tools: {', '.join(r.tool_calls)}" if r.tool_calls else "")
    if verbose:
        tag += f" · {r.route_reason}"
    console.print(tag + "[/]")
    console.print(Markdown(r.text or "_(empty reply)_"))


@app.command()
def chat(profile: Optional[str] = ProfileOpt,
         role: Optional[str] = typer.Option(None, help="Force 'fast' or 'reasoning' for the whole session"),
         verbose: bool = typer.Option(False, "-v", help="Show routing reasons")) -> None:
    """Interactive chat. Commands: /fast, /reason, /auto, /new, /exit."""
    cfg, _client, mem, atlas = _build(profile)
    cid = mem.new_conversation()
    console.print(f"[bold]Atlas[/] · profile [cyan]{cfg.profile}[/] · fast={cfg.models.get('fast')} · reasoning={cfg.models.get('reasoning')}")
    console.print("[dim]/fast /reason /auto to switch, /new for a fresh conversation, /exit to quit[/]")
    while True:
        try:
            text = console.input("[bold green]you>[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if not text:
            continue
        if text in ("/exit", "/quit"):
            break
        if text in ("/fast", "/reason", "/auto"):
            role = {"/fast": "fast", "/reason": "reasoning", "/auto": None}[text]
            console.print(f"[dim]mode: {role or 'auto'}[/]")
            continue
        if text == "/new":
            cid = mem.new_conversation()
            console.print("[dim]new conversation[/]")
            continue
        try:
            with console.status("thinking..."):
                r = atlas.ask(cid, text, force_role=role)
        except OllamaError as e:
            console.print(f"[red]{e}[/]")
            continue
        _print_reply(r, verbose)


@app.command()
def ask(question: str, profile: Optional[str] = ProfileOpt,
        role: Optional[str] = typer.Option(None, help="fast | reasoning"),
        verbose: bool = typer.Option(False, "-v")) -> None:
    """One-shot question."""
    _cfg, _client, mem, atlas = _build(profile)
    try:
        r = atlas.ask(mem.new_conversation(), question, force_role=role)
    except OllamaError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)
    _print_reply(r, verbose)


@app.command()
def doctor(profile: Optional[str] = ProfileOpt) -> None:
    """Check Ollama is reachable and the profile's models are pulled."""
    cfg = load_config(profile)
    client = OllamaClient(cfg.ollama_host, 10)
    console.print(f"profile: [cyan]{cfg.profile}[/]  ollama: {cfg.ollama_host}  db: {cfg.db_path}")
    try:
        installed = set(client.list_models())
    except OllamaError as e:
        console.print(f"[red]✗ {e}[/]")
        raise typer.Exit(1)
    console.print("[green]✓ Ollama reachable[/]")
    missing = []
    for role_name, model in cfg.models.items():
        have = model in installed or f"{model}:latest" in installed
        console.print(f"  {'[green]✓' if have else '[red]✗'} {role_name:<10} {model}[/]")
        if not have:
            missing.append(model)
    if missing:
        console.print("Pull missing models:\n  " + "\n  ".join(f"ollama pull {m}" for m in missing))
        raise typer.Exit(1)


@app.command()
def history(profile: Optional[str] = ProfileOpt, limit: int = 10) -> None:
    """Show recent conversations."""
    mem = Memory(load_config(profile).db_path)
    t = Table("id", "started", "msgs", "first message")
    for c in mem.recent_conversations(limit):
        t.add_row(str(c["id"]), c["started_at"], str(c["n"]), (c["first"] or "")[:60])
    console.print(t)


@app.command()
def serve(profile: Optional[str] = ProfileOpt, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the FastAPI gateway (localhost only by default)."""
    import uvicorn

    from .gateway import create_app
    uvicorn.run(create_app(load_config(profile)), host=host, port=port)


@deadlines_app.command("add")
def deadlines_add(title: str, due: str = typer.Option(..., "--due", "-d", help="YYYY-MM-DD [HH:MM], today, tomorrow, +3d, friday"),
                  course: Optional[str] = typer.Option(None, "--course", "-c"),
                  profile: Optional[str] = ProfileOpt) -> None:
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
                   profile: Optional[str] = ProfileOpt) -> None:
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
def deadlines_done(deadline_id: int, profile: Optional[str] = ProfileOpt) -> None:
    """Mark a deadline as done (it is kept, never deleted)."""
    mem = Memory(load_config(profile).db_path)
    if mem.complete_deadline(deadline_id):
        console.print(f"[green]Marked #{deadline_id} done[/]")
    else:
        console.print(f"[red]No deadline #{deadline_id}[/]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
