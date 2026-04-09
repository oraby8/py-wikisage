"""Answer a question using qmd retrieval context + LLM synthesis."""

from __future__ import annotations

import re
from pathlib import Path

from litellm import completion
from rich.console import Console

from py_wikisage.core.config import qmd_collection_name
from py_wikisage.core.llm_utils import build_completion_kwargs
from py_wikisage.core.qmd_wrapper import run_query

console = Console()

# LLM cites qmd://<collection>/path; normalize for readable terminal markdown.
_QMD_INLINE = re.compile(r"`qmd://[^/]+/([^`\s]+)`")
_QMD_MULTILINE = re.compile(
    r"\(\s*from\s*\n\s*`qmd://[^/]+/([^`]+)`\s*\)",
    re.IGNORECASE | re.DOTALL,
)


def format_answer_for_terminal(answer: str) -> str:
    """
    Prettify model output for Rich Markdown: readable wiki paths instead of qmd://
    URIs, and fix common broken line breaks before citation backticks.
    """
    text = answer.strip()
    if not text:
        return text
    text = _QMD_MULTILINE.sub(r"(from `wiki/\1`)", text)
    text = _QMD_INLINE.sub(r"`wiki/\1`", text)  # file path still under wiki/
    return text


def ask_with_wiki_context(question: str, config: dict, project_root: Path) -> str:
    """
    Run qmd hybrid query to gather context, then ask the configured LLM to answer
    with citations to wiki paths where possible.
    """
    coll = qmd_collection_name(config, project_root)
    retrieval = run_query(question, coll)
    if not retrieval.strip():
        console.print(
            "[yellow]No retrieval text from qmd; answering with model knowledge only.[/yellow]"
        )

    prompt = (
        "You help the user explore their personal wiki. Use the RETRIEVAL_CONTEXT below "
        "(from a local markdown search engine). Answer the QUESTION like a careful scientist.\n"
        "- **Mine the context fully** before concluding something is absent. If the wiki describes "
        "corpora, benchmarks, repurposed data, utterance counts, dialect coverage, or training "
        "resources — even without a commercial-style dataset brand name — treat that as evidence "
        "about **data / datasets** and summarize it explicitly.\n"
        "- Prefer facts supported by the context; do not contradict the wiki without saying the "
        "wiki is silent or ambiguous.\n"
        "- Cite wiki file paths or titles mentioned in the context when you use them.\n"
        "- If the context is truly insufficient, say so briefly; do not invent beyond it.\n\n"
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
