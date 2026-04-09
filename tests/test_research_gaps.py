"""Tests for arXiv parsing and research-gaps orchestration."""

import io
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console

from py_wikisage.core.arxiv_client import (
    ArxivEntry,
    parse_arxiv_atom_feed,
    query_to_arxiv_search,
    reset_arxiv_rate_limit_clock,
    search_arxiv,
    write_arxiv_clip,
)
from py_wikisage.core.research_gaps import (
    dedupe_arxiv_gap_queries,
    merge_unique_queries,
    run_research_gaps,
    tavily_search,
)


_MINIMAL_ATOM = b"""<?xml version='1.0'?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1234.5678v1</id>
    <title>  Hello   World  </title>
    <summary>Abstract line.</summary>
    <published>2020-01-01T00:00:00Z</published>
    <link title="pdf" href="http://arxiv.org/pdf/1234.5678v1.pdf" rel="related" type="application/pdf"/>
  </entry>
</feed>
"""


def test_parse_arxiv_atom_feed_extracts_entry():
    entries = parse_arxiv_atom_feed(_MINIMAL_ATOM)
    assert len(entries) == 1
    e = entries[0]
    assert e.arxiv_id == "1234.5678v1"
    assert e.title == "Hello World"
    assert "Abstract" in e.summary
    assert "arxiv.org/abs/1234.5678v1" in e.abs_url


def test_query_to_arxiv_search():
    assert query_to_arxiv_search("Voice Cloning") == 'all:"Voice Cloning"'


def test_merge_unique_queries_order_and_dedupe():
    assert merge_unique_queries(["a", "b"], ["a", "c"]) == ["a", "b", "c"]


def test_dedupe_arxiv_gap_queries_one_per_search_string():
    assert dedupe_arxiv_gap_queries(["Voice", "Voice", "Other"]) == ["Voice", "Other"]


def test_dedupe_arxiv_gap_queries_distinct_phrases():
    out = dedupe_arxiv_gap_queries(["F5-TTS", "F5-TTS speech synthesis"])
    assert len(out) == 2


@patch("py_wikisage.core.arxiv_client.time.sleep", return_value=None)
def test_search_arxiv_retries_after_429(_mock_sleep):
    reset_arxiv_rate_limit_clock()
    calls = {"n": 0}

    class _Ok:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return _MINIMAL_ATOM

    def fake_urlopen(_req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(
                "https://export.arxiv.org/api/query",
                429,
                "Too Many",
                {"Retry-After": "0"},
                BytesIO(b""),
            )
        return _Ok()

    with patch(
        "py_wikisage.core.arxiv_client.urllib.request.urlopen",
        side_effect=fake_urlopen,
    ):
        entries = search_arxiv('all:"x"', max_results=3, max_retries=4)
    assert len(entries) == 1
    assert calls["n"] == 2


def test_write_arxiv_clip(tmp_path: Path):
    ent = ArxivEntry(
        arxiv_id="9999.9999v2",
        title='Title "quoted"',
        summary="S",
        published="2021-02-02",
        abs_url="https://arxiv.org/abs/9999.9999v2",
        pdf_url="https://arxiv.org/pdf/9999.9999v2.pdf",
    )
    p = write_arxiv_clip(ent, tmp_path)
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "source: arxiv" in text
    assert "9999.9999v2" in text
    assert "## Abstract" in text


def test_dry_run_does_not_create_web_clips(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "A.md").write_text("Link [[Missing Page]]\n", encoding="utf-8")
    raw = tmp_path / "raw"
    raw.mkdir()
    cfg = {"llm": {"provider": "openai", "model": "gpt-4o-mini"}}
    buf = io.StringIO()
    console = Console(file=buf, width=100, force_terminal=True)
    run_research_gaps(
        tmp_path,
        wiki,
        raw,
        cfg,
        apply=False,
        max_results=2,
        sources={"arxiv"},
        limit_queries=10,
        llm_gaps=False,
        console=console,
    )
    assert not (raw / "web_clips").exists()


@patch("py_wikisage.core.research_gaps.check_qmd_installed", return_value=False)
@patch("py_wikisage.core.research_gaps.ingest_file")
@patch("py_wikisage.core.research_gaps.search_arxiv")
def test_apply_writes_clip_and_calls_ingest(mock_search, mock_ingest, _mock_qmd, tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "A.md").write_text("Link [[Gap Topic]]\n", encoding="utf-8")
    raw = tmp_path / "raw"
    raw.mkdir()
    mock_search.return_value = [
        ArxivEntry(
            arxiv_id="1111.2222v1",
            title="Paper",
            summary="Abst",
            published="2022-01-01",
            abs_url="https://arxiv.org/abs/1111.2222v1",
            pdf_url="https://arxiv.org/pdf/1111.2222v1.pdf",
        )
    ]
    mock_ingest.return_value = MagicMock()
    cfg = {"llm": {"provider": "openai", "model": "gpt-4o-mini"}}
    console = Console(file=io.StringIO(), width=80, force_terminal=True)
    run_research_gaps(
        tmp_path,
        wiki,
        raw,
        cfg,
        apply=True,
        max_results=3,
        sources={"arxiv"},
        limit_queries=10,
        llm_gaps=False,
        console=console,
    )
    clip = raw / "web_clips" / "1111.2222v1.md"
    assert clip.is_file()
    mock_ingest.assert_called_once()
    args, _kwargs = mock_ingest.call_args
    assert args[1].resolve() == clip.resolve()


@patch("py_wikisage.core.research_gaps.urllib.request.urlopen")
def test_tavily_search_parses_results(mock_urlopen):
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value.read.return_value = (
        b'{"results": [{"url": "https://example.com/a", "title": "T", "content": "C"}]}'
    )
    mock_urlopen.return_value = mock_cm
    out = tavily_search("q", "key", 3)
    assert len(out) == 1
    assert out[0]["url"] == "https://example.com/a"
