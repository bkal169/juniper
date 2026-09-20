"""BM25-style keyword fallback for when pgvector / Supabase is unavailable.

The cache is a local JSONL file populated during normal operation.
On circuit OPEN, callers use keyword_search_fallback() instead.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_CACHE_FILE = Path(__file__).parent.parent.parent.parent / "data" / "thought_cache.jsonl"


# ------------------------------------------------------------------
# Cache population (call during normal operation)
# ------------------------------------------------------------------

def cache_thoughts(thoughts: list[dict]) -> None:
    """Append thoughts to the local cache, deduplicating by id."""
    if not thoughts:
        return
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing_ids: set[str] = set()
    if _CACHE_FILE.exists():
        for line in _CACHE_FILE.read_text(encoding="utf-8").splitlines():
            try:
                existing_ids.add(str(json.loads(line)["id"]))
            except (json.JSONDecodeError, KeyError):
                pass

    with _CACHE_FILE.open("a", encoding="utf-8") as fh:
        for t in thoughts:
            if str(t.get("id", "")) not in existing_ids:
                fh.write(json.dumps(t) + "\n")


# ------------------------------------------------------------------
# Fallback search
# ------------------------------------------------------------------

def keyword_search_fallback(query: str) -> list[dict]:
    """Return up to 10 cached thoughts ranked by BM25-style term overlap.

    Returns an empty list if the cache doesn't exist or query is blank.
    """
    if not _CACHE_FILE.exists():
        return []

    query_terms = set(_tokenise(query))
    if not query_terms:
        # No query → return most-recent cached entries
        return _load_all()[-10:]

    scored: list[tuple[float, dict]] = []
    seen_ids: set[str] = set()

    for doc in _load_all():
        doc_id = str(doc.get("id", ""))
        if doc_id in seen_ids:
            continue
        seen_ids.add(doc_id)

        doc_terms = set(_tokenise(doc.get("thought", "")))
        if not doc_terms:
            continue

        overlap = query_terms & doc_terms
        if not overlap:
            continue

        # Approximate BM25 score: term precision weighted by IDF-proxy (1/freq)
        score = sum(1.0 / max(1, doc_terms.count(t)) for t in overlap) / len(query_terms)
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:10]]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _tokenise(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _load_all() -> list[dict]:
    docs: list[dict] = []
    for line in _CACHE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            docs.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return docs
