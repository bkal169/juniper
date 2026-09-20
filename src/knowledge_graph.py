"""Entity + relation extraction from brain_thoughts → kg_nodes / kg_edges.

Cheap-model call order (first success wins):
  1. Gemma via local Ollama   — free, fastest
  2. MiniMax cloud            — free tier
  3. Kimi K3 (1M ctx)         — via MOONSHOT_API_KEY, $3/$15 per Mtok
                                (T6/#43 2026-07-17 bump — was K2.6 at $0.6/Mtok in)
  4. Empty result             — silent degradation

Run via:   python -m src.knowledge_graph
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

import httpx

from .utils.circuit_breaker import CircuitBreaker, CircuitOpenError
from .utils import fallback_search
from .utils import wal

logger = logging.getLogger(__name__)

# Module-level circuit breaker — shared across all calls in this process
_cb = CircuitBreaker(
    failure_threshold=3,
    failure_window_s=60.0,
    recovery_timeout_s=30.0,
    call_timeout_s=3.0,
)


@dataclass
class Entity:
    label: str
    entity_type: str
    confidence: float


@dataclass
class Relation:
    source_label: str
    target_label: str
    relation_type: str
    confidence: float


EXTRACTION_PROMPT = """You extract entities and relations from a thought.
Return ONLY JSON, no prose:
{
  "entities": [{"label": "", "entity_type": "person|company|project|concept|tool|location|agent", "confidence": 0.0}],
  "relations": [{"source_label": "", "target_label": "", "relation_type": "works_at|uses|owns|mentions|relates_to|reports_to", "confidence": 0.0}]
}
Keep only high-signal items (confidence >= 0.6). Skip generic words."""


def _sb_url() -> str:
    return os.environ.get("SUPABASE_URL", "").rstrip("/")


def _sb_key() -> str:
    return os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _sb_headers(extra: dict | None = None) -> dict[str, str]:
    key = _sb_key()
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _try_ollama(text: str) -> dict | None:
    """Try local Ollama/Gemma. Returns parsed dict or None on failure."""
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    try:
        r = httpx.post(
            f"{ollama_url}/chat/completions",
            json={
                "model": os.environ.get("OLLAMA_MODEL", "gemma3:4b"),
                "messages": [
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user",   "content": text},
                ],
                "max_tokens": 800,
            },
            timeout=30,
        )
        r.raise_for_status()
        return _parse_json(r.json()["choices"][0]["message"]["content"])
    except Exception:
        return None


def _try_minimax(text: str) -> dict | None:
    """Try MiniMax cloud (free tier). Returns parsed dict or None on failure."""
    mm_key = os.environ.get("MINIMAX_API_KEY")
    if not mm_key:
        return None
    try:
        r = httpx.post(
            "https://api.minimax.chat/v1/chat/completions",
            headers={"Authorization": f"Bearer {mm_key}"},
            json={
                "model": os.environ.get("MINIMAX_MODEL", "MiniMax-Text-01"),
                "messages": [
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user",   "content": text},
                ],
                "max_tokens": 800,
            },
            timeout=30,
        )
        r.raise_for_status()
        return _parse_json(r.json()["choices"][0]["message"]["content"])
    except Exception:
        return None


def _try_kimi(text: str) -> dict | None:
    """Try Kimi K3 via the Moonshot native API (1M context, $3/$15 per Mtok).
    Falls back here when both Gemma and MiniMax are unavailable.

    NOTE: this hits Moonshot's own native API (api.moonshot.cn), not
    OpenRouter — its model-naming convention is the bare "kimi-k3" (no
    "moonshotai/" provider prefix; that prefix is OpenRouter-specific and is
    NOT a valid native Moonshot model id). T6/#43 (2026-07-17): default
    bumped from "kimi-k2" to the verified native-API name "kimi-k3"
    (platform.kimi.ai/docs/guide/kimi-k3-quickstart, 2026-07-16 release).
    If KIMI_MODEL is set for the OpenRouter-routed callers elsewhere in the
    fleet (moonshotai/kimi-k3), that same value would be wrong here — this
    function intentionally does NOT share KIMI_MODEL with the OpenRouter
    call sites; it reads its own env var so the two naming conventions never
    collide.
    """
    moonshot_key = os.environ.get("MOONSHOT_API_KEY")
    if not moonshot_key:
        return None
    kimi_model = os.environ.get("MOONSHOT_MODEL", "kimi-k3")
    try:
        r = httpx.post(
            "https://api.moonshot.cn/v1/chat/completions",
            headers={"Authorization": f"Bearer {moonshot_key}"},
            json={
                "model": kimi_model,
                "messages": [
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user",   "content": text},
                ],
                "max_tokens": 800,
            },
            timeout=30,
        )
        r.raise_for_status()
        return _parse_json(r.json()["choices"][0]["message"]["content"])
    except Exception:
        return None


def _call_cheap_model(text: str) -> dict:
    """Try cheap models in tier order: Gemma → MiniMax → Kimi K3 → empty."""
    result = _try_ollama(text)
    if result is not None:
        return result

    result = _try_minimax(text)
    if result is not None:
        return result

    result = _try_kimi(text)
    if result is not None:
        logger.debug("[knowledge_graph] used Kimi K3 for extraction (Gemma+MiniMax unavailable)")
        return result

    logger.warning("[knowledge_graph] all cheap models unavailable — returning empty extraction")
    return {"entities": [], "relations": []}


def _parse_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"entities": [], "relations": []}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"entities": [], "relations": []}


def extract_from_thought(text: str) -> tuple[list[Entity], list[Relation]]:
    data = _call_cheap_model(text)
    entities = [
        Entity(
            label=e["label"].strip(),
            entity_type=e.get("entity_type", "concept"),
            confidence=float(e.get("confidence", 0.0)),
        )
        for e in data.get("entities", [])
        if e.get("label") and float(e.get("confidence", 0.0)) >= 0.6
    ]
    relations = [
        Relation(
            source_label=r["source_label"].strip(),
            target_label=r["target_label"].strip(),
            relation_type=r.get("relation_type", "relates_to"),
            confidence=float(r.get("confidence", 0.0)),
        )
        for r in data.get("relations", [])
        if r.get("source_label") and r.get("target_label") and float(r.get("confidence", 0.0)) >= 0.6
    ]
    return entities, relations


def _do_upsert(entities: list[Entity], relations: list[Relation]) -> None:
    """Raw Supabase write via httpx REST — called directly or via circuit breaker."""
    url = _sb_url()
    if not url or not _sb_key():
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
    upsert_headers = _sb_headers({"Prefer": "return=minimal,resolution=merge-duplicates"})
    insert_headers = _sb_headers({"Prefer": "return=minimal"})
    with httpx.Client(timeout=10.0) as client:
        for e in entities:
            client.post(
                f"{url}/rest/v1/kg_nodes",
                headers=upsert_headers,
                json={"label": e.label, "node_type": e.entity_type, "confidence": e.confidence},
            ).raise_for_status()
        for r in relations:
            client.post(
                f"{url}/rest/v1/kg_edges",
                headers=insert_headers,
                json={
                    "source_label":  r.source_label,
                    "target_label":  r.target_label,
                    "relation_type": r.relation_type,
                    "confidence":    r.confidence,
                },
            ).raise_for_status()


def upsert_graph(entities: list[Entity], relations: list[Relation], thought_id: str | None = None) -> None:
    if not entities and not relations:
        return

    entry_id = wal.wal_append({
        "type": "upsert_graph",
        "thought_id": str(thought_id) if thought_id else None,
        "entities": [
            {"label": e.label, "entity_type": e.entity_type, "confidence": e.confidence}
            for e in entities
        ],
        "relations": [
            {
                "source_label": r.source_label,
                "target_label": r.target_label,
                "relation_type": r.relation_type,
                "confidence": r.confidence,
            }
            for r in relations
        ],
    })

    try:
        _cb.call(_do_upsert, entities, relations)
        wal.wal_commit(entry_id)
    except (CircuitOpenError, TimeoutError) as exc:
        logger.warning("upsert_graph skipped (circuit open / timeout): %s", exc)
        raise
    except Exception:
        raise


def _replay_wal_entry(entry: dict) -> None:
    """Reconstruct and re-submit a single uncommitted WAL entry."""
    entities = [
        Entity(label=e["label"], entity_type=e["entity_type"], confidence=e["confidence"])
        for e in entry.get("entities", [])
    ]
    relations = [
        Relation(
            source_label=r["source_label"],
            target_label=r["target_label"],
            relation_type=r["relation_type"],
            confidence=r["confidence"],
        )
        for r in entry.get("relations", [])
    ]
    _do_upsert(entities, relations)
    wal.wal_commit(entry["_wal_id"])
    logger.info("WAL replayed entry %s (thought_id=%s)", entry["_wal_id"], entry.get("thought_id"))


def process_recent(limit: int = 50) -> int:
    for entry in wal.wal_replay():
        if entry.get("type") == "upsert_graph":
            try:
                _replay_wal_entry(entry)
            except Exception as exc:
                logger.warning("WAL replay failed for %s: %s", entry.get("_wal_id"), exc)

    url = _sb_url()
    key = _sb_key()

    try:
        def _fetch() -> list[dict]:
            resp = httpx.get(
                f"{url}/rest/v1/thoughts",
                headers=_sb_headers(),
                params={
                    "select": "id,content,metadata",
                    "order":  "created_at.desc",
                    "limit":  str(limit),
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()

        rows: list[dict] = _cb.call(_fetch)
        fallback_search.cache_thoughts(rows)

    except CircuitOpenError:
        logger.warning("[knowledge_graph] Supabase circuit OPEN — using keyword fallback cache")
        rows = fallback_search.keyword_search_fallback("")
    except Exception as exc:
        logger.error("[knowledge_graph] fetch failed: %s", exc)
        return 0

    processed = 0
    for row in rows:
        meta = row.get("metadata") or {}
        if meta.get("kg_extracted"):
            continue
        # Column is 'content' in the thoughts table (not 'thought')
        content = row.get("content") or ""
        if not content:
            continue
        entities, relations = extract_from_thought(content)
        try:
            upsert_graph(entities, relations, thought_id=row.get("id"))
        except (CircuitOpenError, TimeoutError):
            logger.warning("[knowledge_graph] circuit open — skipping remaining rows")
            break
        except Exception as exc:
            logger.error("[knowledge_graph] upsert failed for row %s: %s", row.get("id"), exc)
            continue

        try:
            updated_meta = {**meta, "kg_extracted": True, "kg_entities": len(entities), "kg_relations": len(relations)}

            def _mark(row_id: str, m: dict) -> None:
                httpx.patch(
                    f"{url}/rest/v1/thoughts",
                    headers=_sb_headers({"Prefer": "return=minimal"}),
                    params={"id": f"eq.{row_id}"},
                    json={"metadata": m},
                    timeout=10.0,
                ).raise_for_status()

            _cb.call(_mark, row["id"], updated_meta)
        except (CircuitOpenError, TimeoutError):
            logger.warning("[knowledge_graph] circuit open — could not mark row %s", row.get("id"))
            break

        processed += 1
    return processed


if __name__ == "__main__":
    n = process_recent()
    print(f"[knowledge_graph] processed {n} thoughts")
