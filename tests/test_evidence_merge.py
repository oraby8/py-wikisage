from py_wikisage.core.evidence_merge import (
    choose_merge_action,
    ensure_contradictions_section,
    parse_confidence,
    title_similarity,
)


def test_title_similarity_overlap():
    assert title_similarity("LLM", "Large Language Model (LLM)") > 0.20


def test_choose_merge_action_confidence_weighted():
    assert choose_merge_action("update", 0.2, 0.4) == "update"
    assert choose_merge_action("create", 0.8, 0.9) == "update"
    assert choose_merge_action("create", 0.55, 0.4) == "update"
    assert choose_merge_action("create", 0.2, 0.9) == "create"


def test_parse_confidence_variants():
    assert parse_confidence(0.7) == 0.7
    assert parse_confidence("confidence=0.45") == 0.45


def test_ensure_contradictions_section():
    out = ensure_contradictions_section("# Title\n\nBody", "- [2026-04-09] source: raw/a.md; confidence=0.40; note: conflict\n")
    assert "## Contradictions / updates" in out
