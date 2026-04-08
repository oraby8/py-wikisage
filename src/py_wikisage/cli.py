import typer
from rich.console import Console
from pathlib import Path
from py_wikisage.core.config import create_default_config, load_config
from py_wikisage.core.compiler import process_raw_documents
from py_wikisage.core.qmd_wrapper import (
    check_qmd_installed,
    init_qmd_collection,
    update_qmd_index,
    run_search,
    run_query,
    require_qmd,
)

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
    cwd = Path.cwd()
    raw_dir = cwd / "raw"
    wiki_dir = cwd / "wiki"

    config = load_config(cwd)

    console.print("[blue]Processing raw documents and generating wiki...[/blue]")
    process_raw_documents(raw_dir, wiki_dir, config)

    if check_qmd_installed():
        console.print("[blue]Updating search index with qmd...[/blue]")
        # Init collection if needed
        init_qmd_collection(str(wiki_dir))
        # Update and embed
        update_qmd_index()
        console.print("[green]Compiled and indexed successfully![/green]")
    else:
        console.print(
            "[yellow]Compiled successfully, but qmd is not installed. Skipping search indexing.[/yellow]"
        )


@app.command()
def search(query: str):
    """Search the compiled wiki"""
    require_qmd()
    console.print(f"[blue]Searching wiki for: {query}[/blue]\n")
    output = run_search(query)
    # The output is formatted by QMD natively using terminal sequences,
    # so we just print it as-is or wrap it cleanly.
    print(output)


@app.command()
def query(query: str):
    """Perform a semantic query against the wiki"""
    require_qmd()
    console.print(f"[blue]Querying wiki for: {query}[/blue]\n")
    output = run_query(query)
    print(output)


if __name__ == "__main__":
    app()
