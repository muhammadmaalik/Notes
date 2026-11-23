from fastapi.testclient import TestClient
from typer.testing import CliRunner

from atlas.agent import Atlas
from atlas.cli import app as cli_app
from atlas.gateway import create_app
from atlas.memory import Memory
from atlas.tools.builtin import build_registry
from conftest import FakeOllama


def test_agent_routes_and_uses_tools(cfg, mem):
    mem.add_deadline("PHY 251 lab", "2026-11-25 23:59")
    fake = FakeOllama(replies=[
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "deadlines_list", "arguments": {}}}]},
        {"role": "assistant", "content": "Your next deadline is the PHY 251 lab on Nov 25."},
    ])
    atlas = Atlas(cfg, fake.client(), mem, build_registry(mem, cfg.workspace))
    cid = mem.new_conversation()
    r = atlas.ask(cid, "hey what's due")
    assert r.role == "fast" and r.model == "qwen3.5:4b"
    assert r.tool_calls == ["deadlines_list"]
    assert "PHY 251" in r.text
    # second request carried the tool result back to the model
    tool_msgs = [m for m in fake.requests[1]["messages"] if m["role"] == "tool"]
    assert "PHY 251 lab" in tool_msgs[0]["content"]
    assert fake.requests[0]["think"] is False and fake.requests[0]["options"]["num_ctx"] == 8192
    assert [m["role"] for m in mem.history(cid)] == ["user", "assistant"]


def test_agent_reasoning_route(cfg, mem):
    fake = FakeOllama(replies=[{"role": "assistant", "content": "x = 3"}])
    atlas = Atlas(cfg, fake.client(), mem, build_registry(mem, cfg.workspace))
    r = atlas.ask(mem.new_conversation(), "Solve the equation 2x + 4 = 10 step by step")
    assert r.role == "reasoning" and fake.requests[0]["model"] == "qwen3.5:9b"
    assert fake.requests[0]["think"] is True


def test_agent_stops_at_tool_limit(cfg, mem):
    loop = {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "list_dir", "arguments": {"path": "."}}}]}
    fake = FakeOllama(replies=[loop] * 20)
    atlas = Atlas(cfg, fake.client(), mem, build_registry(mem, cfg.workspace))
    r = atlas.ask(mem.new_conversation(), "hi")
    assert "tool-step limit" in r.text and len(r.tool_calls) == cfg.max_tool_steps + 1


def test_gateway_health_and_chat(cfg):
    fake = FakeOllama(replies=[{"role": "assistant", "content": "Hello, Muhammad."}])
    app = create_app(cfg, fake.client(), Memory(cfg.db_path))
    c = TestClient(app)
    h = c.get("/health").json()
    assert h["ok"] and h["profile"] == "laptop" and "qwen3.5:4b" in h["installed"]
    r = c.post("/chat", json={"message": "hi"}).json()
    assert r["reply"] == "Hello, Muhammad." and r["role"] == "fast" and r["conversation_id"] >= 1
    assert c.post("/chat", json={"message": "hi", "role": "bogus"}).status_code == 400


def test_gateway_denies_change_tools(cfg):
    fake = FakeOllama(replies=[
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "deadlines_add", "arguments": {"title": "x", "due": "tomorrow"}}}]},
        {"role": "assistant", "content": "I couldn't add it without approval."},
    ])
    mem = Memory(cfg.db_path)
    c = TestClient(create_app(cfg, fake.client(), mem))
    c.post("/chat", json={"message": "add a deadline x tomorrow"})
    assert mem.list_deadlines() == []


def test_cli_deadlines(cfg):
    runner = CliRunner()
    res = runner.invoke(cli_app, ["deadlines", "add", "MEC 262 HW 7", "--due", "2026-12-03", "--course", "MEC 262"])
    assert res.exit_code == 0, res.output
    res = runner.invoke(cli_app, ["deadlines", "list"])
    assert "MEC 262 HW 7" in res.output and "2026-12-03" in res.output
    res = runner.invoke(cli_app, ["deadlines", "done", "1"])
    assert res.exit_code == 0
    assert "No deadlines" in runner.invoke(cli_app, ["deadlines", "list"]).output
    assert runner.invoke(cli_app, ["deadlines", "add", "x", "--due", "someday"]).exit_code == 1
