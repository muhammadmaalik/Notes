"""TUI tests with Textual's App.run_test / Pilot (Ollama, nvidia-smi and the network are all mocked)."""

import asyncio
import threading

from conftest import FakeOllama
from typer.testing import CliRunner

from atlas.agent import Callbacks, Reply
from atlas.system import gpu_stats, ollama_status
from atlas.tui import AtlasApp
from atlas.tui.widgets import AssistantMessage, ConfirmScreen, HistoryInput, ReportScreen

GPUS = [
    {"index": "0", "name": "RTX 5070 Ti", "util": 63.0, "mem_used": 11800.0, "mem_total": 16303.0, "temp": 61.0,
     "power": 210.0},
    {"index": "1", "name": "RTX 3060", "util": 12.0, "mem_used": 4100.0, "mem_total": 12288.0, "temp": 48.0,
     "power": 60.0},
]
UP = [{"host": "http://127.0.0.1:11434", "roles": ["fast", "reasoning"], "ok": True, "error": "",
       "loaded": [{"name": "gpt-oss:20b", "size": 14e9, "size_vram": 14e9}]}]
DOWN = [{"host": "http://127.0.0.1:11434", "roles": ["fast"], "ok": False, "error": "refused", "loaded": []}]


def make_app(cfg, mem, fake=None, gpus=GPUS, status=UP, **kw):
    fake = fake or FakeOllama()
    return AtlasApp(cfg, fake.pool(cfg), mem, gpu_probe=lambda: gpus, status_probe=lambda: status,
                    poll_seconds=0, **kw)


def run(coro):
    return asyncio.run(coro)


async def settle(app, pilot):
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause(0.05)


def test_boots_with_system_tab(cfg, mem):
    async def go():
        app = make_app(cfg, mem)
        async with app.run_test(size=(140, 40)) as pilot:
            await settle(app, pilot)
            assert app.title == "Atlas" and app.theme == "atlas"
            assert "show" not in app.query_one("#banner").classes
            assert app.query_one("#gpu-table").row_count == 2
            assert "gpt-oss:20b" in str(app.query_one("#sys-models").render())
    run(go())


def test_degrades_without_gpu_and_ollama(cfg, mem):
    async def go():
        app = make_app(cfg, mem, gpus=None, status=DOWN)
        async with app.run_test(size=(140, 40)) as pilot:
            await settle(app, pilot)
            assert "show" in app.query_one("#banner").classes
            assert "not reachable" in str(app.query_one("#banner").render())
            assert "nvidia-smi not found" in str(app.query_one("#sys-gpu-msg").render())
            assert app.query_one("#gpu-table").display is False
    run(go())


def test_chat_streams_with_thinking_and_header(cfg, mem):
    fake = FakeOllama(responder=lambda body: {"content": "**Hello** Maalik, here is the plan.",
                                              "thinking": "user wants a plan"})

    async def go():
        app = make_app(cfg, mem, fake)
        async with app.run_test(size=(140, 40)) as pilot:
            app.set_mode("reasoning")
            await pilot.click("#prompt")
            await pilot.press(*"plan my week")
            await pilot.press("enter")
            await settle(app, pilot)
            block = app.query(AssistantMessage).last()
            assert "Hello" in block.answer_text
            assert block.thinking_text == "user wants a plan"
            assert block.query_one(".thinking").display is True
            meta = str(block.query_one(".meta").render())
            assert "reason" in meta and cfg.model_for("reasoning") in meta
            assert app.cid is not None and not app.busy
            assert [m["role"] for m in mem.messages(app.cid)] == ["user", "assistant"]
    run(go())


def test_autocomplete_history_and_modes(cfg, mem):
    async def go():
        app = make_app(cfg, mem)
        async with app.run_test(size=(140, 40)) as pilot:
            inp = app.query_one("#prompt", HistoryInput)
            inp.focus()
            await pilot.press("/", "r", "e", "s", "tab")
            assert inp.value == "/research "
            inp.value = "/re"
            await pilot.press("tab")
            assert inp.value in ("/reason", "/research ", "/remember ")
            inp.value = "/deep"
            await pilot.press("enter")
            assert app.mode == "deep"
            await pilot.press("ctrl+t")
            assert app.mode == "auto"
            await pilot.press("up")
            assert inp.value == "/deep"
            await pilot.press("down")
            assert inp.value == ""
    run(go())


def test_deadlines_memory_panel(cfg, mem):
    mem.add_fact("Maalik leads FEA for Stony Brook Robotics", None, source="user")

    async def go():
        app = make_app(cfg, mem)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press("ctrl+d")
            app.query_one("#dl-title").value = "PHY 251 lab report"
            app.query_one("#dl-due").value = "2026-12-04 17:00"
            await pilot.click("#dl-add")
            await pilot.pause()
            assert [d["title"] for d in mem.list_deadlines()] == ["PHY 251 lab report"]
            await pilot.click("#dl-done")
            await pilot.pause()
            assert mem.list_deadlines() == []
            app.query_one("#side").active = "tab-memory"
            await pilot.pause()
            assert app.query_one("#mem-table").row_count == 1
            app.query_one("#mem-forget").press()      # (toasts can cover the button for a mouse click)
            await pilot.pause()
            assert mem.list_facts() == []
    run(go())


def test_reports_open_in_viewer(cfg, mem):
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    (cfg.reports_dir / "2026-11-21-voyager-1.md").write_text("# Voyager 1\n\nLaunched 1977.\n")

    async def go():
        app = make_app(cfg, mem)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press("ctrl+r")
            await pilot.pause()
            lv = app.query_one("#reports-list")
            lv.focus()
            lv.index = 0
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, ReportScreen)
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, ReportScreen)
    run(go())


def test_resume_conversation(cfg, mem):
    cid = mem.new_conversation()
    mem.add_message(cid, "user", "what is a qubit?")
    mem.add_message(cid, "assistant", "A two-level quantum system.", model="qwen3.5:9b", route_reason="heuristic")

    async def go():
        app = make_app(cfg, mem)
        async with app.run_test(size=(140, 40)) as pilot:
            assert app.cid is None
            lv = app.query_one("#chats-list")
            lv.focus()
            lv.index = 0
            await pilot.press("enter")
            await pilot.pause()
            assert app.cid == cid
            blocks = list(app.query(AssistantMessage))
            assert blocks and "two-level" in blocks[-1].answer_text
            await pilot.press("ctrl+n")
            assert app.cid is None
    run(go())


def test_tool_confirmation_modal(cfg, mem):
    async def go():
        app = make_app(cfg, mem)
        async with app.run_test(size=(140, 40)) as pilot:
            results = []
            t = threading.Thread(target=lambda: results.append(app.confirm_tool("write_file", {"path": "a.txt"})))
            t.start()
            for _ in range(50):
                await pilot.pause(0.02)
                if isinstance(app.screen, ConfirmScreen):
                    break
            assert isinstance(app.screen, ConfirmScreen)
            await pilot.press("y")
            await pilot.pause()
            t.join(2)
            t2 = threading.Thread(target=lambda: results.append(app.confirm_tool("write_file", {"path": "b"})))
            t2.start()
            for _ in range(50):
                await pilot.pause(0.02)
                if isinstance(app.screen, ConfirmScreen):
                    break
            await pilot.press("enter")          # focused button is Deny
            await pilot.pause()
            t2.join(2)
            assert results == [True, False]
            assert app.confirm_tool("x", {}) is False   # main thread never blocks
    run(go())


class StubAtlas:
    """Agent stand-in that emits research progress like the real pipeline."""
    call_me, tz = "Maalik", "America/New_York"

    def __init__(self, gate):
        self.gate, self.seen = gate, []

    def ask(self, cid, text, force_role=None, cb: Callbacks | None = None, background=True):
        cb.on_event("route: research · gpt-oss:20b · depth 1 · command")
        cb.on_event("planning searches")
        cb.on_event("search: voyager 1 mission")
        cb.on_event("reading 8 sources")
        for i in range(1, 4):
            cb.on_event(f"  read [{i}] Source {i}")
        self.gate.wait(5)                      # UI must stay responsive while we're "working"
        cb.on_event("writing report from 3 sources")
        cb.on_token("# Voyager report body")
        return Reply("Summary of Voyager.\n\nSaved: data/reports/x.md", "research", "gpt-oss:20b", "command",
                     report_path="/tmp/x.md", streamed=True)

    def wait_background(self, timeout=60):
        pass


def test_research_progress_without_freezing(cfg, mem):
    gate = threading.Event()

    async def go():
        app = make_app(cfg, mem, atlas=StubAtlas(gate))
        async with app.run_test(size=(140, 40)) as pilot:
            app.handle_text("/research voyager 1")
            block = app.query(AssistantMessage).last()
            for _ in range(100):
                await pilot.pause(0.02)
                if "reading 3/8" in str(block.query_one(".progress-label").render()):
                    break
            assert "reading 3/8" in str(block.query_one(".progress-label").render())
            assert app.busy
            await pilot.press("ctrl+t")            # UI still handles keys mid-research
            assert app.mode == "fast"
            gate.set()
            await settle(app, pilot)
            assert not app.busy
            assert block.answer_text.startswith("Summary of Voyager")
            assert "report body" not in block.answer_text     # full report goes to the file, not the chat
    run(go())


def test_system_probes(cfg, monkeypatch):
    monkeypatch.setattr("atlas.system.shutil.which", lambda _x: None)
    assert gpu_stats() is None

    class R:
        stdout = "0, NVIDIA GeForce RTX 5070 Ti, 55, 9000, 16303, 60, 200.5\n"
    monkeypatch.setattr("atlas.system.shutil.which", lambda _x: "/usr/bin/nvidia-smi")
    monkeypatch.setattr("atlas.system.subprocess.run", lambda *a, **k: R())
    g = gpu_stats()
    assert g[0]["name"] == "RTX 5070 Ti" and g[0]["util"] == 55 and g[0]["power"] == 200.5
    fake = FakeOllama()
    fake.loaded = [{"name": "qwen3.5:4b", "size": 3e9, "size_vram": 3e9}]
    st = ollama_status(cfg, fake.pool(cfg))
    assert st[0]["ok"] and st[0]["loaded"][0]["name"] == "qwen3.5:4b"


def test_cli_no_args_launches_tui(monkeypatch):
    from atlas.cli import app as cli_app
    called = {}
    monkeypatch.setattr("atlas.tui.run_tui", lambda cfg, pool, mem, conversation_id=None: called.update(c=cfg))
    r = CliRunner().invoke(cli_app, [])
    assert r.exit_code == 0, r.output
    assert "c" in called
    r = CliRunner().invoke(cli_app, ["tui", "--help"])
    assert r.exit_code == 0 and "terminal UI" in r.output
