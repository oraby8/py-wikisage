from unittest.mock import patch
from py_wikisage.core.prompts import get_extraction_prompt, get_synthesis_prompt


@patch("py_wikisage.core.prompts._read_package_text")
def test_get_extraction_prompt_specific(mock_read):
    def se(rel: str):
        if rel == "prompts/extract_papers.txt":
            return "Custom Paper Prompt"
        return None

    mock_read.side_effect = se
    prompt = get_extraction_prompt("papers")
    assert prompt == "Custom Paper Prompt"


@patch("py_wikisage.core.prompts._read_package_text")
def test_get_extraction_prompt_fallback(mock_read):
    def se(rel: str):
        if rel == "prompts/extract_unknown_category.txt":
            return None
        if rel == "prompts/extract_concepts.txt":
            return "Fallback Concept Prompt"
        return None

    mock_read.side_effect = se
    prompt = get_extraction_prompt("unknown_category")
    assert prompt == "Fallback Concept Prompt"


@patch("py_wikisage.core.prompts._read_package_text")
def test_get_synthesis_prompt(mock_read):
    mock_read.return_value = "Synthesis Prompt"
    prompt = get_synthesis_prompt()
    assert prompt == "Synthesis Prompt"
