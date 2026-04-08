import typer
from pathlib import Path
from rich.console import Console

from py_wikisage.core.ask_wiki import ask_with_wiki_context, save_answer_markdown
from py_wikisage.core.compiler import ingest_file, process_raw_documents
from py_wikisage.core.config import create_default_config, load_config
from py_wikisage.core.lint_wiki import run_lint
from py_wikisage.core.project_templates import ensure_agents_md
from py_wikisage.core.qmd_wrapper import (
    check_qmd_installed,
    init_qmd_collection,
    update_qmd_index,
    run_search,
    run_query,
    require_qmd,
)
from py_wikisage.core.state import log_action
from py_wikisage.core.wiki_index import regenerate_wiki_index

app = typer.Typer(
    help="Py-WikiSage: LLM-powered Markdown wiki compiler and search engine"
)
console = Console()


@app.command()
def init():
    """Initialize the wiki project directory"""
    cwd = Path.cwd()

    raw_dir = cwd / "raw"
    wiki_dir = cwd / "wiki"
    inside_raw_dir = ["assets", "papers", "repos", "articles", "experiments"]

    raw_dir.mkdir(exist_ok=True)
    wiki_dir.mkdir(exist_ok=True)
    for dir_name in inside_raw_dir:
        (raw_dir / dir_name).mkdir(exist_ok=True)

    config_created = create_default_config(cwd)
    agents_created = ensure_agents_md(cwd)

    console.print("[green]Initialized py-wikisage project[/green]")
    if config_created:
        console.print("Created [bold]config.yaml[/bold]")
    if agents_created:
        console.print("Created [bold]AGENTS.md[/bold] (wiki schema for you and your LLM agent)")
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
    result = process_raw_documents(raw_dir, wiki_dir, config)

    index_path = regenerate_wiki_index(wiki_dir)
    if index_path:
        console.print(f"[dim]Updated {index_path.relative_to(cwd)}[/dim]")

    log_action(
        wiki_dir,
        "compile",
        f"{result.files_processed} raw file(s) processed, {len(result.articles)} article(s) written",
    )

    if check_qmd_installed():
        console.print("[blue]Updating search index with qmd...[/blue]")
        init_qmd_collection(str(wiki_dir))
        update_qmd_index()
        console.print("[green]Compiled and indexed successfully![/green]")
    else:
        console.print(
            "[yellow]Compiled successfully, but qmd is not installed. Skipping search indexing.[/yellow]"
        )


@app.command()
def ingest(
    path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a file under raw/ (e.g. raw/papers/note.md)",
    ),
):
    """Process a single raw file (re-ingest even if it was compiled before)."""
    cwd = Path.cwd()
    raw_dir = cwd / "raw"
    wiki_dir = cwd / "wiki"
    config = load_config(cwd)

    path = path.resolve()
    raw_resolved = raw_dir.resolve()
    try:
        path.relative_to(raw_resolved)
    except ValueError:
        console.print(
            f"[red]Path must be inside {raw_dir} (got {path})[/red]"
        )
        raise typer.Exit(code=1)

    console.print(f"[blue]Ingesting {path.relative_to(cwd)}...[/blue]")
    result = ingest_file(raw_dir, path, wiki_dir, config)

    index_path = regenerate_wiki_index(wiki_dir)
    if index_path:
        console.print(f"[dim]Updated {index_path.relative_to(cwd)}[/dim]")

    log_action(
        wiki_dir,
        "ingest_cli",
        f"{path.name} -> {len(result.articles)} article(s)",
    )

    if check_qmd_installed():
        init_qmd_collection(str(wiki_dir))
        update_qmd_index()
    console.print("[green]Ingest finished.[/green]")


@app.command()
def lint():
    """Check wiki for broken wikilinks and orphan pages."""
    cwd = Path.cwd()
    wiki_dir = cwd / "wiki"
    issues, info = run_lint(wiki_dir)
    for line in info:
        console.print(f"[dim]{line}[/dim]")
    if not issues:
        console.print("[green]No issues reported.[/green]")
        return
    for msg in issues:
        console.print(f"[yellow]{msg}[/yellow]")
    raise typer.Exit(code=1)


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to answer using wiki context"),
    save: str | None = typer.Option(
        None,
        "--save",
        help="Save answer as markdown under wiki/ (e.g. notes/my-answer.md)",
    ),
):
    """Answer using qmd retrieval + LLM (citations from context)."""
    cwd = Path.cwd()
    wiki_dir = cwd / "wiki"
    config = load_config(cwd)

    require_qmd()
    console.print(f"[blue]Asking (wiki-backed): {question}[/blue]\n")
    answer = ask_with_wiki_context(question, config)
    console.print(answer)
    if save:
        try:
            out = save_answer_markdown(wiki_dir, question, answer, save)
            console.print(f"\n[green]Saved to {out.relative_to(cwd)}[/green]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(code=1)


@app.command()
def search(query: str):
    """Search the compiled wiki"""
    require_qmd()
    console.print(f"[blue]Searching wiki for: {query}[/blue]\n")
    output = run_search(query)
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
