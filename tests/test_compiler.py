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
