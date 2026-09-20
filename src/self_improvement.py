"""Weekly self-improvement loop.

Reads the two most recent `weekly_reports` rows, identifies regressions
(cost spike, cache hit drop, rejection rate up), and emits suggestions
as `activity_events` (source='juniper', kind='improvement.suggestion').

Run via:   python -m src.self_improvement
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass

import httpx


@dataclass
class Suggestion:
    kind: str
    severity: str
    message: str
    metric: str
    current: float
    previous: float


def _sb_url() -> str:
    return os.environ.get("SUPABASE_URL", "").rstrip("/")


def _sb_key() -> str:
    return os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _sb_headers() -> dict[str, str]:
    key = _sb_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def analyze_last_two_weeks() -> list[Suggestion]:
    url = _sb_url()
    key = _sb_key()
    if not url or not key:
        return []
    try:
        resp = httpx.get(
            f"{url}/rest/v1/weekly_reports",
            headers=_sb_headers(),
            params={"select": "*", "order": "week_start.desc", "limit": "2"},
            timeout=10.0,
        )
        resp.raise_for_status()
        rows_data = resp.json()
    except Exception:
        return []
    if len(rows_data) < 2:
        return []
    curr, prev = rows_data[0], rows_data[1]
    out: list[Suggestion] = []

    if float(curr["est_cost_usd"]) > float(prev["est_cost_usd"]) * 1.2:
        out.append(Suggestion(
            kind="cost_spike",
            severity="warn",
            message="Model cost up >20% WoW — consider lowering tier floor or enabling batch.",
            metric="est_cost_usd",
            current=float(curr["est_cost_usd"]),
            previous=float(prev["est_cost_usd"]),
        ))

    if float(curr["cache_hit_pct"]) < float(prev["cache_hit_pct"]) - 10:
        out.append(Suggestion(
            kind="cache_hit_drop",
            severity="warn",
            message="Prompt cache hit rate fell >10pp — check system prompt stability.",
            metric="cache_hit_pct",
            current=float(curr["cache_hit_pct"]),
            previous=float(prev["cache_hit_pct"]),
        ))

    rej_total_curr = int(curr.get("hitl_rejected", 0) or 0) + int(curr.get("hitl_approved", 0) or 0)
    rej_total_prev = int(prev.get("hitl_rejected", 0) or 0) + int(prev.get("hitl_approved", 0) or 0)
    if rej_total_curr and rej_total_prev:
        rej_rate_curr = int(curr.get("hitl_rejected", 0) or 0) / rej_total_curr
        rej_rate_prev = int(prev.get("hitl_rejected", 0) or 0) / rej_total_prev
        if rej_rate_curr > rej_rate_prev + 0.10:
            out.append(Suggestion(
                kind="rejection_rate_up",
                severity="warn",
                message="HITL rejection rate up >10pp — tighten auto_threshold or retrain agents.",
                metric="rejection_rate",
                current=rej_rate_curr,
                previous=rej_rate_prev,
            ))

    return out


def publish(suggestions: list[Suggestion]) -> None:
    """Write improvement suggestions as system thoughts in Supabase (httpx, no SDK)."""
    if not suggestions:
        return
    url = _sb_url()
    key = _sb_key()
    if not url or not key:
        return
    headers = {**_sb_headers(), "Prefer": "return=minimal"}
    for s in suggestions:
        try:
            httpx.post(
                f"{url}/rest/v1/thoughts",
                headers=headers,
                json={
                    "content":    f"[self_improvement] {s.severity.upper()} {s.kind}: {s.message}",
                    "source":     "system",
                    "entry_type": "improvement.suggestion",
                    "agent":      "juniper",
                    "metadata":   asdict(s),
                    "confidence": 0.9,
                },
                timeout=10.0,
            ).raise_for_status()
        except Exception as exc:
            print(f"[self_improvement] failed to publish suggestion: {exc!r}")


if __name__ == "__main__":
    suggestions = analyze_last_two_weeks()
    publish(suggestions)
    for s in suggestions:
        print(f"[self_improvement] {s.severity.upper()} {s.kind}: {s.message}")
    if not suggestions:
        print("[self_improvement] no regressions detected")
