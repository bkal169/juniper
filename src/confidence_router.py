"""Picks tier + escalation policy from confidence_thresholds table.

The Next.js side writes thresholds into `confidence_thresholds`; Python reads
them to decide whether an autonomous action is auto / hitl / reject.

Patch H consumer: also reads active rules from `junior_rules` and applies them
BEFORE confidence-based decisioning. A rule with action='reject' short-circuits
to reject; action='flag' caps the decision at hitl regardless of confidence.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

import httpx
from supabase import Client, create_client

Decision = Literal["auto", "hitl", "reject"]


@dataclass
class Threshold:
    action_type: str
    auto_threshold: float
    hitl_threshold: float
    reject_threshold: float


@dataclass
class JuniorRule:
    id: str
    description: str
    condition: str
    action: str  # 'reject' | 'flag' | 'allow'
    confidence: float
    episode_count: int


def _client() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _sb_headers() -> dict[str, str]:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def load_thresholds() -> dict[str, Threshold]:
    rows = _client().table("confidence_thresholds").select("*").execute()
    return {r["action_type"]: Threshold(**r) for r in rows.data}


def load_active_rules() -> list[JuniorRule]:
    """Pull active junior_rules via raw REST (supabase-js count quirk; raw is reliable)."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not url:
        return []
    try:
        resp = httpx.get(
            f"{url}/rest/v1/junior_rules",
            headers=_sb_headers(),
            params={"select": "id,description,condition,action,confidence,episode_count", "active": "eq.true"},
            timeout=8.0,
        )
        resp.raise_for_status()
        return [JuniorRule(**r) for r in resp.json()]
    except Exception:
        return []


def evaluate_rules(
    rules: list[JuniorRule],
    *,
    action_type: str,
    division: str | None,
    decision_text: str,
    agent: str | None = None,
    payload: dict | None = None,
    audit_count_24h: int = 0,
    executed_count_24h: int = 0,
) -> JuniorRule | None:
    """Match the proposed action against active rules. Returns the first matching
    rule whose `condition` evaluates true (AND-chained clauses), or None.

    Supported DSL clauses (Phase 7.4 extended):
      - "decision ~* 'PATTERN'"            — regex on decision_text
      - "agent = 'X'"                      — equality on agent name           (Phase 7.4)
      - "action_type = 'X'"                — equality on action_type          (Phase 7.4)
      - "action_type ~* 'PATTERN'"         — regex on action_type             (Phase 7.4)
      - "division = 'X'"                   — equality on division
      - "executed_count_24h = N"           — exact integer
      - "audit_count_24h >= N"             — at-least
      - "<field> = 'X'"                    — equality on payload string field  (Phase 7.4)
      - "<field> ~* 'PATTERN'"             — regex on payload string field    (Phase 7.4)
      - "<field> >= N" / "<= N" / "> N" / "< N" / "= N"
                                            — numeric comparison on payload    (Phase 7.4)

    Examples:
      "agent = 'sage' AND action_type ~* 'list_price'"
      "agent = 'bishop' AND target_segment ~* '(healthcare|defense|banking_core)'"
      "agent = 'bishop' AND prospect_aum_estimate >= 100000000"
    """
    payload = payload or {}
    # String-equality / regex fields handled by named matchers below.
    # Numeric fields are NOT in this set — generic numeric matcher handles them
    # uniformly via `executed_count_24h` / `audit_count_24h` -> kwargs synthesis.
    HANDLED_STRING_FIELDS = {
        "decision", "agent", "action_type", "division",
    }

    # Synthesize kwargs into payload so generic numeric matcher can process them too.
    # Avoids the silent-skip bug where rules using `executed_count_24h >= 5` (instead
    # of `= N`) would fail to match because the specific handler only supported `=`.
    payload_with_kwargs = dict(payload)
    payload_with_kwargs.setdefault("executed_count_24h", executed_count_24h)
    payload_with_kwargs.setdefault("audit_count_24h", audit_count_24h)

    EPS = 1e-9

    for rule in rules:
        cond = rule.condition or ""
        matched = True

        # decision regex
        m = re.search(r"decision\s*~\*\s*'([^']+)'", cond)
        if m:
            try:
                if not re.search(m.group(1), decision_text or "", re.IGNORECASE):
                    matched = False
            except re.error:
                matched = False

        # agent equality
        if matched:
            m = re.search(r"agent\s*=\s*'([^']+)'", cond)
            if m and (agent or "") != m.group(1):
                matched = False

        # action_type regex (independent — both regex and equality clauses can coexist)
        if matched:
            m = re.search(r"action_type\s*~\*\s*'([^']+)'", cond)
            if m:
                try:
                    if not re.search(m.group(1), action_type or "", re.IGNORECASE):
                        matched = False
                except re.error:
                    matched = False

        # action_type equality (independent of regex clause; both apply if both present)
        if matched:
            m = re.search(r"action_type\s*=\s*'([^']+)'", cond)
            if m and (action_type or "") != m.group(1):
                matched = False

        # division equality
        if matched:
            m = re.search(r"division\s*=\s*'([^']+)'", cond)
            if m and (division or "") != m.group(1):
                matched = False

        # arbitrary payload string fields (regex form)
        if matched:
            for fmatch in re.finditer(r"(\w+)\s*~\*\s*'([^']+)'", cond):
                field, pattern = fmatch.group(1), fmatch.group(2)
                if field in HANDLED_STRING_FIELDS:
                    continue
                val = str(payload.get(field, ""))
                try:
                    if not re.search(pattern, val, re.IGNORECASE):
                        matched = False
                        break
                except re.error:
                    matched = False
                    break

        # arbitrary payload string fields (equality form)
        if matched:
            for fmatch in re.finditer(r"(\w+)\s*=\s*'([^']+)'", cond):
                field, expected = fmatch.group(1), fmatch.group(2)
                if field in HANDLED_STRING_FIELDS:
                    continue
                if str(payload.get(field, "")) != expected:
                    matched = False
                    break

        # numeric fields — uniform handling for both kwarg-derived and arbitrary payload fields
        # (executed_count_24h and audit_count_24h are synthesized into payload_with_kwargs above)
        if matched:
            for fmatch in re.finditer(r"(\w+)\s*(>=|<=|>|<|=)\s*(\d+(?:\.\d+)?)", cond):
                field, op, thresh_str = fmatch.group(1), fmatch.group(2), fmatch.group(3)
                if field in HANDLED_STRING_FIELDS:
                    continue  # skip numeric on string fields
                threshold = float(thresh_str)
                val = payload_with_kwargs.get(field)
                if val is None:
                    matched = False
                    break
                try:
                    val_num = float(val)
                except (TypeError, ValueError):
                    matched = False
                    break
                if op == ">=" and val_num < threshold:
                    matched = False; break
                if op == "<=" and val_num > threshold:
                    matched = False; break
                if op == ">" and val_num <= threshold:
                    matched = False; break
                if op == "<" and val_num >= threshold:
                    matched = False; break
                if op == "=" and abs(val_num - threshold) > EPS:
                    matched = False; break

        if matched:
            return rule
    return None


def decide(
    action_type: str,
    confidence: float,
    thresholds: dict[str, Threshold],
    *,
    rules: list[JuniorRule] | None = None,
    division: str | None = None,
    decision_text: str = "",
    agent: str | None = None,
    payload: dict | None = None,
    audit_count_24h: int = 0,
    executed_count_24h: int = 0,
) -> Decision:
    """Decide action verdict — Junior rules take precedence over confidence.

    Phase 7.4 extension: pass `agent` and `payload` so rules with
    agent/action_type/payload-numeric clauses can fire at runtime.
    """
    if rules:
        matched = evaluate_rules(
            rules,
            action_type=action_type,
            division=division,
            decision_text=decision_text,
            agent=agent,
            payload=payload,
            audit_count_24h=audit_count_24h,
            executed_count_24h=executed_count_24h,
        )
        if matched is not None:
            if matched.action == "reject":
                return "reject"
            if matched.action == "flag":
                # cap to hitl regardless of confidence
                return "hitl"
            # 'allow' falls through to confidence-based logic

    t = thresholds.get(action_type)
    if t is None:
        return "hitl"
    if confidence >= t.auto_threshold:
        return "auto"
    if confidence >= t.hitl_threshold:
        return "hitl"
    if confidence >= t.reject_threshold:
        return "hitl"
    return "reject"


if __name__ == "__main__":
    rules = load_active_rules()
    print(f"juniper.confidence_router — loaded {len(rules)} active junior_rules")
    for r in rules:
        print(f"  - [{r.action}] {r.description[:80]}")
