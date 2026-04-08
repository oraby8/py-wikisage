import subprocess
from unittest.mock import patch
from py_wikisage.cli import app
from typer.testing import CliRunner

runner = CliRunner()


@patch("py_wikisage.core.qmd_wrapper.subprocess.run")
def test_search_command(mock_run):
    mock_run.return_value.stdout = b"Found result: Concept A"
    mock_run.return_value.returncode = 0

    result = runner.invoke(app, ["search", "Concept"])

    assert result.exit_code == 0
    assert "Found result: Concept A" in result.stdout
    mock_run.assert_called_with(
        ["qmd", "search", "Concept", "-c", "wiki"], capture_output=True, check=False
    )


@patch("py_wikisage.core.qmd_wrapper.subprocess.run")
def test_query_command(mock_run):
    mock_run.return_value.stdout = b"Query result: Concept A"
    mock_run.return_value.returncode = 0

    result = runner.invoke(app, ["query", "What is Concept A?"])

    assert result.exit_code == 0
    assert "Query result: Concept A" in result.stdout
    mock_run.assert_called_with(
        ["qmd", "query", "What is Concept A?", "-c", "wiki"],
        capture_output=True,
        check=False,
    )
