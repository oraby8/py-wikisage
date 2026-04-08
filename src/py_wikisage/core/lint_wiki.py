"""Cheap wiki health checks: wikilinks and orphan pages."""

from __future__ import annotations

import re
from pathlib import Path
from collections import defaultdict

from py_wikisage.core.wiki_index import is_meta_wiki_file

WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+\.md)\)")


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


def run_lint(wiki_dir: Path) -> tuple[list[str], list[str]]:
    """
    Returns (issues, info_lines) where issues are problems, info is summary stats.
    """
    if not wiki_dir.is_dir():
        return ([f"Wiki directory does not exist: {wiki_dir}"], [])

    valid_keys: set[str] = set()
    file_by_stem: dict[str, str] = {}

    for path in wiki_dir.rglob("*.md"):
        if is_meta_wiki_file(path, wiki_dir):
            continue
        valid_keys.add(_normalize_key(path.stem))
        file_by_stem[_normalize_key(path.stem)] = str(path.relative_to(wiki_dir))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("#"):
                valid_keys.add(_normalize_key(s.lstrip("#").strip()))
                break

    inbound: dict[str, int] = defaultdict(int)
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
            inbound[_normalize_key(Path(fname).stem)] += 1

    for path in wiki_dir.rglob("*.md"):
        if is_meta_wiki_file(path, wiki_dir):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for target in _link_targets(text):
            key = _normalize_key(target)
            inbound[key] += 1
            if key not in valid_keys:
                issues.append(
                    f"Broken wikilink in {path.relative_to(wiki_dir)!s}: [[{target}]] (no matching page)"
                )

    orphans: list[str] = []
    for path in wiki_dir.rglob("*.md"):
        if is_meta_wiki_file(path, wiki_dir):
            continue
        stem_key = _normalize_key(path.stem)
        if inbound.get(stem_key, 0) == 0:
            orphans.append(str(path.relative_to(wiki_dir)))

    for o in orphans:
        issues.append(f"Orphan page (no inbound wikilinks or index link): {o}")

    n_pages = len(file_by_stem)
    n_broken = sum(1 for i in issues if i.startswith("Broken"))
    info = [
        f"Pages scanned: {n_pages}",
        f"Broken link reports: {n_broken}",
        f"Orphan pages: {len(orphans)}",
    ]
    return issues, info
