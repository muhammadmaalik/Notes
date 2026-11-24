"""Web helpers: DuckDuckGo search and page-text extraction."""

from __future__ import annotations

import re
from html import unescape

import httpx

UA = ("Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0 Atlas/0.2")


SEARCH_BACKENDS = ("auto", "yahoo", "duckduckgo", "brave", "auto")


def search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Returns [{'title','href','body'}]. Tries several ddgs backends (they rate-limit at random)."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from ddgs import DDGS
    n = max(1, min(int(max_results), 15))
    last: Exception | None = None
    for backend in SEARCH_BACKENDS:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                results = list(DDGS().text(query, max_results=n, backend=backend))
            if results:
                return results
        except Exception as e:  # "No results found", ratelimits, timeouts
            last = e
    if last:
        raise last
    return []


def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|nav|footer|header|aside)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def extract_text(html: str, url: str = "") -> str:
    try:
        import trafilatura
        text = trafilatura.extract(html, url=url or None, include_comments=False, include_tables=True,
                                   favor_recall=True)
        if text and len(text) > 200:
            return text
    except Exception:
        pass
    return _strip_html(html)


def fetch_text(url: str, max_chars: int = 8000, timeout: float = 20) -> str:
    """Download a page and return its main text (truncated). Raises on HTTP/network errors."""
    with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": UA}) as c:
        r = c.get(url)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            return pdf_text(r.content, max_chars)
        text = extract_text(r.text, url) if "html" in ctype or "<html" in r.text[:500].lower() else r.text
    return text[:max_chars]


def pdf_text(data: bytes, max_chars: int = 8000, max_pages: int = 25) -> str:
    """Text from a PDF (NASA NTRS reports, papers, datasheets)."""
    import io

    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    out, total = [], 0
    for page in reader.pages[:max_pages]:
        t = page.extract_text() or ""
        out.append(t)
        total += len(t)
        if total >= max_chars:
            break
    return re.sub(r"[ \t]+", " ", "\n".join(out)).strip()[:max_chars]
