from pathlib import Path
from py_wikisage.core.state import log_action, is_file_processed


def test_log_action_appends_and_reads(tmp_path: Path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()

    log_action(wiki_dir, "ingest", "file1.md")

    log_file = wiki_dir / "log.md"
    assert log_file.exists()

    content = log_file.read_text()
    assert "ingest | file1.md" in content
    # Checking for date format roughly
    assert "## [" in content

    # Test appending
    log_action(wiki_dir, "ingest", "file2.md")
    content = log_file.read_text()
    assert "ingest | file1.md" in content
    assert "ingest | file2.md" in content


def test_is_file_processed(tmp_path: Path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()

    # Should be false if log doesn't exist or file not in it
    assert not is_file_processed(wiki_dir, "file1.md")

    log_action(wiki_dir, "ingest", "file1.md")

    assert is_file_processed(wiki_dir, "file1.md")
    assert not is_file_processed(wiki_dir, "file2.md")
