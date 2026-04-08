import typer
from rich.console import Console

app = typer.Typer(
    help="Py-WikiSage: LLM-powered Markdown wiki compiler and search engine"
)
console = Console()


@app.command()
def init():
    """Initialize the wiki project directory"""
    console.print("[yellow]init command is not implemented yet[/yellow]")


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
