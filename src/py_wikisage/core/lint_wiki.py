"""Cheap wiki health checks: wikilinks and orphan pages."""

from __future__ import annotations

import re
from pathlib import Path
from collections import defaultdict

from py_wikisage.core.wiki_index import is_meta_wiki_file

WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+\.md)\)")
# Short token that looks like an acronym (ASR, LLM, F5-TTS, UTMOS)
_ACRONYMISH = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,20}$")


def _link_targets(raw: str) -> list[str]:
    targets: list[str] = []
    for match in WIKILINK.finditer(raw):
        inner = match.group(1).strip()
        if "|" in inner:
            inner = inner.split("|", 1)[0].strip()
        targets.append(inner)
    return targets


def _normalize_key(name: str) -> str:
    s = name.strip()
    if s.lower().endswith(".md"):
        s = s[:-3]
    return s.casefold()


def _fuzzy_key(name: str) -> str:
    """Loosen punctuation so F5-TTS and F5 TTS match."""
    s = _normalize_key(name)
    s = re.sub(r"[-_.]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _expand_title_variants(title: str) -> set[str]:
    """
    All normalized/fuzzy keys that should count as this page title for link resolution.
    Handles:
    - Full title
    - "Long Name (ACRONYM)" <-> "ACRONYM (Long Name)"
    - Fuzzy punctuation variants
    """
    keys: set[str] = set()
    t = title.strip()
    if not t:
        return keys

    keys.add(_normalize_key(t))
    keys.add(_fuzzy_key(t))

    m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", t)
    if not m:
        return keys

    before, ins = m.group(1).strip(), m.group(2).strip()
    keys.add(_normalize_key(before))
    keys.add(_normalize_key(ins))
    keys.add(_fuzzy_key(before))
    keys.add(_fuzzy_key(ins))

    b_ns = before.replace(" ", "")
    i_ns = ins.replace(" ", "")

    # "Long Name (ACRONYM)" <-> "ACRONYM (Long Name)"; same formula covers both
    if _ACRONYMISH.fullmatch(i_ns) or _ACRONYMISH.fullmatch(b_ns):
        rev = f"{ins} ({before})"
        keys.add(_normalize_key(rev))
        keys.add(_fuzzy_key(rev))

    return keys


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()
    return ""


def run_lint(wiki_dir: Path) -> tuple[list[str], list[str]]:
    """
    Returns (issues, info_lines) where issues are problems, info is summary stats.
    """
    if not wiki_dir.is_dir():
        return ([f"Wiki directory does not exist: {wiki_dir}"], [])

    # Every string that can resolve a wikilink target
    valid_keys: set[str] = set()
    # Per page: keys that count as "this page" for orphan detection
    page_resolve_keys: list[tuple[Path, set[str]]] = []
    file_by_stem: dict[str, str] = {}

    for path in wiki_dir.rglob("*.md"):
        if is_meta_wiki_file(path, wiki_dir):
            continue
        file_by_stem[_normalize_key(path.stem)] = str(path.relative_to(wiki_dir))
        aliases: set[str] = set()
        aliases |= _expand_title_variants(path.stem)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        h1 = _first_heading(text)
        if h1:
            aliases |= _expand_title_variants(h1)
        valid_keys |= aliases
        page_resolve_keys.append((path, aliases))

    inbound: dict[str, int] = defaultdict(int)
    broken_seen: set[tuple[str, str]] = set()
    issues: list[str] = []

    index_path = wiki_dir / "index.md"
    if index_path.is_file():
        try:
            idx_text = index_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            idx_text = ""
        for m in MD_LINK.finditer(idx_text):
            raw_target = m.group(1).strip()
            fname = raw_target.split("/")[-1]
            stem = Path(fname).stem
            for k in _expand_title_variants(stem):
                inbound[k] += 1

    for path in wiki_dir.rglob("*.md"):
        if is_meta_wiki_file(path, wiki_dir):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(wiki_dir))
        for target in _link_targets(text):
            for k in _expand_title_variants(target):
                inbound[k] += 1
            if not (_expand_title_variants(target) & valid_keys):
                dedupe_key = (rel, target)
                if dedupe_key not in broken_seen:
                    broken_seen.add(dedupe_key)
                    issues.append(
                        f"Broken wikilink in {rel!s}: [[{target}]] (no matching page)"
                    )

    orphans: list[str] = []
    for path, aliases in page_resolve_keys:
        total = sum(inbound.get(k, 0) for k in aliases)
        if total == 0:
            orphans.append(str(path.relative_to(wiki_dir)))

    for o in orphans:
        issues.append(f"Orphan page (no inbound wikilinks or index link): {o}")

    n_pages = len(file_by_stem)
    n_broken = len(broken_seen)
    info = [
        f"Pages scanned: {n_pages}",
        f"Broken link reports: {n_broken}",
        f"Orphan pages: {len(orphans)}",
    ]
    return issues, info
