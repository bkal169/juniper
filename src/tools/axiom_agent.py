"""AxiomOS Agent execution tool — HITL queue, deal stages, activity logging.

ALL outbound actions must be queued via axiom_queue_outbound and approved by a human
before execution. No action is auto-executed by this module.

Usage:
    from tools.axiom_agent import axiom_queue_outbound, axiom_update_deal_stage

    result = axiom_queue_outbound(
        action_type="send_email",
        payload={"to": "prospect@co.com", "subject": "Follow-up"},
        agent="AxiomOS",
    )
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _supabase_url() -> str:
    url = os.environ.get("SUPABASE_URL", "")
    if not url:
        raise RuntimeError("SUPABASE_URL env var not set")
    return url.rstrip("/")


def _service_key() -> str:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY env var not set")
    return key


def _headers() -> dict[str, str]:
    key = _service_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def axiom_queue_outbound(
    action_type: str,
    payload: dict[str, Any],
    agent: str = "AxiomOS",
    requires_approval: bool = True,
) -> dict[str, Any]:
    """Queue an outbound action in hitl_queue for human review before execution.

    ALL outbound actions must flow through this function — nothing is auto-executed.
    """
    try:
        base = _supabase_url()
        row = {
            "item_type": action_type,
            "title": f"[{agent}] {action_type}",
            "context": payload,
            "agent": agent,
            "status": "pending",
        }
        resp = httpx.post(
            f"{base}/rest/v1/hitl_queue",
            headers=_headers(),
            json=row,
            timeout=15,
        )
        resp.raise_for_status()
        queued = resp.json()
        logger.info("axiom_queue_outbound: queued %s id=%s", action_type, queued[0].get("id") if queued else "?")
        return {"ok": True, "queued": queued[0] if queued else row, "error": None}
    except httpx.TimeoutException:
        return {"ok": False, "queued": None, "error": "Supabase request timed out"}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "queued": None, "error": f"HTTP {exc.response.status_code}: {exc.response.text}"}
    except Exception as exc:
        logger.exception("axiom_queue_outbound failed")
        return {"ok": False, "queued": None, "error": str(exc)}


def axiom_update_deal_stage(
    deal_id: str,
    new_stage: str,
    notes: str = "",
) -> dict[str, Any]:
    """PATCH deals.stage for a given deal_id. new_stage must match the deal_stage enum."""
    try:
        base = _supabase_url()
        body: dict[str, Any] = {"stage": new_stage}
        if notes:
            body["notes"] = notes
        resp = httpx.patch(
            f"{base}/rest/v1/deals?id=eq.{deal_id}",
            headers=_headers(),
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
        updated = resp.json()
        return {"ok": True, "updated": updated, "error": None}
    except httpx.TimeoutException:
        return {"ok": False, "updated": None, "error": "Supabase request timed out"}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "updated": None, "error": f"HTTP {exc.response.status_code}: {exc.response.text}"}
    except Exception as exc:
        logger.exception("axiom_update_deal_stage failed")
        return {"ok": False, "updated": None, "error": str(exc)}


def axiom_log_activity(
    entity_type: str,
    entity_id: str,
    action: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a row to activity_log for audit trail purposes."""
    try:
        base = _supabase_url()
        row = {
            "user_id": os.environ.get("AXIOM_AGENT_USER_ID", "axiom-agent"),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "metadata": metadata or {},
        }
        resp = httpx.post(
            f"{base}/rest/v1/activity_log",
            headers=_headers(),
            json=row,
            timeout=15,
        )
        resp.raise_for_status()
        logged = resp.json()
        return {"ok": True, "logged": logged[0] if logged else row, "error": None}
    except httpx.TimeoutException:
        return {"ok": False, "logged": None, "error": "Supabase request timed out"}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "logged": None, "error": f"HTTP {exc.response.status_code}: {exc.response.text}"}
    except Exception as exc:
        logger.exception("axiom_log_activity failed")
        return {"ok": False, "logged": None, "error": str(exc)}


def axiom_apollo_sequence_stub(
    contact_email: str,
    sequence_name: str,
) -> dict[str, Any]:
    """Queue an Apollo sequence enrollment for HITL approval — never auto-enrolls.

    Apollo enrollment must be reviewed and approved via the HITL queue before execution.
    """
    payload = {"contact_email": contact_email, "sequence_name": sequence_name}
    return axiom_queue_outbound(
        action_type="apollo_sequence_enroll",
        payload=payload,
        agent="AxiomOS",
        requires_approval=True,
    )


if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)
    print("=== axiom_apollo_sequence_stub (queues HITL item) ===")
    r = axiom_apollo_sequence_stub("test@example.com", "Cold Outreach Q2")
    print(json.dumps(r, indent=2, default=str))
