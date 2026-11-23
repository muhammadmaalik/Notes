import json

from atlas.agent import Atlas, Callbacks
from atlas.ollama_client import ClientPool
from atlas.tools.builtin import build_registry
from conftest import FakeOllama, fake_embedding


def make(cfg, mem, fake, researcher=None):
    return Atlas(cfg, fake.pool(cfg), mem, build_registry(mem, cfg.workspace), researcher=researcher)


def test_fast_prefix_sends_only_the_message(cfg, mem):
    fake = FakeOllama(replies=[{"content": "Hey Maalik."}])
    r = make(cfg, mem, fake).ask(mem.new_conversation(), "/fast Something")
    assert r.role == "fast" and fake.requests[0]["model"] == "qwen3.5:4b"
    assert fake.requests[0]["messages"][-1] == {"role": "user", "content": "Something"}


def test_knows_users_name_and_time(cfg, mem):
    fake = FakeOllama()
    make(cfg, mem, fake).ask(mem.new_conversation(), "what's my name?")
    sp = fake.system_prompt()
    assert "Maalik" in sp and "Stony Brook" in sp and "America/New_York" in sp


def test_history_and_followup_topic(cfg, mem):
    fake = FakeOllama(replies=[{"content": "A pendulum's period is 2π√(L/g)."}, {"content": "More detail..."}])
    a = make(cfg, mem, fake)
    cid = mem.new_conversation()
    a.ask(cid, "/fast how does a simple pendulum period depend on length")
    r = a.ask(cid, "I want more please")
    assert r.role == "reasoning" and "follow-up" in r.route_reason
    msgs = fake.requests[1]["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert "simple pendulum" in msgs[0]["content"]   # topic hint carried into the system prompt


def test_remember_forget_and_retrieval(cfg, mem):
    fake = FakeOllama()
    a = make(cfg, mem, fake)
    assert "Saved" in a.ask(1, "/remember Maalik is taking PHY 251 this semester").text
    assert "Saved" in a.ask(1, "/remember Maalik's favorite language is Python").text
    assert "Already known" in a.ask(1, "/remember Maalik is taking PHY 251 this semester").text
    assert "Not allowed" not in a.ask(1, "/remember my passport number is 123").text
    assert len(mem.list_facts()) == 2  # passport fact blocked
    assert "#1" in a.ask(1, "/memory").text

    cid = mem.new_conversation()
    a.ask(cid, "what should I study for PHY 251 this semester")
    assert "PHY 251" in fake.system_prompt(0)

    assert "Forgot" in a.ask(1, "/forget PHY 251").text
    assert [f["text"] for f in mem.list_facts()] == ["Maalik's favorite language is Python"]


def test_background_fact_extraction(cfg, mem):
    cfg.memory["extract"] = True

    def responder(body):
        if body.get("format") == "json":
            return {"content": json.dumps({"facts": ["Maalik is building a LoRa base station.",
                                                     "Maalik's password is hunter2"]})}
        return {"content": "Nice project."}

    fake = FakeOllama(responder=responder)
    a = make(cfg, mem, fake)
    a.ask(mem.new_conversation(), "I'm building a LoRa base station with an SX1262 for my watch")
    a.wait_background(10)
    facts = [f["text"] for f in mem.list_facts()]
    assert facts == ["Maalik is building a LoRa base station."]
    assert fake.embed_requests, "facts should be embedded"


def test_fact_search_ranks_by_similarity(cfg, mem):
    for t in ["Maalik works Saturdays at his job", "Maalik leads FEA at Stony Brook Robotics",
              "Maalik likes quantum mechanics"]:
        mem.add_fact(t, fake_embedding(t))
    hits = mem.search_facts(fake_embedding("FEA robotics"), k=1, min_similarity=0.1)
    assert hits[0]["text"].startswith("Maalik leads FEA")
    # keyword fallback without embeddings
    assert mem.search_facts(None, k=1, query_text="quantum stuff")[0]["text"].endswith("quantum mechanics")


def test_streaming_tokens_and_thinking(cfg, mem):
    fake = FakeOllama(replies=[{"thinking": "Let me work this out carefully.", "content": "x = 3, because 2x = 6."}])
    toks, thinks, events = [], [], []
    r = make(cfg, mem, fake).ask(mem.new_conversation(), "Solve 2x + 4 = 10 step by step",
                                 cb=Callbacks(toks.append, thinks.append, events.append))
    assert "".join(toks) == "x = 3, because 2x = 6." and len(toks) > 1
    assert "".join(thinks) == "Let me work this out carefully."
    assert r.streamed and r.text == "x = 3, because 2x = 6."
    assert fake.requests[0]["stream"] is True
    assert any(e.startswith("route: reasoning") for e in events)


def test_streaming_with_tool_calls(cfg, mem):
    mem.add_deadline("MEC 262 HW", "2026-12-03 23:59")
    fake = FakeOllama(replies=[
        {"content": "", "tool_calls": [{"function": {"name": "deadlines_list", "arguments": {}}}]},
        {"content": "MEC 262 HW is due Dec 3."},
    ])
    toks = []
    r = make(cfg, mem, fake).ask(mem.new_conversation(), "what deadlines do I have coming up soon",
                                 cb=Callbacks(on_token=toks.append))
    assert r.tool_calls == ["deadlines_list"] and "".join(toks) == "MEC 262 HW is due Dec 3."


def test_deep_unloads_fast_when_on_other_host(cfg, mem):
    cfg.models["deep"] = "qwen3.8:27b"
    cfg.hosts = {"fast": "http://a:11435", "deep": "http://b:11434", "embed": "http://a:11435"}
    cfg.deep_unload_fast = True
    fake = FakeOllama()
    a = Atlas(cfg, ClientPool(cfg, factory=lambda h: fake.client()), mem, build_registry(mem, cfg.workspace))
    r = a.ask(mem.new_conversation(), "/deep derive the hydrogen atom energy levels")
    assert r.role == "deep" and r.model == "qwen3.8:27b"
    assert fake.generate_requests == [{"model": "qwen3.5:4b", "keep_alive": 0}]
    assert fake.requests[-1]["think"] is True


def test_usage_messages(cfg, mem):
    a = make(cfg, mem, FakeOllama())
    assert a.ask(1, "/deep").text.startswith("Usage")
    assert a.ask(1, "/remember").text.startswith("Usage")
