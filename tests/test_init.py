import os
from pathlib import Path
from typer.testing import CliRunner
from py_wikisage.cli import app

runner = CliRunner()


def test_init_command(tmp_path: Path):
    # Change current working directory to the temporary path for the test
    os.chdir(tmp_path)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert "Initialized py-wikisage project" in result.stdout
    assert (tmp_path / "raw").exists()
    assert (tmp_path / "wiki").exists()
    assert (tmp_path / "config.yaml").exists()
    assert (tmp_path / "AGENTS.md").exists()
