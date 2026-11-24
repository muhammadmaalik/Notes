import json

from conftest import FakeOllama

from atlas.agent import Atlas
from atlas.research import Researcher, slugify, summary_of
from atlas.tools.builtin import build_registry

PAGES = {
    "https://science.nasa.gov/mission/voyager/spacecraft/": "Voyager 1 has a 3.7 m high-gain antenna. " * 20,
    "https://en.wikipedia.org/wiki/Voyager_1": "Voyager 1 launched September 5, 1977 on a Titan IIIE. " * 20,
    "https://voyager.jpl.nasa.gov/mission/spacecraft/": "Three RTGs supplied about 470 W at launch. " * 20,
    "https://voyager.jpl.nasa.gov/mission/status/": "Voyager 1 entered interstellar space in 2012. " * 20,
    "https://broken.example.com/page": None,
}


def fake_search(q, k):
    return [{"title": f"Page {i}", "href": url, "body": "snippet"} for i, url in enumerate(PAGES)][:k]


def fake_fetch(url, n):
    if PAGES[url] is None:
        raise ConnectionError("down")
    return PAGES[url][:n]


def responder(body):
    prompt = body["messages"][-1]["content"]
    if body.get("format") == "json" and "search queries" in prompt:
        return {"content": json.dumps({"title": "Voyager 1: Design and Mission",
                                       "queries": ["Voyager 1 spacecraft design", "Voyager 1 RTG power",
                                                   "Voyager 1 mission timeline"]})}
    if "Extract the facts" in prompt:
        return {"content": "- " + prompt.split("SOURCE TEXT:")[1].strip()[:60]}
    if "professional research report" in prompt:
        return {"content": "## Summary\nVoyager 1 is a three-axis stabilized probe powered by RTGs [3].\n\n"
                           "## Key facts\n- 3.7 m HGA [1]\n- Launched 1977 [2]\n"}
    return {"content": "ok"}


def make_researcher(cfg, fake):
    return Researcher(cfg, fake.pool(cfg), call_me="Maalik", search_fn=fake_search, fetch_fn=fake_fetch)


def test_research_pipeline_writes_cited_report(cfg):
    fake = FakeOllama(responder=responder)
    events = []
    res = make_researcher(cfg, fake).run("Voyager 1 design and mission", emit=events.append)
    assert res.title == "Voyager 1: Design and Mission"
    assert res.path.exists() and res.path.parent == cfg.reports_dir
    doc = res.path.read_text()
    assert "## Sources" in doc and "https://en.wikipedia.org/wiki/Voyager_1" in doc and "[3]" in doc
    assert "broken.example.com" not in doc                      # failed fetch skipped
    assert len(res.sources) == 4 and [s.n for s in res.sources] == [1, 2, 3, 4]
    assert res.summary.startswith("Voyager 1 is a three-axis")
    assert sum(e.startswith("search:") for e in events) == 3   # one per planned query
    # per-source notes go to the fast model, planning + synthesis to the reasoning model
    models = [r["model"] for r in fake.requests]
    assert models[0] == "qwen3.5:9b" and models[-1] == "qwen3.5:9b" and models.count("qwen3.5:4b") == 4


def test_research_domain_cap(cfg):
    fake = FakeOllama(responder=responder)
    r = make_researcher(cfg, fake)
    many = lambda q, k: [{"title": "x", "href": f"https://voyager.jpl.nasa.gov/p{i}", "body": ""} for i in range(5)]
    r.search_fn = many
    picked = r.gather(["q"], lambda m: None)
    assert len(picked) == 2


def test_research_via_chat_trigger_and_followup(cfg, mem):
    fake = FakeOllama(responder=responder)
    atlas = Atlas(cfg, fake.pool(cfg), mem, build_registry(mem, cfg.workspace),
                  researcher=make_researcher(cfg, fake))
    cid = mem.new_conversation()
    r = atlas.ask(cid, "Nah, look into Voyager 1, can you get some research done on the design please")
    assert r.role == "research" and r.report_path and "Report saved" in r.text and "[1]" in r.text
    n_before = len(fake.requests)
    r2 = atlas.ask(cid, "I want more please")
    assert r2.role == "research"
    plan_prompt = fake.requests[n_before]["messages"][-1]["content"]
    assert "Voyager 1" in plan_prompt and "Go deeper" in plan_prompt


def test_helpers():
    assert slugify("Voyager 1: Design & Mission!") == "voyager-1-design-mission"
    assert summary_of("## Summary\nShort.\n## Next\nx") == "Short."


def test_docx_export_skipped_without_pandoc(cfg, monkeypatch):
    from atlas import research
    monkeypatch.setattr(research.shutil, "which", lambda name: None)
    cfg.research["formats"] = ["md", "docx"]
    events = []
    res = make_researcher(cfg, FakeOllama(responder=responder)).run("Voyager 1", emit=events.append)
    assert res.path.exists() and res.extra_files == []
    assert any("docx export skipped" in e for e in events)


def test_pdf_text_extraction():
    import io

    from pypdf import PdfWriter

    from atlas.web import pdf_text
    buf = io.BytesIO()
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    w.write(buf)
    assert pdf_text(buf.getvalue()) == ""      # blank page parses without error
