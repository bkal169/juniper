"""Capability-based task router driven by ``workflows/agents/MANIFEST.json``.

Implements the auto-routing recipe documented in ``workflows/agents/MANIFEST.md``
section *Auto-routing recipe (for Juniper)*:

  1. Match incoming task verb to a capability key
     (e.g. ``draft a foundation letter`` -> ``founder-letter-drafting``).
  2. Read the agent id from ``_index_by_capability``.
  3. Read the agent's ``governance_gates`` and attach them to the call pipeline.
  4. Read ``cost_tier`` -> map to ``_cost_tier_legend`` -> set the call's model.
  5. Read ``mode`` -> route through HITL queue if ``supervised``, run direct if
     ``autonomous``.

The manifest is loaded at startup and memoized on file mtime — any in-place
edit to MANIFEST.json invalidates the cache on the next call. This means
Juniper picks up new agents / capability changes without a restart.

Three resolution strategies are exposed for the *capability matching* step
because incoming task descriptions vary:

* :func:`route_capability` — exact capability key (fast path)
* :func:`route_by_keywords` — fuzzy: scan a free-text task description for
  substring overlap against capability keys, return best match
* :func:`route_by_agent` — short-circuit: caller already knows the agent id

When no capability matches, or when multiple agents share the capability with
equal weight, the router returns ``None`` so the caller can escalate to Alan
via HITL (per the recipe's "no agent matches OR multiple agents match
equally" rule from the wiring brief).

Created 2026-05-10 by voice-drift-and-manifest wiring task —
implements Juniper's MANIFEST-driven capability dispatch.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


# --- Constants ----------------------------------------------------------------

#: Default location of the manifest relative to the repo root. Resolved up
#: from ``juniper/src/manifest_router.py`` so the module works regardless of
#: where the process is started from.
DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent.parent  # ../.. = repo root
    / "workflows" / "agents" / "MANIFEST.json"
)

#: Map ``cost_tier`` legend keys -> Anthropic model id env var (with sensible
#: defaults). The Python side mirrors ``MODEL_HAIKU`` / ``MODEL_SONNET`` /
#: ``MODEL_OPUS`` from ``juniper/src/model_router.py`` so a single env var
#: change moves both routers.
DEFAULT_MODEL_BY_COST_TIER: dict[str, str | None] = {
    "haiku-eligible": os.environ.get("MODEL_HAIKU", "claude-haiku-4-5-20251001"),
    "sonnet-default": os.environ.get("MODEL_SONNET", "claude-sonnet-4-6"),
    "opus-required": os.environ.get("MODEL_OPUS", "claude-opus-4-6"),
    "infrastructure": None,  # Mycelium = substrate, no model assignment
}


# --- Data shapes --------------------------------------------------------------

@dataclass
class RouteDecision:
    """Result of a capability lookup."""

    agent_id: str
    """Resolved agent id (e.g., ``"rose"``)."""

    capability: str
    """The capability key that matched."""

    model: str | None
    """Resolved Anthropic model id (or ``None`` for substrate)."""

    cost_tier: str
    """Cost-tier legend key (e.g., ``"opus-required"``)."""

    governance_gates: list[str]
    """Gate ids that the call pipeline must attach (e.g., ``["rose-voice-lock"]``)."""

    mode: str
    """``"supervised"`` / ``"autonomous"`` / ``"substrate"``."""

    requires_hitl: bool
    """True when ``mode == "supervised"`` — caller must route through HITL."""

    domain: str
    """Functional domain (e.g., ``"creative"``, ``"orchestration"``)."""

    soul_doc_path: str | None
    """Canonical agent doc path for downstream prompt-cache or context loads."""

    notes: str | None = None
    """Free-text notes from the manifest record (``agent.notes``)."""


@dataclass
class _CachedManifest:
    """Internal cache shape — reloaded when MANIFEST.json mtime changes."""

    raw: dict
    mtime_ns: int
    path: Path

    # Pre-computed lookups (kept in sync with raw on reload)
    capability_index: dict[str, list[str]] = field(default_factory=dict)
    domain_index: dict[str, list[str]] = field(default_factory=dict)
    governance_gate_index: dict[str, list[str]] = field(default_factory=dict)
    cost_tier_index: dict[str, list[str]] = field(default_factory=dict)
    agents_by_id: dict[str, dict] = field(default_factory=dict)


# --- Module-level cache state -------------------------------------------------

_CACHE: _CachedManifest | None = None
_CACHE_LOCK = threading.Lock()


# --- Loader -------------------------------------------------------------------

def _load(path: Path) -> _CachedManifest:
    """Read MANIFEST.json from disk and pre-compute lookup indexes."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    mtime_ns = path.stat().st_mtime_ns

    cap_idx = dict(raw.get("_index_by_capability") or {})
    dom_idx = dict(raw.get("_index_by_domain") or {})
    gate_idx = dict(raw.get("_index_by_governance_gate") or {})
    cost_idx = dict(raw.get("_index_by_cost_tier") or {})
    agents_by_id = {a["id"]: a for a in raw.get("agents", []) if "id" in a}

    return _CachedManifest(
        raw=raw,
        mtime_ns=mtime_ns,
        path=path,
        capability_index=cap_idx,
        domain_index=dom_idx,
        governance_gate_index=gate_idx,
        cost_tier_index=cost_idx,
        agents_by_id=agents_by_id,
    )


def get_manifest(path: Path | str | None = None) -> _CachedManifest:
    """Return the parsed manifest cache, reloading on mtime change.

    Thread-safe via a module-level lock. The caller never mutates the cache.
    Pass ``path`` to override the default location (useful in tests).
    """
    target = Path(path) if path else DEFAULT_MANIFEST_PATH
    with _CACHE_LOCK:
        global _CACHE
        try:
            current_mtime = target.stat().st_mtime_ns
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"MANIFEST.json not found at {target}. The capability router "
                f"requires it (per workflows/agents/MANIFEST.md). Generate via "
                f"`workflows/agents/MANIFEST.json` or pass an explicit path."
            ) from exc

        if _CACHE is None or _CACHE.path != target or _CACHE.mtime_ns != current_mtime:
            logger.info(
                "[manifest_router] (re)loading %s (mtime_ns=%d, prev=%s)",
                target, current_mtime,
                _CACHE.mtime_ns if _CACHE else "cold",
            )
            _CACHE = _load(target)
            n_agents = len(_CACHE.agents_by_id)
            n_caps = len(_CACHE.capability_index)
            n_gates = len(_CACHE.governance_gate_index)
            logger.info(
                "[manifest_router] loaded: %d agents, %d capabilities, %d gates",
                n_agents, n_caps, n_gates,
            )
        return _CACHE


def reload_manifest(path: Path | str | None = None) -> _CachedManifest:
    """Force a reload regardless of mtime — useful in tests + manual triggers."""
    target = Path(path) if path else DEFAULT_MANIFEST_PATH
    with _CACHE_LOCK:
        global _CACHE
        _CACHE = _load(target)
        return _CACHE


# --- Internal: route construction --------------------------------------------

def _build_decision(
    cache: _CachedManifest,
    agent_id: str,
    capability: str,
) -> RouteDecision | None:
    """Materialize a RouteDecision from an agent record + capability."""
    agent = cache.agents_by_id.get(agent_id)
    if agent is None:
        logger.warning(
            "[manifest_router] capability=%r resolved to agent_id=%r but no "
            "agent record exists for that id (manifest desync).",
            capability, agent_id,
        )
        return None

    cost_tier = (agent.get("cost_tier") or "sonnet-default").strip()
    model_default = agent.get("model_default")
    if model_default is None:
        # Fall back to env-var-driven default if the manifest didn't pin a model.
        model_default = DEFAULT_MODEL_BY_COST_TIER.get(cost_tier)

    mode = (agent.get("mode") or "supervised").strip()
    return RouteDecision(
        agent_id=agent_id,
        capability=capability,
        model=model_default,
        cost_tier=cost_tier,
        governance_gates=list(agent.get("governance_gates") or []),
        mode=mode,
        requires_hitl=(mode == "supervised"),
        domain=agent.get("domain") or "unknown",
        soul_doc_path=agent.get("soul_doc_path"),
        notes=agent.get("notes"),
    )


# --- Public API: capability resolution ----------------------------------------

def route_capability(
    capability: str,
    *,
    manifest_path: Path | str | None = None,
    multi: bool = False,
) -> RouteDecision | list[RouteDecision] | None:
    """Resolve an exact capability key to a routing decision.

    Returns ``None`` when:
      * no agent declares the capability, OR
      * ``multi=False`` (default) AND multiple agents declare it with equal
        weight (caller must escalate to Alan / HITL — the manifest doesn't
        currently rank ties)

    When ``multi=True``, returns a list of all matching agents (or ``[]`` if
    none). This is the path for callers that want to fan out the same task
    to multiple agents (e.g. cross-checking).
    """
    if not capability:
        return [] if multi else None

    cache = get_manifest(manifest_path)
    candidates = cache.capability_index.get(capability) or []

    if multi:
        out: list[RouteDecision] = []
        for aid in candidates:
            d = _build_decision(cache, aid, capability)
            if d is not None:
                out.append(d)
        return out

    if not candidates:
        logger.debug(
            "[manifest_router] capability=%r matched no agents — caller "
            "should escalate to Alan", capability,
        )
        return None
    if len(candidates) > 1:
        logger.info(
            "[manifest_router] capability=%r matched %d agents (%s) — "
            "tie; returning None to force HITL escalation",
            capability, len(candidates), ",".join(candidates),
        )
        return None

    return _build_decision(cache, candidates[0], capability)


def route_by_agent(
    agent_id: str,
    *,
    manifest_path: Path | str | None = None,
) -> RouteDecision | None:
    """Short-circuit: caller already knows which agent. Returns the
    decision (model, gates, mode) for that agent's *first* declared
    capability — useful for pure cost/gate/mode lookups when the
    capability is implicit. Returns ``None`` if the agent isn't in the
    manifest.
    """
    cache = get_manifest(manifest_path)
    agent = cache.agents_by_id.get(agent_id)
    if agent is None:
        return None
    caps = agent.get("capabilities") or []
    placeholder_cap = caps[0] if caps else "(unspecified)"
    return _build_decision(cache, agent_id, placeholder_cap)


# --- Fuzzy matcher ------------------------------------------------------------

# Very simple verb -> capability shortcuts for common phrasings. Extend
# whenever Juniper drifts on a frequent task verb. The fuzzy matcher below
# also scans the full free-text against capability keys, so this is just
# acceleration — not strictly required.
_VERB_HINTS: dict[str, str] = {
    "draft a foundation letter": "founder-letter-drafting",
    "write a caption": "caption-writing",
    "compose the morning brief": "morning-brief-composition",
    "draft a deal memo": "deal-memo-3-perspectives",
    "build a kill case": "kill-case-builder",
    "score a forecast": "decision-critic",
    "score voice drift": "voice-drift-evaluator",
    "run a forecast": "dated-forecasts",
    "settle a forecast": "settlement-tracking",
    "scan anomalies": "threat-detection",
    "watch slo": "sre-slo-watch",
    "weekly counsel": "weekly-counsel",
    "daily ledger": "daily-ledger-reconciliation",
    "watchlist scan": "watchlist-scans",
    "calibrate": "calibration-ledger",
    "synthesize": "swarm-synthesis",
    "research the web": "web-search",
    "extract zoning": "zoning-research",
    "scrape a site": "firecrawl-scrape",
    "lock visuals": "visual-lock-gate",
    "design system review": "design-system-ownership",
}


def _tokenize(s: str) -> set[str]:
    """Lowercase + alphanumeric tokens. Used for fuzzy capability matching."""
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def route_by_keywords(
    task_description: str,
    *,
    manifest_path: Path | str | None = None,
    min_token_overlap: int = 1,
) -> RouteDecision | None:
    """Fuzzy: scan a free-text task description for the capability with
    the highest token-overlap score. Returns ``None`` when no capability
    has at least ``min_token_overlap`` tokens shared with the input or
    when the top-scoring set ties.

    This is the slow path. Callers that already know the capability key
    should prefer :func:`route_capability`.
    """
    if not task_description:
        return None

    cache = get_manifest(manifest_path)

    # Verb-hint fast path (cheap exact-substring shortcut for the common
    # phrasings above — Juniper's prompts trend stable so these accelerate
    # the common 80% without LLM cost).
    lowered = task_description.lower()
    for hint, capability in _VERB_HINTS.items():
        if hint in lowered:
            if capability in cache.capability_index:
                return route_capability(capability, manifest_path=manifest_path)

    # Token-overlap path
    task_tokens = _tokenize(task_description)
    if not task_tokens:
        return None

    best_caps: list[str] = []
    best_score = 0
    for capability in cache.capability_index:
        cap_tokens = _tokenize(capability.replace("-", " "))
        overlap = len(task_tokens & cap_tokens)
        if overlap < min_token_overlap:
            continue
        if overlap > best_score:
            best_score = overlap
            best_caps = [capability]
        elif overlap == best_score:
            best_caps.append(capability)

    if not best_caps or best_score < min_token_overlap:
        return None
    if len(best_caps) > 1:
        # Tie at the same score — escalate to Alan / HITL per the wiring
        # brief's "multiple agents match equally" rule.
        logger.info(
            "[manifest_router] task=%r matched %d capabilities at score %d (%s) — "
            "tie; returning None to force HITL escalation",
            task_description[:60], len(best_caps), best_score,
            ",".join(best_caps),
        )
        return None

    return route_capability(best_caps[0], manifest_path=manifest_path)


# --- Public API: introspection ------------------------------------------------

def list_capabilities(manifest_path: Path | str | None = None) -> list[str]:
    """All capability keys declared in the manifest, sorted."""
    cache = get_manifest(manifest_path)
    return sorted(cache.capability_index.keys())


def list_agents(manifest_path: Path | str | None = None) -> list[str]:
    """All agent ids declared in the manifest, sorted."""
    cache = get_manifest(manifest_path)
    return sorted(cache.agents_by_id.keys())


def agents_for_gate(
    gate_id: str,
    *,
    manifest_path: Path | str | None = None,
) -> list[str]:
    """Agents that enforce a given governance gate."""
    cache = get_manifest(manifest_path)
    return list(cache.governance_gate_index.get(gate_id) or [])


def agents_for_cost_tier(
    cost_tier: str,
    *,
    manifest_path: Path | str | None = None,
) -> list[str]:
    """Agents whose ``cost_tier`` matches (e.g., ``"opus-required"``)."""
    cache = get_manifest(manifest_path)
    return list(cache.cost_tier_index.get(cost_tier) or [])


def schema_version(manifest_path: Path | str | None = None) -> str:
    """Current ``_schema_version`` of the manifest."""
    cache = get_manifest(manifest_path)
    return str(cache.raw.get("_schema_version") or "unknown")


# --- CLI smoke test -----------------------------------------------------------

if __name__ == "__main__":
    """Smoke test — run `python -m src.manifest_router` to verify wiring.

    Prints schema version, agent count, capability count, and exercises the
    three routing paths on canonical inputs. Useful as a deployment health
    check (e.g. add to juniper's startup log if the deploy looks suspect).
    """
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        cache = get_manifest()
    except FileNotFoundError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"schema_version={schema_version()}")
    print(f"agents={len(cache.agents_by_id)}")
    print(f"capabilities={len(cache.capability_index)}")
    print()

    # Exercise the three routing paths
    cases = [
        ("route_capability", "voice-generation"),
        ("route_capability", "voice-drift-evaluator"),
        ("route_capability", "morning-brief-composition"),
        ("route_by_agent",   "junior"),
        ("route_by_keywords", "draft a foundation letter for HOJ Ep 2"),
        ("route_by_keywords", "score voice drift across the inbox this week"),
        ("route_by_keywords", "compose tomorrow's morning brief"),
    ]
    for fn_name, arg in cases:
        if fn_name == "route_capability":
            d = route_capability(arg)
        elif fn_name == "route_by_agent":
            d = route_by_agent(arg)
        else:
            d = route_by_keywords(arg)

        if d is None:
            print(f"  {fn_name:<22} {arg!r:<50} -> None (HITL escalate)")
        else:
            print(
                f"  {fn_name:<22} {arg!r:<50} -> {d.agent_id:<10} "
                f"model={d.model} gates={d.governance_gates} "
                f"mode={d.mode}"
            )
