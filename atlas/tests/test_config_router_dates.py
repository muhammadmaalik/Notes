from datetime import datetime

import pytest

from atlas.config import load_config
from atlas.dates import parse_due
from atlas.router import heuristic_score, route


def test_profiles_load():
    lap, home = load_config("laptop"), load_config("homepc")
    assert lap.model_for("fast") == "qwen3.5:4b"
    assert lap.model_for("reasoning") == "qwen3.5:9b"
    assert home.model_for("reasoning") == "gpt-oss:20b"
    assert lap.options_for("fast")["think"] is False


def test_missing_profile():
    with pytest.raises(FileNotFoundError):
        load_config("nope")


@pytest.mark.parametrize("text", [
    "Solve the integral ∫ x^2 dx from 0 to 3",
    "Debug this:\n```python\ndef f(x): return x/0\n```",
    "Derive the moment of inertia of a thin rod and explain why step by step",
])
def test_routes_reasoning(cfg, text):
    assert route(text, cfg).role == "reasoning"


@pytest.mark.parametrize("text", ["hi", "thanks!", "what time is it", "hello atlas"])
def test_routes_fast(cfg, text):
    assert route(text, cfg).role == "fast"


def test_unsure_uses_llm_classifier_when_enabled(cfg):
    from conftest import FakeOllama
    fake = FakeOllama(replies=[{"role": "assistant", "content": "REASON"}])
    cfg.llm_classify = True
    r = route("Compare two internship offers for me", cfg, fake.client())
    assert r.role == "reasoning" and r.reason == "llm-classify"
    assert fake.requests[0]["model"] == "qwen3.5:4b"


def test_score_long_prompt():
    score, why = heuristic_score("word " * 300, long_chars=700)
    assert "long" in why and score >= 2


def test_parse_due():
    now = datetime(2026, 11, 21, 12, 0)  # a Saturday
    assert parse_due("2026-12-05", now) == "2026-12-05 23:59"
    assert parse_due("2026-12-05 09:30", now) == "2026-12-05 09:30"
    assert parse_due("tomorrow", now) == "2026-11-22 23:59"
    assert parse_due("+3d", now) == "2026-11-24 23:59"
    assert parse_due("friday", now) == "2026-11-27 23:59"
    with pytest.raises(ValueError):
        parse_due("someday", now)


def test_relative_paths_resolve_inside_repo(monkeypatch):
    from atlas.config import REPO_ROOT
    monkeypatch.delenv("ATLAS_DB", raising=False)
    c = load_config("laptop")
    assert c.db_path == REPO_ROOT / "data" / "atlas.db"
    assert c.workspace == REPO_ROOT / "data" / "workspace"
