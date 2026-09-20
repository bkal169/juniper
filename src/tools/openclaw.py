"""OpenClaw research tool — dispatches tasks to the OpenClaw daemon.

OpenClaw is Juniper's autonomous web research agent.  This module provides
the Python-side tool that POSTs research tasks to the daemon and returns
structured results.

Daemon:  http://127.0.0.1:18788  (local) | https://openclaw.jrih.dev (public)
Auth:    Bearer token from OPENCLAW_API_KEY env var
Railway: OPENCLAW_URL + OPENCLAW_API_KEY are set as Railway env vars.

Usage:
    from src.tools.openclaw import openclaw_research

    result = openclaw_research(
        task="Find distressed properties in ZIP 33161 under $300k",
        mode="property_search",
        max_results=10,
    )
    if result["ok"]:
        for item in result["results"]:
            print(item)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)

ResearchMode = Literal["property_search", "serp", "competitor", "general"]

# Default to local daemon; Railway override via OPENCLAW_URL
_DEFAULT_URL = "http://127.0.0.1:18788"


def _base_url() -> str:
    return os.environ.get("OPENCLAW_URL", _DEFAULT_URL).rstrip("/")


def _api_key() -> str | None:
    return os.environ.get("OPENCLAW_API_KEY")


def openclaw_research(
    task: str,
    mode: ResearchMode = "general",
    max_results: int = 10,
    timeout_s: float = 60.0,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """POST a research task to the OpenClaw daemon and return results.

    Args:
        task:        Natural-language description of what to research.
        mode:        Research mode — controls which scraper/pipeline is used.
        max_results: Maximum number of results to return.
        timeout_s:   Request timeout in seconds.
        extra:       Optional extra params forwarded to the daemon payload.

    Returns:
        dict with keys:
            ok (bool)          — True on success
            results (list)     — Structured research results
            metadata (dict)    — Task metadata from daemon (timing, source, etc.)
            error (str|None)   — Error message if ok=False
    """
    url = f"{_base_url()}/research"
    key = _api_key()

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    payload: dict[str, Any] = {
        "task": task,
        "mode": mode,
        "max_results": max_results,
    }
    if extra:
        payload.update(extra)

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=timeout_s)
        resp.raise_for_status()
        data = resp.json()
        logger.info(
            "[openclaw] task=%r mode=%s results=%d",
            task[:80],
            mode,
            len(data.get("results", [])),
        )
        return {
            "ok": True,
            "results": data.get("results", []),
            "metadata": data.get("metadata", {}),
            "error": None,
        }

    except httpx.TimeoutException:
        logger.warning("[openclaw] timeout after %.0fs — task=%r", timeout_s, task[:80])
        return {"ok": False, "results": [], "metadata": {}, "error": "timeout"}

    except httpx.HTTPStatusError as exc:
        logger.error("[openclaw] HTTP %s — %s", exc.response.status_code, exc.response.text[:200])
        return {
            "ok": False,
            "results": [],
            "metadata": {},
            "error": f"http_{exc.response.status_code}",
        }

    except Exception as exc:
        logger.error("[openclaw] unexpected error: %r", exc)
        return {"ok": False, "results": [], "metadata": {}, "error": str(exc)}


def openclaw_health() -> bool:
    """Quick health check against the daemon.  Returns True if reachable."""
    try:
        resp = httpx.get(f"{_base_url()}/health", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


if __name__ == "__main__":
    alive = openclaw_health()
    print(f"[openclaw] daemon health: {'OK' if alive else 'UNREACHABLE'}")
    if alive:
        r = openclaw_research("test ping", mode="general", max_results=1, timeout_s=10)
        print(f"[openclaw] test result: {r}")
