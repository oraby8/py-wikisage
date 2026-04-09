import copy
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from py_wikisage.cli import app
from py_wikisage.core.config import DEFAULT_CONFIG, qmd_collection_name

runner = CliRunner()
_FAKE_ROOT = Path("/virtual/qmd-test-vault")
_EXPECTED_COLL = qmd_collection_name(copy.deepcopy(DEFAULT_CONFIG), _FAKE_ROOT)


@patch("py_wikisage.cli.Path.cwd", return_value=_FAKE_ROOT)
@patch("py_wikisage.core.qmd_wrapper.subprocess.run")
def test_search_command(mock_run, _mock_cwd):
    mock_run.return_value.stdout = "Found result: Concept A"
    mock_run.return_value.returncode = 0

    result = runner.invoke(app, ["search", "Concept"])

    assert result.exit_code == 0
    assert "Found result: Concept A" in result.stdout
    mock_run.assert_called_with(
        ["qmd", "search", "Concept", "-c", _EXPECTED_COLL],
        capture_output=True,
        text=True,
        check=False,
    )


@patch("py_wikisage.cli.Path.cwd", return_value=_FAKE_ROOT)
@patch("py_wikisage.core.qmd_wrapper.subprocess.run")
def test_query_command(mock_run, _mock_cwd):
    mock_run.return_value.stdout = "Query result: Concept A"
    mock_run.return_value.returncode = 0

    result = runner.invoke(app, ["query", "What is Concept A?"])

    assert result.exit_code == 0
    assert "Query result: Concept A" in result.stdout
    mock_run.assert_called_with(
        ["qmd", "query", "What is Concept A?", "-c", _EXPECTED_COLL],
        capture_output=True,
        text=True,
        check=False,
    )
