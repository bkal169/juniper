"""
JRIH — Calibrated HITL Sigmoid Gate (Build #1)

Replaces ad-hoc HITL thresholds with an interpretable, self-calibrating gate.

    z  →  p = sigma(A*z + B)  →  p > tau ? auto-execute : HITL

Everything lives in log-odds space until the final squash, so tau is readable
as odds: tau=0.95 means "auto-act only above 19:1 odds of being correct."

The gate DECIDES; it does not execute. Callers execute on `auto_executed`.
That keeps the gate side-effect-free apart from its own ledger row.

Wiring:
  * Below tau  → a `hitl_queue` row is created (the surface `hitl_review.py`
    already reads), and its id is stored on the ledger row.
  * Alan's approve/reject in `hitl_review.py` IS the training label —
    `sync_outcomes_from_hitl()` pulls it back as outcome 1/0. No second
    human-resolution path is introduced.

Schema: supabase/schema_decision_calibration.sql
Nightly refit: agents/recalibrate_gate.py

Target project: Mycelium OS · zqrgazuaideuumksijhe (Brain DB since 2026-04-28).
"""

import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, NamedTuple, Optional

from config import sb, SUPABASE_URL

# ─────────────────────────────────────────────────────────────
# Project guard
#
# Phase 13.3 removed a HARD assertion here because it blocked a legitimate
# repoint. So this warns loudly rather than raising — unless you opt in to
# strict mode. Wrong-project writes have bitten this system twice; silence
# is the failure mode we are buying our way out of.
# ─────────────────────────────────────────────────────────────

EXPECTED_SUPABASE_REF = os.environ.get('EXPECTED_SUPABASE_REF', 'zqrgazuaideuumksijhe')
STRICT_PROJECT = os.environ.get('DECISION_GATE_STRICT_PROJECT', '0') == '1'


def _check_project() -> None:
    if EXPECTED_SUPABASE_REF and EXPECTED_SUPABASE_REF not in SUPABASE_URL:
        msg = (
            f"[decision_gate] SUPABASE_URL does not contain expected project ref "
            f"'{EXPECTED_SUPABASE_REF}'. Actual: {SUPABASE_URL}. "
            f"The Brain DB is zqrgazuaideuumksijhe; obtoinsjncbqdqgdeddl is the LIVE "
            f"Heart of Juniper production backend — do not write gate data there. "
            f"Set EXPECTED_SUPABASE_REF if this repoint is intentional."
        )
        if STRICT_PROJECT:
            raise RuntimeError(msg)
        print(f"WARNING: {msg}")


_check_project()


# ─────────────────────────────────────────────────────────────
# Math (pure Python — no numpy in requirements.txt)
# ─────────────────────────────────────────────────────────────

def sigmoid(z: float) -> float:
    """Numerically stable logistic. Never overflows on large |z|."""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def logit(p: float, eps: float = 1e-12) -> float:
    """Inverse of sigmoid. Clamped so p=0/1 don't blow up."""
    p = min(max(p, eps), 1.0 - eps)
    return math.log(p / (1.0 - p))


def odds(p: float) -> float:
    """Read a probability as odds — the interpretable form of tau."""
    return p / (1.0 - p) if p < 1.0 else float('inf')


# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────

DEFAULT_CONFIG: Dict[str, Any] = {
    'tau': 0.80,
    'tau_floor': 0.60,
    'target_precision': 0.95,
    'platt_a': 1.0,
    'platt_b': 0.0,
    'min_samples': 50,
    'max_tau_step': 0.10,
}

_config_cache: Dict[str, Dict[str, Any]] = {}


def get_config(agent: str, refresh: bool = False) -> Dict[str, Any]:
    """Load per-agent gate config, creating the row on first use."""
    if not refresh and agent in _config_cache:
        return _config_cache[agent]

    result = sb.table('decision_gate_config').select('*').eq('agent', agent).execute()
    rows = result.data or []

    if rows:
        cfg = rows[0]
    else:
        cfg = {'agent': agent, **DEFAULT_CONFIG}
        sb.table('decision_gate_config').insert(cfg).execute()
        print(f"[decision_gate] created default config for agent '{agent}'")

    _config_cache[agent] = cfg
    return cfg


# ─────────────────────────────────────────────────────────────
# The gate
# ─────────────────────────────────────────────────────────────

class GateDecision(NamedTuple):
    auto_executed: bool
    p: float
    tau: float
    logit: float
    row_id: Optional[str]
    hitl_item_id: Optional[str]

    @property
    def needs_hitl(self) -> bool:
        return not self.auto_executed

    def explain(self) -> str:
        verdict = 'AUTO' if self.auto_executed else 'HITL'
        return (
            f"[{verdict}] p={self.p:.4f} (odds {odds(self.p):.1f}:1) "
            f"tau={self.tau:.4f} z={self.logit:+.3f}"
        )


def evaluate(
    agent: str,
    decision_ref: str,
    z: float,
    *,
    title: Optional[str] = None,
    context: Optional[str] = None,
    item_type: str = 'low_confidence',
    division: Optional[str] = None,
    source_thought_id: Optional[str] = None,
) -> GateDecision:
    """
    Score a decision and route it.

    `z` is the RAW logit — the pre-sigmoid score. Pass log-odds, not a
    probability. If your scorer emits a probability, wrap it: `logit(p)`.

    Returns a GateDecision. The caller performs the action when
    `auto_executed` is True. Nothing is executed here.
    """
    cfg = get_config(agent)
    tau = float(cfg['tau'])

    # Platt-calibrated probability. With defaults (A=1, B=0) this is plain sigma(z).
    p = sigmoid(float(cfg['platt_a']) * z + float(cfg['platt_b']))
    auto = p > tau

    hitl_item_id: Optional[str] = None
    if not auto:
        hitl_row = {
            'item_type': item_type,
            'title': title or f'{agent}: {decision_ref}',
            'context': context,
            'agent': agent,
            'division': division,
            'confidence': p,
            'status': 'pending',
        }
        if source_thought_id:
            hitl_row['source_thought_id'] = source_thought_id
        inserted = sb.table('hitl_queue').insert(hitl_row).execute()
        if inserted.data:
            hitl_item_id = inserted.data[0]['id']

    ledger = {
        'agent': agent,
        'decision_ref': decision_ref,
        'logit': z,
        'p': p,
        'tau': tau,
        'auto_executed': auto,
        'hitl_item_id': hitl_item_id,
    }
    written = sb.table('decision_calibration').insert(ledger).execute()
    row_id = written.data[0]['id'] if written.data else None

    return GateDecision(
        auto_executed=auto,
        p=p,
        tau=tau,
        logit=z,
        row_id=row_id,
        hitl_item_id=hitl_item_id,
    )


def record_outcome(row_id: str, outcome: int) -> None:
    """
    Label a decision after the fact. 1 = correct, 0 = wrong.

    Auto-executed decisions need this called by whatever observes the result —
    they never pass through `hitl_review.py`, so they have no other label
    source. Without it the nightly fit sees only the sub-tau population
    (see the selection-bias warning in recalibrate_gate.py).
    """
    if outcome not in (0, 1):
        raise ValueError(f'outcome must be 0 or 1, got {outcome!r}')
    sb.table('decision_calibration').update({
        'outcome': outcome,
        'resolved_at': datetime.now(timezone.utc).isoformat(),
    }).eq('id', row_id).execute()


def sync_outcomes_from_hitl(agent: Optional[str] = None) -> int:
    """
    Pull Alan's approve/reject decisions across as training labels.

    approved → outcome 1 (gate was right to be unsure, and the action was good)
    rejected → outcome 0

    Deferred and still-pending items are skipped. Returns rows updated.
    """
    q = (sb.table('decision_calibration')
           .select('id, hitl_item_id')
           .is_('outcome', 'null')
           .not_.is_('hitl_item_id', 'null'))
    if agent:
        q = q.eq('agent', agent)
    pending = q.execute().data or []
    if not pending:
        return 0

    by_hitl = {r['hitl_item_id']: r['id'] for r in pending}
    resolved = (sb.table('hitl_queue')
                  .select('id, status')
                  .in_('id', list(by_hitl.keys()))
                  .in_('status', ['approved', 'rejected'])
                  .execute().data or [])

    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    for item in resolved:
        sb.table('decision_calibration').update({
            'outcome': 1 if item['status'] == 'approved' else 0,
            'resolved_at': now,
        }).eq('id', by_hitl[item['id']]).execute()
        updated += 1

    return updated


if __name__ == '__main__':
    n = sync_outcomes_from_hitl()
    print(f"[decision_gate] synced {n} outcome(s) from hitl_queue")
    for agent, cfg in ((a, get_config(a)) for a in ['juniper']):
        print(f"  {agent}: tau={cfg['tau']} (odds {odds(float(cfg['tau'])):.1f}:1) "
              f"floor={cfg['tau_floor']} A={cfg['platt_a']} B={cfg['platt_b']}")
