import pytest

from atlas.tools.builtin import build_registry
from atlas.tools.registry import PermissionDenied, Tier, Tool, ToolRegistry


def test_memory_conversations(mem):
    cid = mem.new_conversation()
    mem.add_message(cid, "user", "hello")
    mem.add_message(cid, "assistant", "hi", model="qwen3.5:4b")
    assert mem.history(cid) == [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
    assert mem.recent_conversations()[0]["n"] == 2


def test_deadlines_crud(mem):
    a = mem.add_deadline("MEC 260 HW", "2026-12-01 23:59", "MEC 260")
    mem.add_deadline("PHY 251 lab", "2026-11-25 23:59")
    assert [d["title"] for d in mem.list_deadlines()] == ["PHY 251 lab", "MEC 260 HW"]
    assert mem.complete_deadline(a)
    assert len(mem.list_deadlines()) == 1 and len(mem.list_deadlines(include_done=True)) == 2


def test_read_tools_run_without_confirm(mem, cfg, tmp_path):
    (tmp_path / "notes.txt").write_text("torque = r x F")
    asked = []
    reg = build_registry(mem, cfg.workspace, confirm=lambda n, a: asked.append(n) or False)
    assert "torque" in reg.call("read_file", {"path": str(tmp_path / "notes.txt")})
    assert "notes.txt" in reg.call("list_dir", {"path": str(tmp_path)})
    assert asked == []


def test_change_tools_need_confirmation(mem, cfg):
    reg = build_registry(mem, cfg.workspace, confirm=lambda n, a: False)
    out = reg.call("deadlines_add", {"title": "x", "due": "tomorrow"})
    assert out.startswith("DENIED") and mem.list_deadlines() == []

    reg_yes = build_registry(mem, cfg.workspace, confirm=lambda n, a: True)
    assert "Added deadline" in reg_yes.call("deadlines_add", {"title": "x", "due": "tomorrow"})
    logged = mem.conn.execute("SELECT tool, allowed FROM tool_log").fetchall()
    assert [tuple(r) for r in logged] == [("deadlines_add", 0), ("deadlines_add", 1)]


def test_write_file_sandbox_and_no_overwrite(mem, cfg, tmp_path):
    reg = build_registry(mem, cfg.workspace, confirm=lambda n, a: True)
    assert "Wrote" in reg.call("write_file", {"path": "doc.md", "content": "# hi"})
    assert "already exists" in reg.call("write_file", {"path": "doc.md", "content": "again"})
    assert "only writes inside" in reg.call("write_file", {"path": str(tmp_path / "escape.txt"), "content": "x"})
    assert "only writes inside" in reg.call("write_file", {"path": "../escape2.txt", "content": "x"})


def test_forbidden_tools_cannot_register():
    reg = ToolRegistry()
    with pytest.raises(PermissionDenied):
        reg.register(Tool("nuke", "x", {}, lambda: "", Tier.FORBIDDEN))
    with pytest.raises(PermissionDenied):
        reg.register(Tool("delete_file", "x", {}, lambda: "", Tier.CHANGE))
    with pytest.raises(PermissionDenied):
        reg.register(Tool("run_sudo", "x", {}, lambda: "", Tier.CHANGE))


def test_unknown_tool_and_bad_args(mem, cfg):
    reg = build_registry(mem, cfg.workspace)
    assert reg.call("nope", {}).startswith("ERROR: unknown tool")
    assert reg.call("read_file", {"wrong": 1}).startswith("ERROR: bad arguments")


def test_web_search_formats_results(monkeypatch):
    import sys
    import types

    class FakeDDGS:
        def text(self, q, max_results=5):
            return [{"title": "Ollama", "href": "https://ollama.com", "body": "Run models locally"}]

    monkeypatch.setitem(sys.modules, "ddgs", types.SimpleNamespace(DDGS=FakeDDGS))
    from atlas.tools.builtin import web_search
    out = web_search("ollama")
    assert "https://ollama.com" in out and out.startswith("1. Ollama")
