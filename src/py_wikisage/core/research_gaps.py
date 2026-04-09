"""Plan and run batched gap research (arXiv + optional Tavily)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode
from typing import Iterable

from litellm import completion
from rich.console import Console

from py_wikisage.core.arxiv_client import (
    ARXIV_SORT_BY,
    ARXIV_SORT_ORDER,
    query_to_arxiv_search,
    search_arxiv,
    write_arxiv_clip,
)
from py_wikisage.core.compiler import _parse_json_payload, ingest_file
from py_wikisage.core.config import qmd_collection_name
from py_wikisage.core.llm_utils import build_completion_kwargs
from py_wikisage.core.lint_wiki import collect_broken_wikilink_targets, run_lint
from py_wikisage.core.prompts import get_research_gaps_prompt
from py_wikisage.core.qmd_wrapper import check_qmd_installed, init_qmd_collection, update_qmd_index
from py_wikisage.core.state import log_action
from py_wikisage.core.wiki_index import regenerate_wiki_index


def _research_section(config: dict) -> dict:
    r = config.get("research")
    return r if isinstance(r, dict) else {}


def resolve_web_api_key(config: dict) -> str | None:
    rc = _research_section(config)
    key = rc.get("web_api_key")
    if key:
        return str(key)
    env_name = rc.get("web_api_key_env") or "TAVILY_API_KEY"
    return os.getenv(str(env_name))


def web_provider_name(config: dict) -> str | None:
    p = _research_section(config).get("web_provider")
    if p is None or p == "":
        return None
    return str(p).strip().lower()


def dedupe_arxiv_gap_queries(queries: list[str]) -> list[str]:
    """One arXiv API call per distinct `search_query` (LLM often repeats near-duplicates)."""
    seen_aq: set[str] = set()
    out: list[str] = []
    for q in queries:
        aq = query_to_arxiv_search(q)
        if not aq.strip():
            continue
        k = aq.casefold()
        if k in seen_aq:
            continue
        seen_aq.add(k)
        out.append(q)
    return out


def merge_unique_queries(*lists: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for lst in lists:
        for q in lst:
            s = (q or "").strip()
            if not s:
                continue
            k = s.casefold()
            if k in seen:
                continue
            seen.add(k)
            out.append(s)
    return out


def tavily_search(query: str, api_key: str, max_results: int, timeout: float = 30.0) -> list[dict]:
    """Call Tavily search API; returns list of dicts with url, title, content."""
    n = max(1, min(max_results, 10))
    body = json.dumps(
        {
            "api_key": api_key,
            "query": query,
            "max_results": n,
            "search_depth": "basic",
            # Bias toward recently indexed pages (research-gaps: prefer latest sources).
            "time_range": "year",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    results = payload.get("results") or []
    out: list[dict] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        url = str(r.get("url") or "").strip()
        if not url:
            continue
        out.append(
            {
                "url": url,
                "title": str(r.get("title") or "").strip() or url,
                "content": str(r.get("content") or "").strip(),
            }
        )
    return out


def write_web_clip(result: dict, dest_dir: Path, provider: str) -> Path:
    url = result["url"]
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    path = dest_dir / f"web-{h}.md"
    title = result["title"].replace('"', '\\"')
    esc_url = url.replace("\\", "\\\\").replace('"', '\\"')
    fm = (
        "---\n"
        f'source: web\n'
        f'provider: {provider}\n'
        f'url: "{esc_url}"\n'
        f'title: "{title}"\n'
        "---\n\n"
    )
    body = f"## Snippet\n\n{result['content']}\n\n## Link\n\n[{result['title']}]({url})\n"
    dest_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(fm + body, encoding="utf-8")
    return path


def _arxiv_api_url(search_query: str, max_results: int) -> str:
    params = urlencode(
        {
            "search_query": search_query,
            "start": 0,
            "max_results": max(1, min(max_results, 50)),
            "sortBy": ARXIV_SORT_BY,
            "sortOrder": ARXIV_SORT_ORDER,
        }
    )
    return f"https://export.arxiv.org/api/query?{params}"


def llm_suggest_queries(
    wiki_dir: Path, config: dict, broken_targets: list[str]
) -> list[str]:
    index_path = wiki_dir / "index.md"
    idx = ""
    if index_path.is_file():
        try:
            idx = index_path.read_text(encoding="utf-8", errors="replace")[:12000]
        except OSError:
            idx = ""
    issues, info = run_lint(wiki_dir)
    broken_n = len(broken_targets)
    user = (
        f"## index.md (excerpt)\n\n{idx}\n\n"
        f"## Broken wikilink targets ({broken_n})\n\n"
        + "\n".join(f"- {t}" for t in broken_targets[:40])
        + "\n\n## Lint summary\n\n"
        + "\n".join(info)
        + "\n\n## Other issues (first 15)\n\n"
        + "\n".join(issues[:15])
    )
    template = get_research_gaps_prompt()
    messages = [
        {"role": "system", "content": template},
        {"role": "user", "content": user},
    ]
    kwargs = build_completion_kwargs(
        config, messages, response_format={"type": "json_object"}
    )
    raw = completion(**kwargs).choices[0].message.content or ""
    data = _parse_json_payload(raw, config, "research_gaps_llm")
    if not isinstance(data, dict):
        return []
    qs = data.get("queries")
    if not isinstance(qs, list):
        return []
    return [str(x).strip() for x in qs if str(x).strip()]


def run_research_gaps(
    cwd: Path,
    wiki_dir: Path,
    raw_dir: Path,
    config: dict,
    *,
    apply: bool,
    max_results: int,
    sources: set[str],
    limit_queries: int,
    llm_gaps: bool,
    console: Console,
) -> None:
    max_results = max(1, min(int(max_results), 50))
    limit_queries = max(1, int(limit_queries))

    broken = collect_broken_wikilink_targets(wiki_dir)
    llm_q: list[str] = []
    if llm_gaps:
        console.print("[blue]Requesting LLM gap queries...[/blue]")
        llm_q = llm_suggest_queries(wiki_dir, config, broken)
    queries = merge_unique_queries(broken, llm_q)[: max(1, limit_queries)]

    if not queries:
        console.print("[yellow]No gap queries (no broken wikilinks and no LLM suggestions).[/yellow]")
        return

    use_arxiv = "arxiv" in sources
    use_web = "web" in sources
    web_key = resolve_web_api_key(config) if use_web else None
    provider = web_provider_name(config)

    if use_web and not web_key:
        console.print(
            "[dim]Web search skipped: configure research.web_api_key_env (e.g. TAVILY_API_KEY) "
            "or research.web_api_key in config.yaml.[/dim]"
        )
        use_web = False
    if use_web and provider != "tavily":
        console.print(
            f"[dim]Web search skipped: research.web_provider is {provider!r}; only 'tavily' is supported in this MVP.[/dim]"
        )
        use_web = False

    if not use_arxiv and not use_web:
        console.print(
            "[yellow]No active fetch backends (use --sources arxiv and/or configure Tavily web search).[/yellow]"
        )

    clips_dir = raw_dir / "web_clips"
    console.print(f"[bold]Planned queries ({len(queries)}):[/bold]")
    seen_arxiv_aq: set[str] = set()
    for q in queries:
        console.print(f"  • {q}")
        if use_arxiv:
            aq = query_to_arxiv_search(q)
            k = aq.casefold()
            if k not in seen_arxiv_aq:
                seen_arxiv_aq.add(k)
                console.print(f"    [dim]arxiv[/dim] {aq}")
                console.print(f"    [dim]GET[/dim] {_arxiv_api_url(aq, max_results)}")
                console.print(
                    f"    [dim]arXiv results: newest submissions first (sort={ARXIV_SORT_BY}); "
                    f"requests spaced ≥3s[/dim]"
                )
                console.print(
                    f"    [dim]would write up to {max_results} file(s) under {clips_dir.relative_to(cwd)}/<arxiv_id>.md[/dim]"
                )
            else:
                console.print(
                    f"    [dim]arxiv[/dim] {aq} (same search as above; skipped in --apply)"
                )
        if use_web:
            console.print(
                f"    [dim]web (tavily, time_range=year)[/dim] up to {max_results} clip(s) → "
                f"{clips_dir.relative_to(cwd)}/web-<hash>.md"
            )

    if not apply:
        console.print("\n[green]Dry run only.[/green] Use [bold]--apply[/bold] to fetch and ingest.")
        log_action(
            wiki_dir,
            "research_gap",
            f"dry-run plan: {len(queries)} quer(ies), sources={','.join(sorted(sources))}",
        )
        return

    if not use_arxiv and not use_web:
        return

    written: list[Path] = []
    arxiv_seen: set[str] = set()
    web_seen_urls: set[str] = set()

    arxiv_fetch_labels = dedupe_arxiv_gap_queries(queries) if use_arxiv else []
    if use_arxiv and len(arxiv_fetch_labels) < len(queries):
        console.print(
            f"[dim]arXiv: {len(arxiv_fetch_labels)} unique search(es) "
            f"(from {len(queries)} gap targets)[/dim]"
        )

    if use_arxiv:
        for q in arxiv_fetch_labels:
            aq = query_to_arxiv_search(q)
            try:
                entries = search_arxiv(aq, max_results=max_results)
            except (urllib.error.URLError, OSError, TimeoutError, urllib.error.HTTPError) as e:
                console.print(f"[red]arXiv fetch failed for {q!r}: {e}[/red]")
                entries = []
            for ent in entries:
                if ent.arxiv_id in arxiv_seen:
                    continue
                arxiv_seen.add(ent.arxiv_id)
                safe = re.sub(r'[<>:"/\\|?*]', "_", ent.arxiv_id)
                path = clips_dir / f"{safe}.md"
                if path.is_file():
                    console.print(f"[dim]skip existing {path.relative_to(cwd)}[/dim]")
                    continue
                write_arxiv_clip(ent, clips_dir)
                written.append(path)
                console.print(f"[green]wrote[/green] {path.relative_to(cwd)}")

    if use_web and web_key:
        for q in queries:
            try:
                wres = tavily_search(q, web_key, max_results=max_results)
            except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as e:
                console.print(f"[red]Web search failed for {q!r}: {e}[/red]")
                wres = []
            for r in wres:
                u = r["url"]
                if u in web_seen_urls:
                    continue
                web_seen_urls.add(u)
                dest = clips_dir / f"web-{hashlib.sha256(u.encode('utf-8')).hexdigest()[:16]}.md"
                if dest.is_file():
                    console.print(f"[dim]skip existing {dest.relative_to(cwd)}[/dim]")
                    continue
                out = write_web_clip(r, clips_dir, "tavily")
                written.append(out)
                console.print(f"[green]wrote[/green] {out.relative_to(cwd)}")

    ingested = 0
    for path in written:
        try:
            ingest_file(raw_dir, path.resolve(), wiki_dir, config)
            ingested += 1
        except Exception as e:
            console.print(f"[red]ingest failed for {path}: {e}[/red]")

    index_path = regenerate_wiki_index(wiki_dir)
    if index_path:
        console.print(f"[dim]Updated {index_path.relative_to(cwd)}[/dim]")

    log_action(
        wiki_dir,
        "research_fetch",
        f"apply: {ingested} file(s) ingested from web_clips, {len(written)} written",
    )

    if check_qmd_installed():
        coll = qmd_collection_name(config, cwd)
        init_qmd_collection(wiki_dir, coll)
        update_qmd_index(coll)
    console.print("[green]research-gaps apply finished.[/green]")
