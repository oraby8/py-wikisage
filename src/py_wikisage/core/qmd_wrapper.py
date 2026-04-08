import subprocess
from rich.console import Console

console = Console()


def check_qmd_installed() -> bool:
    """Check if qmd is installed and available in the system PATH."""
    try:
        result = subprocess.run(["qmd", "--version"], capture_output=True, check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def init_qmd_collection(wiki_path: str):
    """Initialize a qmd collection for the wiki path."""
    subprocess.run(
        ["qmd", "collection", "add", wiki_path, "--name", "wiki"],
        capture_output=True,
        check=False,
    )


def update_qmd_index():
    """Run qmd update and embed to refresh the index."""
    subprocess.run(["qmd", "update"], capture_output=True, check=False)
    subprocess.run(["qmd", "embed"], capture_output=True, check=False)


def run_search(query: str) -> str:
    """Execute qmd search for the given query in the wiki collection."""
    result = subprocess.run(
        ["qmd", "search", query, "-c", "wiki"],
        capture_output=True,
        check=False,
    )
    return result.stdout.decode("utf-8")


def run_query(query: str) -> str:
    """Execute qmd hybrid query for the given string in the wiki collection."""
    result = subprocess.run(
        ["qmd", "query", query, "-c", "wiki"],
        capture_output=True,
        check=False,
    )
    return result.stdout.decode("utf-8")


def require_qmd():
    """Ensure qmd is installed, or print instructions and exit."""
    if not check_qmd_installed():
        console.print("[red]Error: `qmd` is not installed or not in PATH.[/red]")
        console.print("Please install it by running:")
        console.print("[bold]npm install -g @tobilu/qmd[/bold]")
        console.print("or")
        console.print("[bold]bun install -g @tobilu/qmd[/bold]")
        exit(1)
