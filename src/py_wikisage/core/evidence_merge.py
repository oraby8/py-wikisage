"""Helpers for confidence-weighted merge and contradiction notes."""

from __future__ import annotations

import re
from datetime import datetime


def normalize_title(value: str) -> str:
    s = value.strip().casefold()
    s = re.sub(r"[^\w\s-]+", " ", s)
    s = re.sub(r"[-_]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def title_similarity(a: str, b: str) -> float:
    """Token Jaccard title similarity in [0, 1] with acronym/paren aliases."""

    def aliases(s: str) -> set[str]:
        out = {normalize_title(s)}
        m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", s.strip())
        if m:
            before, inside = m.group(1).strip(), m.group(2).strip()
            out.add(normalize_title(before))
            out.add(normalize_title(inside))
            out.add(normalize_title(f"{inside} ({before})"))
        return {x for x in out if x}

    best = 0.0
    for av in aliases(a):
        ta = set(av.split())
        if not ta:
            continue
        for bv in aliases(b):
            tb = set(bv.split())
            if not tb:
                continue
            inter = len(ta & tb)
            union = len(ta | tb)
            if union:
                best = max(best, inter / union)
    return best


def parse_confidence(value: object, default: float = 0.55) -> float:
    if isinstance(value, (int, float)):
        v = float(value)
        if 0.0 <= v <= 1.0:
            return v
    if isinstance(value, str):
        m = re.search(r"([01](?:\.\d+)?)", value)
        if m:
            v = float(m.group(1))
            if 0.0 <= v <= 1.0:
                return v
    return default


def choose_merge_action(requested_action: str, similarity: float, confidence: float) -> str:
    """
    Confidence-weighted decision:
    - explicit updates stay updates
    - high overlap becomes update
    - medium overlap only creates when confidence is strong
    """
    action = (requested_action or "").strip().lower()
    if action == "update":
        return "update"
    if similarity >= 0.72:
        return "update"
    if similarity >= 0.50 and confidence < 0.80:
        return "update"
    return "create"


def format_contradiction_note(source: str, reason: str, confidence: float) -> str:
    day = datetime.now().strftime("%Y-%m-%d")
    return (
        f"- [{day}] source: {source}; confidence={confidence:.2f}; note: {reason}\n"
    )


def ensure_contradictions_section(content: str, note: str) -> str:
    marker = "## Contradictions / updates"
    text = content.rstrip() + "\n"
    if marker in text:
        return text + ("\n" if not text.endswith("\n") else "") + note
    return f"{text}\n{marker}\n\n{note}"
