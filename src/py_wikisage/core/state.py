from pathlib import Path
from datetime import datetime


def log_action(wiki_dir: Path, action: str, details: str) -> None:
    log_file = wiki_dir / "log.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"## [{timestamp}] {action} | {details}\n"

    with open(log_file, "a") as f:
        f.write(log_line)


def is_file_processed(wiki_dir: Path, filename: str) -> bool:
    log_file = wiki_dir / "log.md"
    if not log_file.exists():
        return False

    with open(log_file, "r") as f:
        content = f.read()
        return f"ingest | {filename}" in content
