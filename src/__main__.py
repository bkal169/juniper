"""Entrypoint that runs all live loops side-by-side.

    python -m src

Each loop runs in its own asyncio task; exceptions are isolated so one
misbehaving loop doesn't take the rest down.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from .event_bus import BusEvent, EventBus
from .knowledge_graph import process_recent
from .self_improvement import analyze_last_two_weeks, publish
from .manifest_router import (
    get_manifest as manifest_get,
    route_capability as manifest_route_capability,
    route_by_keywords as manifest_route_by_keywords,
    schema_version as manifest_schema_version,
)
from .tools.openclaw import openclaw_health, openclaw_research
from .tools.agent_seed import seed_agents
from .tools.alfred import (
    alfred_market_snapshot,
    alfred_roi_score,
    alfred_portfolio_snapshot,
    alfred_fred_refresh,
)
from .tools.vision import vision_analyze_property_photo, vision_scan_document, vision_brand_qa
from .tools.axiom_agent import axiom_queue_outbound, axiom_update_deal_stage, axiom_log_activity
from .utils import wal

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# SIGTERM handler — flush WAL and exit cleanly
# ------------------------------------------------------------------

def _handle_sigterm(sig: int, frame: object) -> None:
    logger.info("SIGTERM received — flushing WAL and exiting")
    wal.flush()
    sys.exit(0)

signal.signal(signal.SIGTERM, _handle_sigterm)


# ------------------------------------------------------------------
# Periodic task runner
# ------------------------------------------------------------------

async def _periodic(name: str, interval_s: float, fn) -> None:
    while True:
        try:
            await asyncio.to_thread(fn)
        except Exception as e:
            print(f"[{name}] error: {e!r}")
        await asyncio.sleep(interval_s)


# ------------------------------------------------------------------
# Heartbeats — bump agents.last_active_at via Supabase REST
# ------------------------------------------------------------------

_HEARTBEAT_AGENTS = ("juniper", "junior", "alfred", "openclaw", "vision", "axiom_pod", "sentinel")


def _heartbeat(agent_id: str) -> None:
    """Stamp agents.last_active_at = NOW() for one agent. Fire-and-forget."""
    try:
        import httpx as _httpx
        url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            return
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with _httpx.Client(timeout=5.0) as hx:
            hx.patch(
                f"{url}/rest/v1/agents?id=eq.{agent_id}",
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json={"last_active_at": now},
            )
    except Exception as exc:
        logger.debug("[heartbeat] %s failed: %r", agent_id, exc)


def _heartbeat_all() -> None:
    for a in _HEARTBEAT_AGENTS:
        _heartbeat(a)


# ------------------------------------------------------------------
# OpenClaw research dispatcher
# ------------------------------------------------------------------

async def _dispatch_openclaw(bus: EventBus, ev: BusEvent) -> None:
    """Handle junior research.request events by dispatching to OpenClaw."""
    task = ev.payload.get("task", "")
    mode = ev.payload.get("mode", "general")
    max_results = int(ev.payload.get("max_results", 10))
    ref_id = ev.ref_id

    if not task:
        logger.warning("[openclaw_handler] research.request missing 'task' in payload")
        return

    logger.info("[openclaw_handler] dispatching: task=%r mode=%s", task[:80], mode)
    result = await asyncio.to_thread(
        openclaw_research, task, mode, max_results, 60.0
    )

    # Re-emit result back onto the bus so Junior / Juniper can consume it
    from .event_bus import BusEvent as _BE
    from datetime import datetime, timezone
    out_ev = _BE(
        id="",
        source="openclaw",
        kind="research.complete" if result["ok"] else "research.failed",
        ref_type="junior",
        ref_id=ref_id,
        payload={
            "task": task,
            "mode": mode,
            "results": result["results"],
            "metadata": result["metadata"],
            "error": result.get("error"),
            "request_id": ref_id,
        },
        occurred_at=datetime.now(timezone.utc),
    )
    try:
        await bus.emit(out_ev)
    except Exception as exc:
        logger.warning("[openclaw_handler] bus.emit failed: %r", exc)
    # Heartbeat: openclaw was just exercised
    await asyncio.to_thread(_heartbeat, "openclaw")
    # Write result to openclaw_runs via httpx (supabase SDK unavailable on Railway/MSVC)
    try:
        import httpx as _httpx
        import os as _os
        _url = _os.environ.get("SUPABASE_URL", "").rstrip("/")
        _key = _os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if _url and _key:
            with _httpx.Client(timeout=10.0) as _hx:
                _hx.post(
                    f"{_url}/rest/v1/openclaw_runs",
                    headers={
                        "apikey": _key,
                        "Authorization": f"Bearer {_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal",
                    },
                    json={
                        "query":        task,
                        "result":       out_ev.payload,
                        "triggered_by": ev.source or "junior",
                        "namespace":    ev.payload.get("namespace", "jrih"),
                    },
                ).raise_for_status()
            logger.info("[openclaw_handler] result written — kind=%s results=%d",
                        out_ev.kind, len(result["results"]))
        else:
            logger.warning("[openclaw_handler] SUPABASE_URL/KEY not set — result not persisted")
    except Exception as exc:
        logger.error("[openclaw_handler] failed to write result event: %r", exc)


# ------------------------------------------------------------------
# Alfred investment intelligence dispatcher
# ------------------------------------------------------------------

async def _dispatch_alfred(bus: EventBus, ev: BusEvent) -> None:
    """Handle alfred.snapshot_request and alfred.roi_request events."""
    kind = ev.kind
    payload = ev.payload

    if kind == "alfred.snapshot_request":
        symbols = payload.get("symbols")  # None → uses ALFRED_WATCHLIST env
        result = await asyncio.to_thread(alfred_market_snapshot, symbols)
        out_kind = "alfred.snapshot_complete" if result["ok"] else "alfred.snapshot_failed"
        out_payload = {"symbols": symbols, "data": result.get("data"), "error": result.get("error")}

    elif kind == "alfred.roi_request":
        result = await asyncio.to_thread(
            alfred_roi_score,
            payload.get("purchase_price", 0),
            payload.get("current_value", 0),
            payload.get("annual_income", 0.0),
            payload.get("hold_years", 1.0),
        )
        out_kind = "alfred.roi_complete" if result["ok"] else "alfred.roi_failed"
        out_payload = {k: result.get(k) for k in ("roi", "annualised_roi", "score", "error")}

    else:
        logger.warning("[alfred_handler] unknown kind: %s", kind)
        return

    await asyncio.to_thread(
        axiom_log_activity, "alfred_event", str(ev.ref_id), out_kind, out_payload
    )
    logger.info("[alfred_handler] %s ref_id=%s ok=%s", out_kind, ev.ref_id, result["ok"])
    await asyncio.to_thread(_heartbeat, "alfred")


# ------------------------------------------------------------------
# Vision image processing dispatcher
# ------------------------------------------------------------------

async def _dispatch_vision(bus: EventBus, ev: BusEvent) -> None:
    """Handle vision.analyze_request events — route by subtype in payload."""
    payload = ev.payload
    subtype = payload.get("subtype", "property_photo")  # property_photo | document | brand_qa
    image_url = payload.get("image_url")
    image_b64 = payload.get("image_base64")
    media_type = payload.get("media_type", "image/jpeg")

    if subtype == "property_photo":
        result = await asyncio.to_thread(
            vision_analyze_property_photo, image_url, image_b64, media_type
        )
        out_kind = "vision.analysis_complete" if result["ok"] else "vision.analysis_failed"
        out_payload = {"subtype": subtype, "analysis": result.get("analysis"), "error": result.get("error")}

    elif subtype == "document":
        goal = payload.get("goal", "Extract all text and key data fields from this document.")
        result = await asyncio.to_thread(vision_scan_document, image_b64, media_type, goal)
        out_kind = "vision.scan_complete" if result["ok"] else "vision.scan_failed"
        out_payload = {"subtype": subtype, "result": result.get("result"), "error": result.get("error")}

    elif subtype == "brand_qa":
        result = await asyncio.to_thread(vision_brand_qa, image_b64, media_type)
        out_kind = "vision.qa_complete" if result["ok"] else "vision.qa_failed"
        out_payload = {"subtype": subtype, "result": result.get("result"), "error": result.get("error")}

    else:
        logger.warning("[vision_handler] unknown subtype: %s", subtype)
        return

    await asyncio.to_thread(
        axiom_log_activity, "vision_event", str(ev.ref_id), out_kind, out_payload
    )
    logger.info("[vision_handler] %s ref_id=%s ok=%s", out_kind, ev.ref_id, result["ok"])
    await asyncio.to_thread(_heartbeat, "vision")


# ------------------------------------------------------------------
# AxiomOS Agent action dispatcher (ALL actions → HITL queue)
# ------------------------------------------------------------------

async def _dispatch_axiom(bus: EventBus, ev: BusEvent) -> None:
    """Handle axiom.action_request events — always routes to HITL, never auto-executes."""
    payload = ev.payload
    action_type = payload.get("action_type", "unknown")
    agent = payload.get("agent", "AxiomOS")

    result = await asyncio.to_thread(
        axiom_queue_outbound, action_type, payload, agent, True
    )
    out_kind = "axiom.queued" if result["ok"] else "axiom.queue_failed"
    logger.info("[axiom_handler] %s action=%s ref_id=%s ok=%s",
                out_kind, action_type, ev.ref_id, result["ok"])
    await asyncio.to_thread(_heartbeat, "axiom_pod")


# ------------------------------------------------------------------
# Junior audit_complete fan-out — emit ROI + research follow-on signals
# ------------------------------------------------------------------

async def _dispatch_audit_complete(bus: EventBus, ev: BusEvent) -> None:
    """Fan out follow-on bus events when Junior signals audit_complete.

    Schema assumption (matches `juniper_audit` rows mirrored into payload):
      - payload.deal_id        → emit alfred.roi_request
      - payload.action_type='research' OR payload.flagged_research → emit research.request
    """
    payload = ev.payload or {}
    deal_id = payload.get("deal_id")
    action_type = (payload.get("action_type") or "").lower()
    division = payload.get("division") or "general"
    decision = payload.get("decision") or payload.get("decision_text") or ""

    # ROI fan-out
    if deal_id:
        try:
            await bus.emit(BusEvent(
                id="",
                source="juniper",
                kind="alfred.roi_request",
                ref_type="alfred",
                ref_id=str(ev.ref_id) if ev.ref_id else None,
                payload={
                    "deal_id": deal_id,
                    "purchase_price": payload.get("purchase_price", 0),
                    "current_value":  payload.get("current_value", 0),
                    "annual_income":  payload.get("annual_income", 0.0),
                    "hold_years":     payload.get("hold_years", 1.0),
                    "audit_id":       payload.get("audit_id"),
                },
                occurred_at=ev.occurred_at,
            ))
            logger.info("[audit_fanout] alfred.roi_request emitted deal_id=%s", deal_id)
        except Exception as exc:
            logger.warning("[audit_fanout] roi emit failed: %r", exc)

    # Research fan-out
    is_research = (
        action_type == "research"
        or bool(payload.get("flagged_research"))
        or "research" in (decision or "").lower()[:80]
    )
    if is_research and decision:
        try:
            await bus.emit(BusEvent(
                id="",
                source="juniper",
                kind="research.request",
                ref_type="openclaw",
                ref_id=str(ev.ref_id) if ev.ref_id else None,
                payload={
                    "task":        decision,
                    "mode":        division,
                    "max_results": int(payload.get("max_results", 10)),
                    "audit_id":    payload.get("audit_id"),
                    "namespace":   payload.get("namespace", "jrih"),
                },
                occurred_at=ev.occurred_at,
            ))
            logger.info(
                "[audit_fanout] research.request emitted (mode=%s task=%r)",
                division, decision[:60],
            )
        except Exception as exc:
            logger.warning("[audit_fanout] research emit failed: %r", exc)

    await asyncio.to_thread(_heartbeat, "junior")


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------

async def main() -> None:
    # Replay any uncommitted WAL entries from a previous crash
    pending = wal.wal_replay()
    if pending:
        logger.info("Startup WAL replay: %d uncommitted entries", len(pending))
    else:
        logger.info("Startup WAL replay: clean (no uncommitted entries)")

    # Phase 0: seed any missing agent nodes into kg_nodes on startup
    try:
        seeded = await asyncio.to_thread(seed_agents)
        if seeded:
            logger.info("Phase 0 agent seed: %s", ", ".join(seeded))
    except Exception as exc:
        logger.warning("Phase 0 agent seed failed (non-fatal): %r", exc)

    # Capability MANIFEST preload — failure is non-fatal; routing handlers
    # will return None on lookup if the manifest can't be read, which the
    # callers translate into HITL escalation per the wiring brief.
    # Per workflows/agents/MANIFEST.md the recipe is: capability -> agent ->
    # (model, governance_gates, mode). The router memoizes on file mtime so
    # MANIFEST.json edits are picked up without a Juniper restart.
    try:
        cache = await asyncio.to_thread(manifest_get)
        logger.info(
            "[manifest_router] schema=%s agents=%d capabilities=%d gates=%d",
            manifest_schema_version(),
            len(cache.agents_by_id),
            len(cache.capability_index),
            len(cache.governance_gate_index),
        )
    except Exception as exc:
        logger.warning(
            "[manifest_router] preload failed (non-fatal — routing will "
            "return None and escalate to HITL): %r", exc,
        )

    # OpenClaw health check on startup
    try:
        alive = await asyncio.to_thread(openclaw_health)
        logger.info("OpenClaw daemon: %s", "ONLINE" if alive else "OFFLINE (will retry per request)")
    except Exception:
        logger.warning("OpenClaw health check failed (daemon may be offline)")

    bus = EventBus()

    # Budget guard
    @bus.on("budget_guard", "budget.exceeded")
    async def _budget(ev: BusEvent) -> None:
        print(f"[juniper] BUDGET EXCEEDED: {ev.payload}")

    # Stale embeddings signal
    @bus.on("juniper", "embeddings.stale")
    async def _stale(ev: BusEvent) -> None:
        print(f"[juniper] stale embeddings: {ev.payload.get('count')}")

    # OpenClaw: handle research dispatch requests from Junior or Juniper
    @bus.on("junior", "research.request")
    @bus.on("juniper", "research.request")
    async def _research(ev: BusEvent) -> None:
        await _dispatch_openclaw(bus, ev)
        await asyncio.to_thread(_heartbeat, "junior")

    # MANIFEST-driven capability routing — any agent can ask Juniper "who
    # owns this capability?". Per workflows/agents/MANIFEST.md auto-routing
    # recipe. Payload accepts EITHER:
    #   - capability: <kebab-case capability key>   (fast-path exact match)
    #   - task: <free-text description>             (fuzzy keyword match)
    # The handler emits route.resolved (or route.unresolved when no agent
    # matches OR multiple agents match equally — caller escalates to HITL).
    @bus.on("any", "task.route_request")
    @bus.on("juniper", "task.route_request")
    @bus.on("junior", "task.route_request")
    @bus.on("alan", "task.route_request")
    async def _task_route(ev: BusEvent) -> None:
        payload = ev.payload or {}
        capability = (payload.get("capability") or "").strip()
        task_text = (payload.get("task") or "").strip()
        # root_task_id — 2026-09-20 (Jev eval Phase 0b plumbing): emit() only
        # persists BusEvent.payload (jsonb), never BusEvent.ref_id (see
        # event_bus.py's schema-mapping note), so a decision was previously
        # unjoinable to the request that produced it. A caller starting a new
        # lineage gets none; carry it forward on every re-dispatch instead of
        # minting a fresh one, per the lineage model in the consolidated plan.
        root_task_id = (payload.get("root_task_id") or "").strip() or ev.ref_id or ev.id

        decision = None
        if capability:
            decision = await asyncio.to_thread(manifest_route_capability, capability)
        elif task_text:
            decision = await asyncio.to_thread(manifest_route_by_keywords, task_text)

        from datetime import datetime, timezone
        out_kind = "task.route_resolved" if decision is not None else "task.route_unresolved"
        out_payload: dict = {
            "root_task_id": root_task_id,
            "request_capability": capability or None,
            "request_task": task_text or None,
        }
        if decision is not None:
            out_payload.update({
                "agent_id": decision.agent_id,
                "capability": decision.capability,
                "model": decision.model,
                "cost_tier": decision.cost_tier,
                "governance_gates": decision.governance_gates,
                "mode": decision.mode,
                "requires_hitl": decision.requires_hitl,
                "domain": decision.domain,
                "soul_doc_path": decision.soul_doc_path,
            })
            logger.info(
                "[manifest_router] resolved cap=%r -> agent=%s model=%s "
                "gates=%s mode=%s (req_id=%s)",
                decision.capability, decision.agent_id, decision.model,
                decision.governance_gates, decision.mode, ev.ref_id,
            )
        else:
            out_payload["reason"] = (
                "no_match_or_tie — caller should escalate to Alan via HITL "
                "per workflows/agents/MANIFEST.md auto-routing recipe step 5"
            )
            logger.info(
                "[manifest_router] unresolved capability=%r task=%r req_id=%s",
                capability, task_text[:60], ev.ref_id,
            )

        try:
            await bus.emit(BusEvent(
                id="",
                source="juniper",
                kind=out_kind,
                ref_type=ev.source,
                ref_id=ev.ref_id,
                payload=out_payload,
                occurred_at=datetime.now(timezone.utc),
            ))
        except Exception as exc:
            logger.warning("[manifest_router] emit failed: %r", exc)
        await asyncio.to_thread(_heartbeat, "juniper")

    # Alfred: investment intelligence requests from Juno or Juniper
    @bus.on("juno", "alfred.snapshot_request")
    @bus.on("juniper", "alfred.snapshot_request")
    @bus.on("juno", "alfred.roi_request")
    @bus.on("juniper", "alfred.roi_request")
    async def _alfred(ev: BusEvent) -> None:
        await _dispatch_alfred(bus, ev)

    # Vision: image analysis requests from Junior, Rose, or AxiomOS
    @bus.on("junior", "vision.analyze_request")
    @bus.on("rose", "vision.analyze_request")
    @bus.on("axiom_agent", "vision.analyze_request")
    @bus.on("axiom_pod", "vision.analyze_request")
    async def _vision(ev: BusEvent) -> None:
        await _dispatch_vision(bus, ev)

    # AxiomOS: all outbound action requests → HITL queue (never auto-execute)
    @bus.on("juniper", "axiom.action_request")
    @bus.on("junior", "axiom.action_request")
    async def _axiom(ev: BusEvent) -> None:
        await _dispatch_axiom(bus, ev)

    # Junior → Juniper: audit_complete triggers fan-out (ROI + research)
    @bus.on("junior", "audit_complete")
    async def _audit_complete(ev: BusEvent) -> None:
        await _dispatch_audit_complete(bus, ev)

    # Phase 15 Alfred: trade_signal pre-wire. Stub handler; Alfred-PM will populate.
    @bus.on("alfred", "trade_signal")
    @bus.on("alfred_pm", "trade_signal")
    async def _trade_signal(ev: BusEvent) -> None:
        logger.info("[trade_signal] received from %s ref_id=%s ticker=%s",
                    ev.source, ev.ref_id, (ev.payload or {}).get("ticker"))
        await asyncio.to_thread(_heartbeat, "alfred")
        # Phase 15.1 will write to trade_signals table here

    # Sentinel → Orchestrator: drain anomaly.alert backlog (Phase 14.3 fix B)
    # No-op consumer that marks alerts applied so the bus doesn't grow unbounded.
    # Severe alerts get logged to axiom activity for HITL surfacing.
    @bus.on("sentinel", "anomaly.alert")
    @bus.on("sentinel.dispatch", "anomaly.alert")
    async def _sentinel(ev: BusEvent) -> None:
        try:
            severity = (ev.payload or {}).get("severity", "low")
            if severity in ("high", "critical"):
                await asyncio.to_thread(
                    axiom_log_activity,
                    "sentinel_alert", str(ev.ref_id or ""), "anomaly.alert", ev.payload or {}
                )
        except Exception as exc:
            logger.debug("[sentinel_handler] log failed: %r", exc)
        await asyncio.to_thread(_heartbeat, "sentinel")

    # Alan → Juniper: audit.approved drains via no-op handler (Phase 14.3 fix A)
    @bus.on("alan", "audit.approved")
    @bus.on("juniper", "audit.approved")
    async def _audit_approved(ev: BusEvent) -> None:
        # Mark applied; the audit-approval flow is handled web-side (Next.js HITL).
        # Python side just acknowledges to drain the bus.
        await asyncio.to_thread(_heartbeat, "juniper")

    def run_self_improvement() -> None:
        publish(analyze_last_two_weeks())

    kg_interval = float(os.environ.get("JUNIPER_KG_INTERVAL_S", "3600"))
    si_interval = float(os.environ.get("JUNIPER_SI_INTERVAL_S", "86400"))
    hb_interval = float(os.environ.get("JUNIPER_HEARTBEAT_INTERVAL_S", "60"))
    fred_interval = float(os.environ.get("ALFRED_FRED_INTERVAL_S", "900"))

    await asyncio.gather(
        bus.run(),
        _periodic("knowledge_graph", kg_interval, process_recent),
        _periodic("self_improvement", si_interval, run_self_improvement),
        _periodic("heartbeats", hb_interval, _heartbeat_all),
        _periodic("alfred_fred_refresh", fred_interval, alfred_fred_refresh),
    )


if __name__ == "__main__":
    asyncio.run(main())
