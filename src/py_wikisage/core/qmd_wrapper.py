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


def require_qmd():
    """Ensure qmd is installed, or print instructions and exit."""
    if not check_qmd_installed():
        console.print("[red]Error: `qmd` is not installed or not in PATH.[/red]")
        console.print("Please install it by running:")
        console.print("[bold]npm install -g @tobilu/qmd[/bold]")
        console.print("or")
        console.print("[bold]bun install -g @tobilu/qmd[/bold]")
        exit(1)
