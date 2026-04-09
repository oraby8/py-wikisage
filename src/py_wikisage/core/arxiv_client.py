"""Fetch arXiv search results (Atom API) and write markdown clips."""

from __future__ import annotations

import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


# arXiv asks for ~1 request / 3s; bursts yield HTTP 429.
ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_MIN_INTERVAL_SEC = 3.0
ARXIV_DEFAULT_TIMEOUT = 60.0
ARXIV_MAX_RETRIES = 6
_last_arxiv_request_end: float = 0.0


def reset_arxiv_rate_limit_clock() -> None:
    """For tests: clear pacing so sequential calls do not sleep."""
    global _last_arxiv_request_end
    _last_arxiv_request_end = 0.0
# Prefer newest submissions first (research-gaps default).
ARXIV_SORT_BY = "submittedDate"
ARXIV_SORT_ORDER = "descending"
_NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


@dataclass
class ArxivEntry:
    arxiv_id: str
    title: str
    summary: str
    published: str
    abs_url: str
    pdf_url: str


def _text(elem: ET.Element | None) -> str:
    if elem is None or elem.text is None:
        return ""
    return " ".join(elem.text.split())


def _entry_id_to_arxiv_id(atom_id: str) -> str:
    # http://arxiv.org/abs/2401.12345v1 -> 2401.12345v1
    m = re.search(r"arxiv\.org/abs/([^/\s]+)", atom_id, re.I)
    if m:
        return m.group(1)
    return re.sub(r"[^\w.\-]", "_", atom_id)[:80]


def _arxiv_rate_limit_wait() -> None:
    """Sleep until at least ARXIV_MIN_INTERVAL_SEC since the last request finished."""
    global _last_arxiv_request_end
    now = time.monotonic()
    gap = ARXIV_MIN_INTERVAL_SEC - (now - _last_arxiv_request_end)
    if gap > 0:
        time.sleep(gap)


def _mark_arxiv_request_done() -> None:
    global _last_arxiv_request_end
    _last_arxiv_request_end = time.monotonic()


def parse_arxiv_atom_feed(data: bytes) -> list[ArxivEntry]:
    """Parse arXiv Atom API response bytes into entries (for tests and search_arxiv)."""
    root = ET.fromstring(data)
    out: list[ArxivEntry] = []
    for entry in root.findall("a:entry", _NS):
        aid_el = entry.find("a:id", _NS)
        atom_id = _text(aid_el)
        arxiv_id = _entry_id_to_arxiv_id(atom_id)
        title = _text(entry.find("a:title", _NS))
        summary = _text(entry.find("a:summary", _NS))
        published = _text(entry.find("a:published", _NS))
        pdf_link = ""
        for link in entry.findall("a:link", _NS):
            if link.get("title") == "pdf" or link.get("type") == "application/pdf":
                pdf_link = link.get("href") or ""
                break
        abs_url = f"https://arxiv.org/abs/{arxiv_id}"
        if not pdf_link:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        else:
            pdf_url = pdf_link
        out.append(
            ArxivEntry(
                arxiv_id=arxiv_id,
                title=title,
                summary=summary,
                published=published,
                abs_url=abs_url,
                pdf_url=pdf_url,
            )
        )
    return out


def search_arxiv(
    query: str,
    max_results: int = 3,
    timeout: float = ARXIV_DEFAULT_TIMEOUT,
    max_retries: int = ARXIV_MAX_RETRIES,
) -> list[ArxivEntry]:
    """
    Query arXiv API. `query` is passed as search_query= (see arXiv API docs).

    Respects arXiv's suggested ~3s spacing between requests and retries on
    429 / transient errors with backoff (similar spirit to other API clients).
    """
    q = query.strip()
    if not q:
        return []
    params = urllib.parse.urlencode(
        {
            "search_query": q,
            "start": 0,
            "max_results": max(1, min(max_results, 50)),
            "sortBy": ARXIV_SORT_BY,
            "sortOrder": ARXIV_SORT_ORDER,
        }
    )
    url = f"{ARXIV_API}?{params}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "py-wikisage/0.1 (research gaps; +https://github.com)"},
    )

    for attempt in range(max(1, max_retries)):
        _arxiv_rate_limit_wait()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            _mark_arxiv_request_done()
            return parse_arxiv_atom_feed(data)
        except urllib.error.HTTPError as e:
            _mark_arxiv_request_done()
            if e.code in (429, 500, 502, 503, 504) and attempt + 1 < max_retries:
                retry_after = 0.0
                if e.headers:
                    raw = e.headers.get("Retry-After")
                    if raw:
                        try:
                            retry_after = float(raw)
                        except ValueError:
                            retry_after = 0.0
                if retry_after <= 0:
                    retry_after = min(
                        90.0, 4.0 * (2**attempt) + random.uniform(0.0, 2.0)
                    )
                time.sleep(retry_after)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            _mark_arxiv_request_done()
            if attempt + 1 >= max_retries:
                raise
            time.sleep(min(60.0, 2.0 * (2**attempt) + random.uniform(0.0, 1.0)))
            continue

    return []


def query_to_arxiv_search(wikilink_target: str) -> str:
    """Turn a wiki concept name into a simple arXiv `all:` query."""
    t = wikilink_target.strip()
    t = re.sub(r"\s+", " ", t)
    if not t:
        return ""
    return f'all:"{t}"'


def json_escape_yaml_string(s: str) -> str:
    """Quote for YAML double-quoted scalar (escape quotes)."""
    esc = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{esc}"'


def write_arxiv_clip(entry: ArxivEntry, dest_dir: Path) -> Path:
    """Write one markdown file under dest_dir. Returns path written."""
    safe = re.sub(r'[<>:"/\\|?*]', "_", entry.arxiv_id)
    path = dest_dir / f"{safe}.md"
    fm = (
        "---\n"
        f'source: arxiv\n'
        f'arxiv_id: "{entry.arxiv_id}"\n'
        f'title: {json_escape_yaml_string(entry.title)}\n'
        f'url_abs: "{entry.abs_url}"\n'
        f'url_pdf: "{entry.pdf_url}"\n'
        f'published: "{entry.published}"\n'
        "---\n\n"
    )
    body = f"## Abstract\n\n{entry.summary.strip()}\n\n## Links\n\n- [abs]({entry.abs_url}) · [pdf]({entry.pdf_url})\n"
    dest_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(fm + body, encoding="utf-8")
    return path
