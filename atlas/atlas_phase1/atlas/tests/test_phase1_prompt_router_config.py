import textwrap

import pytest

from atlas.config import load_config
from atlas.profile import load_profile, render_profile
from atlas.prompts import build_system_prompt
from atlas.router import is_followup, parse_command, route, wants_research


def test_profile_renders_known_facts_and_no_sensitive_keys(tmp_path):
    from atlas.config import REPO_ROOT
    prof = load_profile(REPO_ROOT / "configs" / "profile.yaml")
    text = render_profile(prof)
    for needle in ["Muhammad Maalik", "Stony Brook", "Mechanical Engineering", "Physics", "2029",
                   "FEA Lead", "Autodesk", "Jane Street", "PsiSat", "DARPA Lift", "Halal", "Saturdays"]:
        assert needle in text, needle
    assert "citizen" not in text.lower() and "immigra" not in text.lower()

    bad = tmp_path / "p.yaml"
    bad.write_text("name: X\nimmigration: secret\npassport: 123\n")
    assert render_profile(load_profile(bad)) == "- Name: X"


def test_system_prompt_has_name_time_facts_and_topic():
    sp = build_system_prompt(call_me="Maalik", profile_text="- Name: Muhammad Maalik", tz="America/New_York",
                             facts=["Maalik is taking PHY 251"], topic_hint="Voyager 1 design")
    assert "Maalik" in sp and "America/New_York" in sp and "PHY 251" in sp and "Voyager 1 design" in sp
    assert "clarifying questions" in sp


def test_parse_command():
    assert parse_command("/fast Something") == ("fast", "Something")
    assert parse_command("/deep prove it") == ("deep", "prove it")
    assert parse_command("/research") == ("research", "")
    assert parse_command("/fastest x") == (None, "/fastest x")
    assert parse_command("hello") == (None, "hello")


@pytest.mark.parametrize("text", [
    "Nah, look into Voyager 1, can you get some research done on that please, only the design",
    "research the Voyager 1 RTG power system",
    "find me sources on topology optimization for drone frames",
])
def test_research_triggers(cfg, text):
    assert wants_research(text) and route(text, cfg).role == "research"


@pytest.mark.parametrize("text", ["I want more please", "more", "go on", "why?", "tell me more", "elaborate"])
def test_followups(cfg, text):
    assert is_followup(text)
    r = route(text, cfg, has_history=True)
    assert r.role == "reasoning" and r.followup


def test_not_followups():
    assert not is_followup("It is raining hard in Stony Brook, should I bike to class today")
    assert not is_followup("explain the Schrödinger equation for a particle in a box")


def test_ambiguous_goes_to_reasoning(cfg):
    assert route("Something", cfg).role == "reasoning"
    assert route("help me plan my week around the robotics meeting", cfg).role == "reasoning"
    assert route("what time is it", cfg).role == "fast"


def test_per_role_hosts_and_local_override(tmp_path, monkeypatch):
    base = tmp_path / "pc.yaml"
    base.write_text(textwrap.dedent("""
        profile: pc
        ollama: {host: "http://127.0.0.1:11434"}
        models:
          fast: {name: "qwen3.5:9b", host: "http://127.0.0.1:11434"}
          reasoning: gpt-oss:20b
        model_options:
          reasoning: {think: low}
    """))
    (tmp_path / "pc.local.yaml").write_text('models:\n  fast: {host: "http://127.0.0.1:11435"}\n')
    c = load_config(path=base)
    assert c.host_for("fast") == "http://127.0.0.1:11435" and c.model_for("fast") == "qwen3.5:9b"
    assert c.host_for("reasoning") == "http://127.0.0.1:11434"
    # deep falls back to reasoning when not configured
    assert c.model_for("deep") == "gpt-oss:20b" and c.options_for("deep") == {"think": "low"}


def test_homepc_think_levels():
    c = load_config("homepc")
    assert c.options_for("reasoning")["think"] == "low"
    assert c.model_for("deep") == "qwen3.8:27b"
    assert c.model_for("embed") == "qwen3-embedding:0.6b"
