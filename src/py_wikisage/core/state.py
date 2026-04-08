from pathlib import Path
from datetime import datetime


def log_action(wiki_dir: Path, action: str, details: str) -> None:
    """Append a grep-friendly line: ## [YYYY-MM-DD] action | details"""
    log_file = wiki_dir / "log.md"
    day = datetime.now().strftime("%Y-%m-%d")
    clock = datetime.now().strftime("%H:%M:%S")
    log_line = f"## [{day}] {action} | {details} ({clock})\n"

    wiki_dir.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_line)


def is_file_processed(wiki_dir: Path, filename: str) -> bool:
    log_file = wiki_dir / "log.md"
    if not log_file.exists():
        return False

    with open(log_file, "r") as f:
        content = f.read()
        return f"ingest | {filename}" in content
