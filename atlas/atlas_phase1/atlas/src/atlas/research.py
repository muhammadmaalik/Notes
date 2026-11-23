"""Deep research: plan -> search -> fetch -> read -> synthesize -> cited Markdown report."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from . import web

if TYPE_CHECKING:
    from .config import Config
    from .ollama_client import ClientPool

Event = Callable[[str], None]

PLAN_PROMPT = """You are planning web research for {call_me}.
Topic: {topic}
{extra}
Write {n} diverse web search queries that together cover the topic well (official/primary sources,
technical details, history, current status, good learning resources). Also write a short report title.
Return JSON: {{"title": "...", "queries": ["...", "..."]}}"""

NOTES_PROMPT = """Research topic: {topic}
Source [{n}]: {title} ({url})

Extract the facts from this source that are relevant to the topic, as tight bullet points.
Keep concrete numbers, dates, names, specs and design details. No intro, no opinions.
If the source is irrelevant or empty, reply exactly: NONE

SOURCE TEXT:
{text}"""

SYNTH_PROMPT = """Write a professional research report in Markdown for {call_me} on: {topic}
{extra}
Use ONLY the numbered source notes below. Cite sources inline like [1] or [2][5] after each claim.
Structure:
## Summary  (4-6 sentences, the key takeaways)
## Key facts  (bullets with numbers/specs)
## (2-5 sections that fit the topic, e.g. Design, Systems, Mission timeline, Current status)
## Best resources to read next  (which sources are most useful and why, with their [n])
## Open questions  (what the sources did not settle)
Do not add a Sources list; it is appended automatically. Do not invent facts or citations.

SOURCE NOTES:
{notes}"""


@dataclass
class Source:
    n: int
    title: str
    url: str
    snippet: str = ""
    text: str = ""
    notes: str = ""
    error: str = ""


@dataclass
class ResearchResult:
    topic: str
    title: str
    path: Path
    summary: str
    sources: list[Source]
    extra_files: list[Path] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].strip("-") or "report"


def _json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text or "", re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}


class Researcher:
    def __init__(self, cfg: "Config", pool: "ClientPool", *, call_me: str = "the user", tz: str = "America/New_York",
                 search_fn: Callable[[str, int], list[dict]] | None = None,
                 fetch_fn: Callable[[str, int], str] | None = None):
        self.cfg, self.pool, self.call_me, self.tz = cfg, pool, call_me, tz
        self.rc = cfg.research
        self.search_fn = search_fn or web.search
        self.fetch_fn = fetch_fn or (lambda url, n: web.fetch_text(url, n))
        self._emit: Event = lambda _m: None

    def _reason_opts(self) -> dict:
        opts = self.cfg.options_for("reasoning")
        opts["think"] = self.rc.get("think", opts.get("think"))
        opts["num_ctx"] = int(self.rc.get("num_ctx", opts.get("num_ctx", 8192)))
        return opts

    # ---------------------------------------------------------------- steps
    def plan(self, topic: str, extra: str, n: int) -> tuple[str, list[str]]:
        msg = self.pool.for_role("reasoning").chat(
            self.cfg.model_for("reasoning"),
            [{"role": "user", "content": PLAN_PROMPT.format(call_me=self.call_me, topic=topic, n=n,
                                                            extra=f"Context: {extra}" if extra else "")}],
            options=self._reason_opts(), fmt="json")
        data = _json(msg.get("content") or "")
        queries = [str(q).strip() for q in data.get("queries", []) if str(q).strip()][:n]
        if not queries:
            queries = [topic, f"{topic} overview", f"{topic} technical details"][:n]
        title = str(data.get("title") or topic).strip()
        return title, queries

    def gather(self, queries: list[str], emit: Event) -> list[Source]:
        per_q = int(self.rc.get("results_per_query", 5))
        max_sources = int(self.rc.get("max_sources", 8))
        seen, per_domain, picked = set(), {}, []
        for q in queries:
            emit(f"search: {q}")
            try:
                results = self.search_fn(q, per_q)
            except Exception as e:
                emit(f"  search failed: {e.__class__.__name__}")
                continue
            for r in results:
                url = (r.get("href") or r.get("url") or "").split("#")[0]
                if not url.startswith("http") or url in seen:
                    continue
                domain = urlparse(url).netloc.removeprefix("www.")
                if per_domain.get(domain, 0) >= 2:
                    continue
                seen.add(url)
                per_domain[domain] = per_domain.get(domain, 0) + 1
                picked.append(Source(0, r.get("title", domain), url, r.get("body", "")))
        # interleave so the first sources are not all from query 1
        return picked[: max_sources * 2]

    def read(self, topic: str, sources: list[Source], emit: Event) -> list[Source]:
        max_chars = int(self.rc.get("max_chars_per_source", 6000))
        max_sources = int(self.rc.get("max_sources", 8))

        def fetch(s: Source) -> Source:
            try:
                s.text = self.fetch_fn(s.url, max_chars)
            except Exception as e:
                s.error = f"{e.__class__.__name__}"
            return s

        with ThreadPoolExecutor(max_workers=6) as ex:
            fetched = list(ex.map(fetch, sources))
        good = [s for s in fetched if len(s.text) >= 300][:max_sources]
        for s in fetched:
            if s.error:
                emit(f"  skip (fetch failed: {s.error}): {s.url}")
        for i, s in enumerate(good, 1):
            s.n = i
        emit(f"reading {len(good)} sources")

        def take_notes(s: Source) -> Source:
            emit(f"  read [{s.n}] {s.title[:70]}")
            try:
                msg = self.pool.for_role("fast").chat(
                    self.cfg.model_for("fast"),
                    [{"role": "user", "content": NOTES_PROMPT.format(topic=topic, n=s.n, title=s.title,
                                                                     url=s.url, text=s.text)}],
                    options={**self.cfg.options_for("fast"), "think": False, "temperature": 0.2})
                s.notes = (msg.get("content") or "").strip()
            except Exception as e:
                s.notes = s.snippet
                emit(f"  notes failed for [{s.n}]: {e.__class__.__name__}")
            return s

        with ThreadPoolExecutor(max_workers=max(1, int(self.rc.get("parallel", 2)))) as ex:
            noted = list(ex.map(take_notes, good))
        return [s for s in noted if s.notes and s.notes.strip().upper() != "NONE"]

    def synthesize(self, topic: str, extra: str, sources: list[Source],
                   on_token: Callable[[str], None] | None) -> str:
        notes = "\n\n".join(f"[{s.n}] {s.title} — {s.url}\n{s.notes}" for s in sources)
        messages = [{"role": "user", "content": SYNTH_PROMPT.format(call_me=self.call_me, topic=topic, notes=notes,
                                                                    extra=f"Focus: {extra}" if extra else "")}]
        client = self.pool.for_role("reasoning")
        model = self.cfg.model_for("reasoning")
        if on_token:
            msg = client.chat_collect(model, messages, options=self._reason_opts(), on_token=on_token)
        else:
            msg = client.chat(model, messages, options=self._reason_opts())
        return (msg.get("content") or "").strip()

    # ---------------------------------------------------------------- report
    def save(self, title: str, topic: str, body: str, sources: list[Source], queries: list[str]) -> tuple[Path, list[Path]]:
        now = datetime.now(ZoneInfo(self.tz))
        out_dir = self.cfg.reports_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{now:%Y-%m-%d-%H%M}-{slugify(title)}.md"
        src_lines = "\n".join(f"{s.n}. [{s.title}]({s.url})" for s in sources)
        doc = (f"---\ntitle: \"{title}\"\nauthor: Atlas for {self.call_me}\ndate: {now:%B %d, %Y}\n---\n\n"
               f"# {title}\n\n*Prepared by Atlas · {now:%B %d, %Y %I:%M %p} · {len(sources)} sources read*\n\n"
               f"{body}\n\n## Sources\n\n{src_lines}\n\n"
               f"<details><summary>Search queries used</summary>\n\n"
               + "\n".join(f"- {q}" for q in queries) + "\n\n</details>\n")
        path.write_text(doc)
        extra = []
        for fmt in self.rc.get("formats", ["md"]):
            if fmt == "md":
                continue
            p = export(path, fmt)
            if p:
                extra.append(p)
            else:
                self._emit(f"{fmt} export skipped: needs pandoc" + (" + typst or LaTeX" if fmt == "pdf" else "")
                           + " (sudo dnf install -y pandoc typst)")
        return path, extra

    # ---------------------------------------------------------------- main
    def run(self, topic: str, *, extra: str = "", depth: int = 1, emit: Event | None = None,
            on_token: Callable[[str], None] | None = None) -> ResearchResult:
        emit = emit or (lambda _m: None)
        self._emit = emit
        n = int(self.rc.get("subqueries", 5)) + (depth - 1) * 2
        emit("planning searches")
        title, queries = self.plan(topic, extra, n)
        sources = self.gather(queries, emit)
        if not sources:
            raise RuntimeError("No search results. Check your internet connection or try a different phrasing.")
        read = self.read(topic, sources, emit)
        if not read:  # fall back to search snippets so the user still gets something
            emit("no pages could be read; using search snippets")
            read = [Source(i, s.title, s.url, s.snippet, notes=s.snippet) for i, s in enumerate(sources[:8], 1)]
        emit(f"writing report from {len(read)} sources")
        body = self.synthesize(topic, extra, read, on_token)
        path, files = self.save(title, topic, body, read, queries)
        return ResearchResult(topic, title, path, summary_of(body), read, files, queries)


def summary_of(body: str, max_chars: int = 900) -> str:
    m = re.search(r"##\s*Summary\s*\n(.+?)(\n##\s|\Z)", body, re.S | re.I)
    text = (m.group(1) if m else body).strip()
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


def export(md_path: Path, fmt: str) -> Path | None:
    """Convert with pandoc. pdf tries typst, then tectonic/xelatex/pdflatex."""
    if not shutil.which("pandoc"):
        return None
    out = md_path.with_suffix(f".{fmt}")
    cmd = ["pandoc", str(md_path), "-o", str(out), "--standalone"]
    if fmt == "pdf":
        engine = next((e for e in ("typst", "tectonic", "xelatex", "pdflatex") if shutil.which(e)), None)
        if not engine:
            return None
        cmd.append(f"--pdf-engine={engine}")
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return out
    except Exception:
        return None
