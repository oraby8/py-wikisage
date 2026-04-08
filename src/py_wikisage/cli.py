import typer
from rich.console import Console
from pathlib import Path
from py_wikisage.core.config import create_default_config

app = typer.Typer(
    help="Py-WikiSage: LLM-powered Markdown wiki compiler and search engine"
)
console = Console()


@app.command()
def init():
    """Initialize the wiki project directory"""
    cwd = Path.cwd()

    # Create directories
    raw_dir = cwd / "raw"
    wiki_dir = cwd / "wiki"

    raw_dir.mkdir(exist_ok=True)
    wiki_dir.mkdir(exist_ok=True)

    # Create config
    config_created = create_default_config(cwd)

    console.print("[green]Initialized py-wikisage project[/green]")
    if config_created:
        console.print("Created [bold]config.yaml[/bold]")
    console.print("Created [bold]raw/[/bold] directory for source documents")
    console.print("Created [bold]wiki/[/bold] directory for generated output")


@app.command()
def compile():
    """Compile raw documents into the wiki"""
    console.print("[yellow]compile command is not implemented yet[/yellow]")


@app.command()
def search(query: str):
    """Search the compiled wiki"""
    console.print(
        f"[yellow]search command is not implemented yet for query: {query}[/yellow]"
    )


@app.command()
def query(query: str):
    """Perform a semantic query against the wiki"""
    console.print(
        f"[yellow]query command is not implemented yet for query: {query}[/yellow]"
    )


if __name__ == "__main__":
    app()
