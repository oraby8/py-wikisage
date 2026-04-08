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

    # Create dummy raw documents in different categories
    papers_dir = raw_dir / "papers"
    papers_dir.mkdir()
    paper_doc = papers_dir / "paper.txt"
    paper_doc.write_text("Paper content about Concept A.")

    clips_dir = raw_dir / "web_clips"
    clips_dir.mkdir()
    clip_doc = clips_dir / "clip.md"
    clip_doc.write_text("Web clip about Concept B.")

    # Mock litellm response
    mock_response_1 = MagicMock()
    mock_response_1.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps([{"title": "Concept A", "content": "Info A"}])
            )
        )
    ]
    mock_response_2 = MagicMock()
    mock_response_2.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps([{"title": "Concept B", "content": "Info B"}])
            )
        )
    ]
    mock_response_3 = MagicMock()
    mock_response_3.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    [
                        {"title": "Concept A", "content": "Final A"},
                        {"title": "Concept B", "content": "Final B"},
                    ]
                )
            )
        )
    ]
    mock_completion.side_effect = [mock_response_1, mock_response_2, mock_response_3]

    # Mock writing to just prevent failing if we remove write logic
    result = runner.invoke(app, ["compile"])

    assert result.exit_code == 0

    # Verify litellm completion was called three times (twice for extract, once for synthesis)
    assert mock_completion.call_count == 3

    # Verify the appropriate prompts were passed
    args_list = mock_completion.call_args_list
    messages_1 = args_list[0].kwargs["messages"][0]["content"]
    messages_2 = args_list[1].kwargs["messages"][0]["content"]

    assert (
        "Paper content about Concept A" in messages_1
        or "Paper content about Concept A" in messages_2
    )
    assert (
        "Web clip about Concept B" in messages_1
        or "Web clip about Concept B" in messages_2
    )


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
    assert "extract the key concepts" in get_extraction_prompt("papers").lower()


@patch("py_wikisage.core.prompts.Path.exists")
@patch("py_wikisage.core.prompts.Path.read_text")
def test_get_synthesis_prompt(mock_read_text, mock_exists):
    from py_wikisage.core.prompts import get_synthesis_prompt

    mock_exists.return_value = True
    mock_read_text.return_value = "Synthesis prompt"
    assert get_synthesis_prompt() == "Synthesis prompt"

    mock_exists.return_value = False
    assert "write" in get_synthesis_prompt().lower()


@patch("py_wikisage.core.compiler.extract_concepts_from_document")
@patch("py_wikisage.core.compiler.completion")
def test_process_raw_documents_synthesis(mock_completion, mock_extract, tmp_path: Path):
    raw_dir = tmp_path / "raw"
    wiki_dir = tmp_path / "wiki"
    raw_dir.mkdir()
    wiki_dir.mkdir()
    config = {"llm": {"provider": "openai", "model": "gpt-4o-mini"}}

    # Create dummy raw documents
    papers_dir = raw_dir / "papers"
    papers_dir.mkdir()
    paper_doc = papers_dir / "paper.txt"
    paper_doc.write_text("Paper content about Concept A.")

    # Mock extract to return dummy concepts
    mock_extract.return_value = [{"title": "Concept A", "content": "Extracted A"}]

    # Mock completion for synthesize pass
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    [{"title": "Concept A", "content": "Final Article A"}]
                )
            )
        )
    ]
    mock_completion.return_value = mock_response

    result = process_raw_documents(raw_dir, wiki_dir, config)

    # After processing, wiki_dir should contain Concept A.md
    assert (wiki_dir / "Concept A.md").exists()
    assert (wiki_dir / "Concept A.md").read_text() == "Final Article A"
    assert result == [{"title": "Concept A", "content": "Final Article A"}]


@patch("py_wikisage.core.compiler.is_file_processed")
@patch("py_wikisage.core.compiler.log_action")
@patch("py_wikisage.core.compiler.extract_concepts_from_document")
@patch("py_wikisage.core.compiler.completion")
def test_incremental_ingestion(
    mock_completion,
    mock_extract,
    mock_log_action,
    mock_is_file_processed,
    tmp_path: Path,
):
    raw_dir = tmp_path / "raw"
    wiki_dir = tmp_path / "wiki"
    raw_dir.mkdir()
    wiki_dir.mkdir()
    config = {"llm": {"provider": "openai", "model": "gpt-4o-mini"}}

    papers_dir = raw_dir / "papers"
    papers_dir.mkdir()

    file1 = papers_dir / "paper1.txt"
    file1.write_text("Processed.")

    file2 = papers_dir / "paper2.txt"
    file2.write_text("Unprocessed.")

    def mock_is_processed(wd, fname):
        return fname == "paper1.txt"

    mock_is_file_processed.side_effect = mock_is_processed

    mock_extract.return_value = [{"title": "Concept B", "content": "Extracted B"}]

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    [{"title": "Concept B", "content": "Final Article B"}]
                )
            )
        )
    ]
    mock_completion.return_value = mock_response

    from py_wikisage.core.compiler import process_raw_documents

    process_raw_documents(raw_dir, wiki_dir, config)

    # Assertions
    assert mock_extract.call_count == 1
    call_args = mock_extract.call_args[0]
    assert (
        call_args[1] == "paper2.txt"
    )  # filename is 2nd positional arg: (content, filename, category, config)

    mock_log_action.assert_called_once_with(wiki_dir, "ingest", "paper2.txt")
