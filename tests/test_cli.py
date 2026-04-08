from typer.testing import CliRunner
from py_wikisage.cli import app

runner = CliRunner()


def test_app_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Py-WikiSage" in result.stdout
    assert "init" in result.stdout
    assert "compile" in result.stdout
    assert "search" in result.stdout
    assert "query" in result.stdout


def test_app_init():
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "init command is not implemented yet" in result.stdout
