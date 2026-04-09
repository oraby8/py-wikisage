"""Tests for wikilink resolution heuristics in lint_wiki."""

from pathlib import Path

from py_wikisage.core.lint_wiki import (
    _expand_title_variants,
    collect_broken_wikilink_targets,
    run_lint,
)


def test_expand_acronym_long_name_roundtrip():
    keys = _expand_title_variants("LLM (Large Language Model)")
    assert "llm" in keys
    assert "large language model (llm)" in keys

    keys2 = _expand_title_variants("Large Language Model (LLM)")
    assert keys & keys2  # overlap so [[...]] either way resolves


def test_expand_mean_opinion_score():
    keys = _expand_title_variants("Mean Opinion Score (MOS)")
    assert "mos (mean opinion score)" in keys


def test_fuzzy_hyphen():
    keys = _expand_title_variants("F5-TTS")
    assert "f5 tts" in keys


def test_collect_broken_wikilink_targets(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "A.md").write_text("See [[Unknown Concept]] here.\n", encoding="utf-8")
    assert collect_broken_wikilink_targets(wiki) == ["Unknown Concept"]


def test_run_lint_resolves_asr_acronym(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "Automatic Speech Recognition (ASR).md").write_text(
        "# Automatic Speech Recognition (ASR)\n\nBody.\n", encoding="utf-8"
    )
    (wiki / "Other.md").write_text(
        "See [[ASR]] for speech.\n", encoding="utf-8"
    )
    issues, info = run_lint(wiki)
    broken = [i for i in issues if i.startswith("Broken")]
    assert not broken, broken


def test_lint_reports_contradictions_missing_source_and_date(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "A.md").write_text(
        "# A\n\n## Contradictions / updates\n\n- conflicting claim without source\n",
        encoding="utf-8",
    )
    issues, _ = run_lint(wiki)
    assert any("Contradictions section missing source citation" in i for i in issues)
    assert any("Contradictions section missing date" in i for i in issues)


def test_lint_reports_many_low_confidence_updates(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "B.md").write_text(
        "# B\n\n## Contradictions / updates\n\n"
        "- [2026-04-09] source: raw/a.md; confidence=0.20; note: one\n"
        "- [2026-04-10] source: raw/b.md; confidence=0.30; note: two\n"
        "- [2026-04-11] source: raw/c.md; confidence=0.40; note: three\n",
        encoding="utf-8",
    )
    issues, _ = run_lint(wiki)
    assert any("many low-confidence updates" in i for i in issues)
