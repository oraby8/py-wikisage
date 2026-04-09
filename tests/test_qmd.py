from pathlib import Path
from unittest.mock import patch

from py_wikisage.core.qmd_wrapper import check_qmd_installed, init_qmd_collection


@patch("subprocess.run")
def test_qmd_is_installed(mock_run):
    mock_run.return_value.returncode = 0
    assert check_qmd_installed() is True
    mock_run.assert_called_with(["qmd", "--version"], capture_output=True, check=False)


@patch("subprocess.run")
def test_qmd_is_not_installed(mock_run):
    mock_run.side_effect = FileNotFoundError()
    assert check_qmd_installed() is False


@patch("subprocess.run")
def test_init_qmd_collection(mock_run):
    init_qmd_collection("/tmp/myproject/wiki", "my-wiki-index")
    mock_run.assert_called_with(
        [
            "qmd",
            "collection",
            "add",
            str(Path("/tmp/myproject/wiki").resolve()),
            "--name",
            "my-wiki-index",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
