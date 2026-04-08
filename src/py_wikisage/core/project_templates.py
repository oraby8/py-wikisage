import importlib.resources


def default_agents_md() -> str:
    text = _read_template("AGENTS.md")
    if text is not None:
        return text
    return "# Py-WikiSage\n\nSee README for workflow.\n"


def _read_template(name: str) -> str | None:
    try:
        root = importlib.resources.files("py_wikisage.templates")
    except (ModuleNotFoundError, TypeError):
        return None
    path = root / name
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def ensure_agents_md(project_root) -> bool:
    """
    Write AGENTS.md from the package template if missing.
    Returns True if a file was created.
    """
    from pathlib import Path

    dest = Path(project_root) / "AGENTS.md"
    if dest.exists():
        return False
    dest.write_text(default_agents_md(), encoding="utf-8")
    return True
