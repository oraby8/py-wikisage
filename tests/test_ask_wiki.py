"""Tests for ask output formatting."""

from py_wikisage.core.ask_wiki import format_answer_for_terminal


def test_format_answer_rewrites_qmd_uri():
    s = "See `qmd://wiki/foo-bar.md` for details."
    assert "qmd://" not in format_answer_for_terminal(s)
    assert "`wiki/foo-bar.md`" in format_answer_for_terminal(s)


def test_format_answer_fixes_multiline_from_citation():
    s = (
        "NileTTS (from \n"
        "`qmd://wiki/niletts-egyptian-arabic-tts-dataset-and-model.md`)."
    )
    out = format_answer_for_terminal(s)
    assert "qmd://" not in out
    assert "(from `wiki/niletts-egyptian-arabic-tts-dataset-and-model.md`)." in out
    assert "from \n`" not in out
