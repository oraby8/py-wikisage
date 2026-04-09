import subprocess
from pathlib import Path

from rich.console import Console

console = Console()


def check_qmd_installed() -> bool:
    """Check if qmd is installed and available in the system PATH."""
    try:
        result = subprocess.run(["qmd", "--version"], capture_output=True, check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _run_qmd(args: list[str], *, what: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
    )


def _report_qmd_failure(proc: subprocess.CompletedProcess, what: str) -> None:
    if proc.returncode == 0:
        return
    err = (proc.stderr or "").strip()
    out = (proc.stdout or "").strip()
    detail = err or out or f"exit {proc.returncode}"
    console.print(f"[yellow]qmd {what} failed ({proc.returncode}):[/yellow] {detail}")


def init_qmd_collection(wiki_path: str | Path, collection_name: str) -> bool:
    """Register this wiki directory as a named qmd collection (project-specific index)."""
    path = str(Path(wiki_path).resolve())
    proc = _run_qmd(
        ["qmd", "collection", "add", path, "--name", collection_name],
        what="collection add",
    )
    if proc.returncode != 0:
        _report_qmd_failure(proc, "collection add")
        console.print(
            "[dim]If the name is already taken by another path, run "
            "`qmd collection list`, then set [bold]qmd.collection[/bold] in config.yaml "
            "or [bold]qmd collection remove <name>[/bold] and compile again.[/dim]"
        )
        return False
    return True


def update_qmd_index(collection_name: str) -> bool:
    """Re-index and embed vectors for this collection (and global embed pass)."""
    up = _run_qmd(["qmd", "update", "-c", collection_name], what="update")
    if up.returncode != 0:
        _report_qmd_failure(up, "update")
        return False
    emb = _run_qmd(["qmd", "embed"], what="embed")
    if emb.returncode != 0:
        _report_qmd_failure(emb, "embed")
        console.print(
            "[dim]Hybrid [bold]query[/bold] may be weak until embed succeeds; "
            "[bold]search[/bold] (keyword) should still work after update.[/dim]"
        )
    return True


def run_search(query: str, collection_name: str) -> str:
    """Execute qmd keyword search in the given collection."""
    result = _run_qmd(
        ["qmd", "search", query, "-c", collection_name],
        what="search",
    )
    out = (result.stdout or "").strip()
    if result.returncode != 0:
        _report_qmd_failure(result, "search")
        if not out:
            return (result.stderr or "").strip()
    return result.stdout or ""


def run_query(query: str, collection_name: str) -> str:
    """Execute qmd hybrid query in the given collection."""
    result = _run_qmd(
        ["qmd", "query", query, "-c", collection_name],
        what="query",
    )
    out = (result.stdout or "").strip()
    if result.returncode != 0:
        _report_qmd_failure(result, "query")
        if not out:
            return (result.stderr or "").strip()
    return result.stdout or ""


def require_qmd():
    """Ensure qmd is installed, or print instructions and exit."""
    if not check_qmd_installed():
        console.print("[red]Error: `qmd` is not installed or not in PATH.[/red]")
        console.print("Please install it by running:")
        console.print("[bold]npm install -g @tobilu/qmd[/bold]")
        console.print("or")
        console.print("[bold]bun install -g @tobilu/qmd[/bold]")
        exit(1)
