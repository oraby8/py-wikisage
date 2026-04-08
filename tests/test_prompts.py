import os
from pathlib import Path
from unittest.mock import patch
from py_wikisage.core.prompts import get_extraction_prompt, get_synthesis_prompt


@patch("py_wikisage.core.prompts.Path.exists")
@patch("py_wikisage.core.prompts.Path.read_text")
def test_get_extraction_prompt_specific(mock_read_text, mock_exists):
    mock_exists.side_effect = lambda: True
    mock_read_text.return_value = "Custom Paper Prompt"

    prompt = get_extraction_prompt("papers")
    assert prompt == "Custom Paper Prompt"


@patch("py_wikisage.core.prompts.Path.exists")
@patch("py_wikisage.core.prompts.Path.read_text")
def test_get_extraction_prompt_fallback(mock_read_text, mock_exists):
    mock_exists.side_effect = [False, True]
    mock_read_text.return_value = "Fallback Concept Prompt"

    prompt = get_extraction_prompt("unknown_category")
    assert prompt == "Fallback Concept Prompt"


@patch("py_wikisage.core.prompts.Path.exists")
@patch("py_wikisage.core.prompts.Path.read_text")
def test_get_synthesis_prompt(mock_read_text, mock_exists):
    mock_exists.return_value = True
    mock_read_text.return_value = "Synthesis Prompt"

    prompt = get_synthesis_prompt()
    assert prompt == "Synthesis Prompt"
