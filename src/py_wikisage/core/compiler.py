import json
import re
from dataclasses import dataclass
from pathlib import Path

from litellm import completion
from rich.console import Console

from py_wikisage.core.llm_utils import build_completion_kwargs
from py_wikisage.core.prompts import get_extraction_prompt, get_synthesis_prompt
from py_wikisage.core.state import is_file_processed, log_action
from py_wikisage.core.utility import read_document
from py_wikisage.core.wiki_index import is_meta_wiki_file

console = Console()

# Max characters per existing page excerpt sent to synthesis (token budget)
_EXISTING_PAGE_CHAR_LIMIT = 6000


@dataclass
class ProcessResult:
    """Outcome of processing raw sources into wiki articles."""

    articles: list[dict]
    files_processed: int = 0


def load_existing_wiki_pages(wiki_dir: Path) -> list[dict]:
    """Load current wiki articles for merge-oriented synthesis (excludes index/log)."""
    if not wiki_dir.is_dir():
        return []

    out: list[dict] = []
    for path in sorted(wiki_dir.rglob("*.md")):
        if is_meta_wiki_file(path, wiki_dir):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        title = path.stem
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("#"):
                title = s.lstrip("#").strip() or title
                break
        body = text
        if len(body) > _EXISTING_PAGE_CHAR_LIMIT:
            body = body[:_EXISTING_PAGE_CHAR_LIMIT] + "\n\n[... truncated for synthesis context ...]"
        out.append({"title": title, "path": path.name, "content": body})
    return out


def extract_concepts_from_document(
    content: str, filename: str, category: str, config: dict
) -> list[dict]:
    prompt_template = get_extraction_prompt(category)

    prompt = f"{prompt_template}\n\nDocument ({filename}):\n{content}"

    try:
        completion_kwargs = build_completion_kwargs(
            config,
            [{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        response = completion(**completion_kwargs)
        response_content = response.choices[0].message.content

        try:
            parsed_data = json.loads(response_content)
            if isinstance(parsed_data, dict):
                for val in parsed_data.values():
                    if isinstance(val, list):
                        concepts = val
                        break
                else:
                    concepts = [parsed_data]
            else:
                concepts = parsed_data
            return concepts
        except json.JSONDecodeError:
            console.print(
                f"[red]Failed to parse JSON from LLM response for {filename}[/red]"
            )
            return []

    except Exception as e:
        console.print(f"[red]Error during LLM extraction for {filename}: {e}[/red]")
        return []


def synthesize_wiki_articles(
    raw_concepts: list[dict],
    config: dict,
    existing_pages: list[dict],
) -> list[dict]:
    if not raw_concepts:
        return []

    prompt_template = get_synthesis_prompt()
    existing_json = json.dumps(existing_pages, indent=2)
    concepts_json = json.dumps(raw_concepts, indent=2)
    prompt = (
        f"{prompt_template}\n\nEXISTING_WIKI_PAGES:\n{existing_json}\n\n"
        f"EXTRACTED_CONCEPTS:\n{concepts_json}"
    )

    try:
        completion_kwargs = build_completion_kwargs(
            config,
            [{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        console.print("[cyan]Synthesizing concepts into final wiki articles...[/cyan]")
        response = completion(**completion_kwargs)
        response_content = response.choices[0].message.content

        try:
            parsed_data = json.loads(response_content)
            if isinstance(parsed_data, dict):
                for val in parsed_data.values():
                    if isinstance(val, list):
                        articles = val
                        break
                else:
                    articles = [parsed_data]
            else:
                articles = parsed_data
            return articles
        except json.JSONDecodeError:
            console.print(
                "[red]Failed to parse JSON from LLM response during synthesis[/red]"
            )
            return []

    except Exception as e:
        console.print(f"[red]Error during LLM synthesis: {e}[/red]")
        return []


def process_raw_documents(
    raw_dir: Path,
    wiki_dir: Path,
    config: dict,
    *,
    restrict_files: frozenset[Path] | None = None,
) -> ProcessResult:
    """
    Read raw documents, extract concepts, merge with existing wiki via synthesis.

    If restrict_files is set, only those paths are processed and the processed-skipping
    log check is bypassed for them (used by `ingest`).
    """
    if not raw_dir.exists():
        console.print(f"[red]Raw directory {raw_dir} does not exist.[/red]")
        return ProcessResult(articles=[], files_processed=0)

    all_extracted_concepts: list[dict] = []
    files_processed = 0

    for file_path in raw_dir.glob("**/*"):
        if not file_path.is_file() or file_path.suffix not in [".txt", ".md", ".pdf"]:
            continue

        resolved = file_path.resolve()
        in_restrict = restrict_files is not None and resolved in restrict_files
        if restrict_files is not None and not in_restrict:
            continue

        if not in_restrict and is_file_processed(wiki_dir, file_path.name):
            console.print(
                f"[dim]Skipping already processed document: {file_path.name}[/dim]"
            )
            continue

        category = file_path.parent.name
        console.print(
            f"Processing document: [bold]{file_path.name}[/bold] (Category: {category})"
        )

        content = read_document(file_path)

        if content:
            concepts = extract_concepts_from_document(
                content, file_path.name, category, config
            )
            all_extracted_concepts.extend(concepts)
            log_action(wiki_dir, "ingest", file_path.name)
            files_processed += 1
        else:
            console.print(f"[red]No content found in {file_path}[/red]")

    existing_pages = load_existing_wiki_pages(wiki_dir)
    final_articles = synthesize_wiki_articles(
        all_extracted_concepts, config, existing_pages
    )

    if final_articles:
        wiki_dir.mkdir(parents=True, exist_ok=True)
        for article in final_articles:
            title = article.get("title", "Untitled")
            content = article.get("content", "")

            safe_title = re.sub(r'[<>:"/\\|?*]', "", title)
            rel_path = article.get("path")
            if not rel_path:
                for ep in existing_pages:
                    if ep.get("title") == title and ep.get("path"):
                        rel_path = ep["path"]
                        break
            if rel_path:
                candidate = (wiki_dir / rel_path).resolve()
                if candidate.is_relative_to(wiki_dir.resolve()):
                    out_path = candidate
                else:
                    out_path = wiki_dir / f"{safe_title}.md"
            else:
                out_path = wiki_dir / f"{safe_title}.md"

            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
            rel_out = out_path.resolve().relative_to(wiki_dir.resolve())
            console.print(f"[green]Wrote synthesized article: {rel_out}[/green]")

    return ProcessResult(articles=final_articles, files_processed=files_processed)


def ingest_file(raw_dir: Path, file_path: Path, wiki_dir: Path, config: dict) -> ProcessResult:
    """Process a single file under raw/ (re-ingest even if previously logged)."""
    file_path = file_path.resolve()
    raw_dir = raw_dir.resolve()
    if not file_path.is_file():
        console.print(f"[red]Not a file: {file_path}[/red]")
        return ProcessResult(articles=[], files_processed=0)
    try:
        file_path.relative_to(raw_dir)
    except ValueError:
        console.print(
            f"[red]File must be under raw directory: {raw_dir}[/red]"
        )
        return ProcessResult(articles=[], files_processed=0)

    return process_raw_documents(
        raw_dir,
        wiki_dir,
        config,
        restrict_files=frozenset([file_path]),
    )
