"""Tests for wikilink resolution heuristics in lint_wiki."""

from pathlib import Path

from py_wikisage.core.lint_wiki import _expand_title_variants, run_lint


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
