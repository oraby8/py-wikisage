import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from litellm import completion
from rich.console import Console

from py_wikisage.core.evidence_merge import (
    choose_merge_action,
    ensure_contradictions_section,
    format_contradiction_note,
    parse_confidence,
    title_similarity,
)
from py_wikisage.core.llm_utils import build_completion_kwargs
from py_wikisage.core.prompts import (
    get_extraction_prompt,
    get_overview_synthesis_prompt,
    get_synthesis_prompt,
)
from py_wikisage.core.qmd_wrapper import check_qmd_installed, run_query
from py_wikisage.core.state import is_file_processed, log_action
from py_wikisage.core.utility import read_document
from py_wikisage.core.wiki_index import is_meta_wiki_file

console = Console()

# Max characters per existing page excerpt sent to synthesis (token budget)
_EXISTING_PAGE_CHAR_LIMIT = 6000
_OVERVIEW_PAGE_NAMES = ("_Synthesis.md", "Research_Overview.md")


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
        out.append(
            {"title": title, "path": str(path.relative_to(wiki_dir)), "content": body}
        )
    return out


def _is_overview_path(path: str) -> bool:
    base = Path(path).name
    return base in _OVERVIEW_PAGE_NAMES


def _extract_index_candidates(wiki_dir: Path) -> list[dict]:
    """Read wiki/index.md bullets like - [Title](path.md)."""
    out: list[dict] = []
    index_path = wiki_dir / "index.md"
    if not index_path.is_file():
        return out
    try:
        text = index_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        m = re.match(r"^\s*-\s+\[(.*?)\]\((.*?)\)", line.strip())
        if not m:
            continue
        title = m.group(1).strip()
        path = m.group(2).strip()
        out.append({"title": title, "path": path})
    return out


def _extract_qmd_paths(result: str) -> set[str]:
    """
    Pull wiki paths from qmd output:
    - qmd://wiki/foo.md
    - ... (foo.md)
    """
    found: set[str] = set()
    for m in re.finditer(r"qmd://wiki/([^\s),]+\.md)", result):
        found.add(m.group(1).strip())
    for m in re.finditer(r"\(([^)\s]+\.md)\)", result):
        found.add(m.group(1).strip())
    return found


def select_relevant_existing_pages(
    raw_concepts: list[dict], existing_pages: list[dict], wiki_dir: Path, top_k: int = 8
) -> list[dict]:
    """
    Hybrid relevance:
    1) index/title token overlap prefilter
    2) qmd rerank by concept titles (when installed)
    """
    if not raw_concepts or not existing_pages:
        return existing_pages[:top_k]

    page_by_path = {p.get("path", ""): p for p in existing_pages if p.get("path")}
    index_entries = _extract_index_candidates(wiki_dir)
    concept_titles = [str(c.get("title", "")).strip() for c in raw_concepts if c.get("title")]

    # Index + title overlap prefilter
    score: dict[str, float] = {}
    for page in existing_pages:
        p_title = str(page.get("title", ""))
        p_path = str(page.get("path", ""))
        if not p_path:
            continue
        best = 0.0
        for ct in concept_titles:
            best = max(best, title_similarity(ct, p_title))
        score[p_path] = best

    # Bonus when index has close title/path match
    for idx in index_entries:
        idx_title = str(idx.get("title", ""))
        idx_path = str(idx.get("path", ""))
        if idx_path not in score:
            continue
        for ct in concept_titles:
            if title_similarity(ct, idx_title) >= 0.35:
                score[idx_path] += 0.20
                break

    # qmd rerank
    if check_qmd_installed():
        for ct in concept_titles[:3]:
            out = run_query(ct)
            for p in _extract_qmd_paths(out):
                if p in score:
                    score[p] += 0.35

    ranked_paths = [k for k, _ in sorted(score.items(), key=lambda kv: kv[1], reverse=True)]
    picked: list[dict] = []
    for p in ranked_paths:
        if p in page_by_path:
            picked.append(page_by_path[p])
        if len(picked) >= top_k:
            break
    # Always include synthesis overview pages even if not in top-k.
    for page in existing_pages:
        p = str(page.get("path", ""))
        if _is_overview_path(p) and page not in picked:
            picked.append(page)
    return picked or existing_pages[:top_k]


def _best_existing_match(title: str, existing_pages: list[dict]) -> tuple[dict | None, float]:
    best_page = None
    best_score = -1.0
    for page in existing_pages:
        s = title_similarity(title, str(page.get("title", "")))
        if s > best_score:
            best_score = s
            best_page = page
    return best_page, max(best_score, 0.0)


def _extract_json_candidate(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    # Strip fenced blocks: ```json ... ```
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    # Prefer whichever JSON root delimiter appears first in text.
    a1, a2 = raw.find("["), raw.rfind("]")
    b1, b2 = raw.find("{"), raw.rfind("}")
    if a1 != -1 and b1 != -1:
        if a1 < b1 and a2 > a1:
            return raw[a1 : a2 + 1]
        if b2 > b1:
            return raw[b1 : b2 + 1]
    if a1 != -1 and a2 > a1:
        return raw[a1 : a2 + 1]
    if b1 != -1 and b2 > b1:
        return raw[b1 : b2 + 1]
    return raw


def _repair_json_once(bad_text: str, config: dict, context_label: str) -> Any | None:
    """One-shot JSON repair pass through the model."""
    repair_prompt = (
        "Fix the following output into STRICT valid JSON only.\n"
        "Rules:\n"
        "- Return JSON only, no prose, no markdown fences.\n"
        "- Preserve original meaning and keys as much as possible.\n"
        f"- Context: {context_label}\n\n"
        f"BAD_OUTPUT:\n{bad_text}\n"
    )
    try:
        kwargs = build_completion_kwargs(
            config,
            [{"role": "user", "content": repair_prompt}],
            response_format={"type": "json_object"},
        )
        repaired = completion(**kwargs).choices[0].message.content or ""
        cand = _extract_json_candidate(repaired)
        if not cand:
            return None
        return json.loads(cand)
    except Exception:
        return None


def _parse_json_payload(raw_text: str, config: dict, context_label: str) -> Any | None:
    cand = _extract_json_candidate(raw_text)
    if cand:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            pass
    return _repair_json_once(raw_text, config, context_label)


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

        parsed_data = _parse_json_payload(
            response_content, config, f"extract concepts for {filename}"
        )
        if parsed_data is None:
            console.print(
                f"[red]Failed to parse JSON from LLM response for {filename}[/red]"
            )
            return []
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

    except Exception as e:
        console.print(f"[red]Error during LLM extraction for {filename}: {e}[/red]")
        return []


def synthesize_wiki_articles(
    raw_concepts: list[dict],
    config: dict,
    existing_pages: list[dict],
    relevant_pages: list[dict],
) -> list[dict]:
    if not raw_concepts:
        return []

    prompt_template = get_synthesis_prompt()
    existing_json = json.dumps(existing_pages, indent=2)
    relevant_json = json.dumps(relevant_pages, indent=2)
    concepts_json = json.dumps(raw_concepts, indent=2)
    prompt = (
        f"{prompt_template}\n\nEXISTING_WIKI_PAGES:\n{existing_json}\n\n"
        f"RELEVANT_EXISTING_PAGES:\n{relevant_json}\n\n"
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

        parsed_data = _parse_json_payload(
            response_content, config, "synthesize wiki articles"
        )
        if parsed_data is None:
            console.print(
                "[red]Failed to parse JSON from LLM response during synthesis[/red]"
            )
            return []
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

    except Exception as e:
        console.print(f"[red]Error during LLM synthesis: {e}[/red]")
        return []


def _overview_page_path(wiki_dir: Path) -> Path:
    default = wiki_dir / "_Synthesis.md"
    alt = wiki_dir / "Research_Overview.md"
    if default.exists():
        return default
    if alt.exists():
        return alt
    return default


def synthesize_overview_page(
    *,
    wiki_dir: Path,
    config: dict,
    extracted_concepts: list[dict],
    updated_pages: list[dict],
) -> dict | None:
    """
    Maintain top-level thesis/synthesis overview page.
    Returns metadata dict for logging when updated.
    """
    if not extracted_concepts:
        return None

    overview_path = _overview_page_path(wiki_dir)
    if overview_path.is_file():
        existing_overview = overview_path.read_text(encoding="utf-8", errors="replace")
    else:
        existing_overview = ""

    prompt = (
        f"{get_overview_synthesis_prompt()}\n\n"
        f"EXISTING_OVERVIEW_PAGE:\n{existing_overview}\n\n"
        f"UPDATED_CONCEPT_PAGES:\n{json.dumps(updated_pages, indent=2)}\n\n"
        f"EXTRACTED_CONCEPTS:\n{json.dumps(extracted_concepts, indent=2)}"
    )

    try:
        kwargs = build_completion_kwargs(config, [{"role": "user", "content": prompt}])
        console.print("[cyan]Updating synthesis overview page...[/cyan]")
        response = completion(**kwargs)
        content = response.choices[0].message.content or ""
    except Exception as e:
        console.print(f"[red]Error during overview synthesis: {e}[/red]")
        return None

    if not content.strip():
        return None

    overview_path.parent.mkdir(parents=True, exist_ok=True)
    overview_path.write_text(content, encoding="utf-8")
    rel = overview_path.resolve().relative_to(wiki_dir.resolve())
    console.print(f"[green]Wrote synthesis overview: {rel}[/green]")
    return {"path": str(rel), "source_count": len(extracted_concepts)}


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
    relevant_pages = select_relevant_existing_pages(
        all_extracted_concepts, existing_pages, wiki_dir
    )
    final_articles = synthesize_wiki_articles(
        all_extracted_concepts, config, existing_pages, relevant_pages
    )

    written_pages: list[dict] = []
    if final_articles:
        wiki_dir.mkdir(parents=True, exist_ok=True)
        for article in final_articles:
            title = article.get("title", "Untitled")
            content = article.get("content", "")
            requested_action = str(article.get("action", "") or "create")
            confidence = parse_confidence(article.get("confidence"))
            source = str(article.get("source", "synthesis"))

            best_page, sim = _best_existing_match(title, existing_pages)
            decided_action = choose_merge_action(requested_action, sim, confidence)
            novelty_guarded = requested_action.lower() == "create" and decided_action == "update"
            if novelty_guarded and best_page is not None:
                content = ensure_contradictions_section(
                    content,
                    format_contradiction_note(
                        source=source,
                        reason=(
                            f"Novelty guard: merged into existing page "
                            f"'{best_page.get('title', best_page.get('path', 'unknown'))}' "
                            f"(title_similarity={sim:.2f})"
                        ),
                        confidence=confidence,
                    ),
                )
                log_action(
                    wiki_dir,
                    "contradiction",
                    f"{title} -> merged with {best_page.get('title', 'unknown')}",
                )

            safe_title = re.sub(r'[<>:"/\\|?*]', "", title)
            rel_path = article.get("path")
            if not rel_path and decided_action == "update" and best_page is not None:
                rel_path = best_page.get("path")
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
            written_pages.append(
                {"title": title, "path": str(rel_out), "content": content}
            )
            log_action(
                wiki_dir,
                "merge",
                f"{decided_action} | {rel_out} | confidence={confidence:.2f}",
            )

    overview_update = synthesize_overview_page(
        wiki_dir=wiki_dir,
        config=config,
        extracted_concepts=all_extracted_concepts,
        updated_pages=written_pages,
    )
    if overview_update is not None:
        log_action(
            wiki_dir,
            "synthesis_update",
            f"{overview_update['path']} | sources={overview_update['source_count']}",
        )

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
