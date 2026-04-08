"""Answer a question using qmd retrieval context + LLM synthesis."""

from __future__ import annotations

from pathlib import Path

from litellm import completion
from rich.console import Console

from py_wikisage.core.llm_utils import build_completion_kwargs
from py_wikisage.core.qmd_wrapper import run_query

console = Console()


def ask_with_wiki_context(question: str, config: dict) -> str:
    """
    Run qmd hybrid query to gather context, then ask the configured LLM to answer
    with citations to wiki paths where possible.
    """
    retrieval = run_query(question)
    if not retrieval.strip():
        console.print(
            "[yellow]No retrieval text from qmd; answering with model knowledge only.[/yellow]"
        )

    prompt = (
        "You help the user explore their personal wiki. Use the RETRIEVAL_CONTEXT below "
        "(from a local markdown search engine). Answer the QUESTION clearly.\n"
        "- Prefer facts supported by the context.\n"
        "- Cite wiki file paths or titles mentioned in the context when you use them.\n"
        "- If context is insufficient, say so briefly and give a careful general answer.\n\n"
        f"RETRIEVAL_CONTEXT:\n{retrieval}\n\nQUESTION:\n{question}\n"
    )

    kwargs = build_completion_kwargs(
        config,
        [{"role": "user", "content": prompt}],
    )
    response = completion(**kwargs)
    return response.choices[0].message.content or ""


def save_answer_markdown(
    wiki_dir: Path, question: str, answer: str, filename: str
) -> Path:
    """Write answer under wiki_dir. Filename is relative to wiki (e.g. notes/my-answer.md)."""
    wiki_root = wiki_dir.resolve()
    rel = Path(filename)
    if rel.is_absolute():
        raise ValueError("Save path must be relative to the wiki directory.")
    out = (wiki_root / rel).resolve()
    if not out.is_relative_to(wiki_root):
        raise ValueError("Save path must stay inside wiki/")
    body = f"# Q\n\n{question}\n\n# A\n\n{answer}\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    return out
