import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from py_wikisage.core.compiler import process_raw_documents
from py_wikisage.cli import app
from typer.testing import CliRunner

runner = CliRunner()


@patch("py_wikisage.core.compiler.completion")
@patch("py_wikisage.core.qmd_wrapper.subprocess.run")
def test_compile_command(mock_subprocess, mock_completion, tmp_path: Path):
    os.chdir(tmp_path)

    # Mock subprocess success
    mock_subprocess.return_value.returncode = 0
    raw_dir = tmp_path / "raw"
    wiki_dir = tmp_path / "wiki"
    raw_dir.mkdir()
    wiki_dir.mkdir()

    # Create a test config
    config_file = tmp_path / "config.yaml"
    config_file.write_text("llm:\n  provider: openai\n  model: gpt-4o-mini")

    # Create a dummy raw document
    test_doc = raw_dir / "test.txt"
    test_doc.write_text(
        "The quick brown fox jumps over the lazy dog. Concept A is important."
    )

    # Mock litellm response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    [
                        {
                            "title": "Concept A",
                            "content": "Concept A is an important concept mentioned in the test document.",
                        }
                    ]
                )
            )
        )
    ]
    mock_completion.return_value = mock_response

    result = runner.invoke(app, ["compile"])

    assert result.exit_code == 0
    assert "Compiled" in result.stdout

    # Verify Concept_A.md was created
    concept_file = wiki_dir / "Concept_A.md"
    assert concept_file.exists()
    assert "Concept A is an important concept" in concept_file.read_text()

    # Verify qmd update and embed were called
    assert mock_subprocess.call_count >= 2


@patch("py_wikisage.core.prompts.Path.exists")
@patch("py_wikisage.core.prompts.Path.read_text")
def test_get_prompt(mock_read_text, mock_exists):
    from py_wikisage.core.prompts import get_prompt

    # Test file exists
    mock_exists.return_value = True
    mock_read_text.return_value = "Loaded Prompt"
    assert get_prompt("some_category", "Default") == "Loaded Prompt"

    # Test file does not exist
    mock_exists.return_value = False
    assert get_prompt("some_category", "Default") == "Default"


@patch("py_wikisage.core.prompts.Path.exists")
@patch("py_wikisage.core.prompts.Path.read_text")
def test_get_extraction_prompt(mock_read_text, mock_exists):
    from py_wikisage.core.prompts import get_extraction_prompt

    # Setup mock to return False for the specific category but True for fallback

    # If the file exists
    mock_exists.side_effect = [True]
    mock_read_text.return_value = "Extract papers prompt"
    assert get_extraction_prompt("papers") == "Extract papers prompt"

    # If specific doesn't exist, but fallback exists
    mock_exists.side_effect = [False, True]
    mock_read_text.return_value = "Extract concepts prompt"
    assert get_extraction_prompt("papers") == "Extract concepts prompt"

    # If neither exists
    mock_exists.side_effect = [False, False]
    assert "extract concepts" in get_extraction_prompt("papers").lower()


@patch("py_wikisage.core.prompts.Path.exists")
@patch("py_wikisage.core.prompts.Path.read_text")
def test_get_synthesis_prompt(mock_read_text, mock_exists):
    from py_wikisage.core.prompts import get_synthesis_prompt

    mock_exists.return_value = True
    mock_read_text.return_value = "Synthesis prompt"
    assert get_synthesis_prompt() == "Synthesis prompt"

    mock_exists.return_value = False
    assert "write" in get_synthesis_prompt().lower()
