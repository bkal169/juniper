"""
JRIH — Nightly recalibration for the HITL sigmoid gate (Build #1)

Fits Platt scaling on resolved decisions, then re-derives tau from a target
precision. Writes both back to `decision_gate_config`.

    python recalibrate_gate.py            # all agents, apply
    python recalibrate_gate.py --dry-run  # fit + report, write nothing
    python recalibrate_gate.py juniper    # single agent

Guardrails (all configurable per-agent in decision_gate_config):
  * min_samples   — refuse to refit on thin data
  * tau_floor     — recalibration may tighten the gate, never remove it
  * max_tau_step  — clamp movement per run so one bad night can't swing it

Pure Python: requirements.txt has no numpy/scipy/sklearn.

Target project: Mycelium OS · zqrgazuaideuumksijhe.
"""

import math
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from config import sb
from decision_gate import sigmoid

# Minimum rows that must land above a candidate tau before its precision is
# trusted. Guards against picking a tau off two lucky samples.
MIN_AUTO_SUBSET = 10

# Platt fit hyperparameters — 2 parameters, so this converges easily.
LEARNING_RATE = 0.5
MAX_ITERS = 5000
GRAD_TOL = 1e-7


# ─────────────────────────────────────────────────────────────
# Platt scaling
# ─────────────────────────────────────────────────────────────

def fit_platt(z: Sequence[float], y: Sequence[int]) -> Tuple[float, float]:
    """
    Fit p = sigma(A*z + B) by gradient descent on cross-entropy.

    Uses Platt's target smoothing so a clean-separation batch doesn't drive
    |A| to infinity:
        y=1 → t+ = (N+ + 1) / (N+ + 2)
        y=0 → t- =        1 / (N- + 2)

    Under cross-entropy the gradient collapses to (p - t), which is the same
    (p_hat - y) form the primitives doc describes.
    """
    n_pos = sum(1 for v in y if v == 1)
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        # One-class batch carries no discriminative signal. Identity calibration.
        return 1.0, 0.0

    t_pos = (n_pos + 1.0) / (n_pos + 2.0)
    t_neg = 1.0 / (n_neg + 2.0)
    targets = [t_pos if v == 1 else t_neg for v in y]

    a, b = 1.0, 0.0
    n = float(len(z))

    for _ in range(MAX_ITERS):
        ga = gb = 0.0
        for zi, ti in zip(z, targets):
            err = sigmoid(a * zi + b) - ti
            ga += err * zi
            gb += err
        ga /= n
        gb /= n

        a -= LEARNING_RATE * ga
        b -= LEARNING_RATE * gb

        if abs(ga) < GRAD_TOL and abs(gb) < GRAD_TOL:
            break

    return a, b


def brier(p: Sequence[float], y: Sequence[int]) -> float:
    """Mean squared error of probability vs outcome. Lower is better-calibrated."""
    return sum((pi - yi) ** 2 for pi, yi in zip(p, y)) / len(p)


def log_loss(p: Sequence[float], y: Sequence[int], eps: float = 1e-12) -> float:
    total = 0.0
    for pi, yi in zip(p, y):
        pi = min(max(pi, eps), 1.0 - eps)
        total -= math.log(pi) if yi == 1 else math.log(1.0 - pi)
    return total / len(p)


# ─────────────────────────────────────────────────────────────
# tau derivation
# ─────────────────────────────────────────────────────────────

def derive_tau(
    p: Sequence[float],
    y: Sequence[int],
    target_precision: float,
) -> Optional[float]:
    """
    Smallest tau whose auto-executed subset (p > tau) hits target precision.

    Smallest — not safest — because we want maximum queue drainage subject to
    the precision floor. Returns None when no candidate clears the bar on
    enough samples; the caller then tightens conservatively instead of guessing.
    """
    candidates = sorted(set(p))
    best: Optional[float] = None

    for tau in candidates:
        subset = [(pi, yi) for pi, yi in zip(p, y) if pi > tau]
        if len(subset) < MIN_AUTO_SUBSET:
            continue
        precision = sum(yi for _, yi in subset) / len(subset)
        if precision >= target_precision:
            best = tau
            break  # candidates ascend, so the first hit is the smallest

    return best


# ─────────────────────────────────────────────────────────────
# Per-agent run
# ─────────────────────────────────────────────────────────────

def recalibrate_agent(agent: str, cfg: Dict, dry_run: bool = False) -> Dict:
    rows = (sb.table('decision_calibration')
              .select('logit, outcome, auto_executed')
              .eq('agent', agent)
              .not_.is_('outcome', 'null')
              .execute().data or [])

    report: Dict = {'agent': agent, 'n_resolved': len(rows), 'applied': False}

    min_samples = int(cfg['min_samples'])
    if len(rows) < min_samples:
        report['skipped'] = f'{len(rows)} resolved rows < min_samples {min_samples}'
        return report

    z = [float(r['logit']) for r in rows]
    y = [int(r['outcome']) for r in rows]

    n_auto = sum(1 for r in rows if r['auto_executed'])
    report['n_resolved_auto'] = n_auto
    report['n_resolved_hitl'] = len(rows) - n_auto

    # ── Selection bias ────────────────────────────────────────
    # HITL rows get labelled by Alan. Auto-executed rows only get labelled if
    # something calls record_outcome(). If none are labelled, we are fitting
    # entirely on the sub-tau population and EXTRAPOLATING above tau — exactly
    # the region tau governs. Say so; don't quietly ship a confident number.
    if n_auto == 0:
        report['warning'] = (
            'No resolved auto-executed rows. tau is being derived purely from the '
            'below-tau population — the fit extrapolates into the region it governs. '
            'Wire record_outcome() on auto-executed paths before trusting this tau.'
        )

    a_old, b_old = float(cfg['platt_a']), float(cfg['platt_b'])
    p_old = [sigmoid(a_old * zi + b_old) for zi in z]

    a_new, b_new = fit_platt(z, y)
    p_new = [sigmoid(a_new * zi + b_new) for zi in z]

    report.update({
        'platt_a': round(a_new, 6),
        'platt_b': round(b_new, 6),
        'brier_before': round(brier(p_old, y), 6),
        'brier_after': round(brier(p_new, y), 6),
        'log_loss_before': round(log_loss(p_old, y), 6),
        'log_loss_after': round(log_loss(p_new, y), 6),
        'base_rate': round(sum(y) / len(y), 4),
    })

    tau_old = float(cfg['tau'])
    tau_floor = float(cfg['tau_floor'])
    max_step = float(cfg['max_tau_step'])
    target = float(cfg['target_precision'])

    derived = derive_tau(p_new, y, target)
    if derived is None:
        # Nothing clears the precision bar. Tighten by one step rather than
        # inventing a threshold — and never past 1.0.
        tau_new = min(1.0, tau_old + max_step)
        report['tau_note'] = (
            f'no candidate tau reached precision {target} on >= {MIN_AUTO_SUBSET} '
            f'samples; tightening by one step'
        )
    else:
        tau_new = derived

    # Clamp: floor first, then anti-whiplash step limit.
    tau_new = max(tau_new, tau_floor)
    tau_new = max(tau_old - max_step, min(tau_old + max_step, tau_new))
    tau_new = max(tau_new, tau_floor)
    tau_new = min(tau_new, 1.0)

    report['tau_before'] = round(tau_old, 6)
    report['tau_after'] = round(tau_new, 6)

    if not dry_run:
        sb.table('decision_gate_config').update({
            'tau': tau_new,
            'platt_a': a_new,
            'platt_b': b_new,
            'last_fit_at': datetime.now(timezone.utc).isoformat(),
            'last_fit_n': len(rows),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }).eq('agent', agent).execute()
        report['applied'] = True

    return report


def run(agents: Optional[List[str]] = None, dry_run: bool = False) -> List[Dict]:
    configs = sb.table('decision_gate_config').select('*').execute().data or []
    if agents:
        configs = [c for c in configs if c['agent'] in agents]

    reports = []
    for cfg in configs:
        reports.append(recalibrate_agent(cfg['agent'], cfg, dry_run=dry_run))
    return reports


def print_report(reports: List[Dict], dry_run: bool) -> None:
    mode = 'DRY RUN — nothing written' if dry_run else 'APPLIED'
    print(f"\n{'=' * 66}")
    print(f"  DECISION GATE RECALIBRATION — {mode}")
    print(f"{'=' * 66}\n")

    if not reports:
        print("  No agent configs found. Has schema_decision_calibration.sql run?\n")
        return

    for r in reports:
        print(f"  {r['agent']}  ({r['n_resolved']} resolved)")
        if 'skipped' in r:
            print(f"    skipped: {r['skipped']}\n")
            continue
        print(f"    labels:    {r['n_resolved_auto']} auto · {r['n_resolved_hitl']} hitl "
              f"· base rate {r['base_rate']}")
        print(f"    platt:     A={r['platt_a']}  B={r['platt_b']}")
        print(f"    brier:     {r['brier_before']} → {r['brier_after']}")
        print(f"    log loss:  {r['log_loss_before']} → {r['log_loss_after']}")
        print(f"    tau:       {r['tau_before']} → {r['tau_after']}")
        if 'tau_note' in r:
            print(f"    note:      {r['tau_note']}")
        if 'warning' in r:
            print(f"    WARNING:   {r['warning']}")
        print()

    print(f"{'=' * 66}\n")


if __name__ == '__main__':
    args = [a for a in sys.argv[1:]]
    dry = '--dry-run' in args
    named = [a for a in args if not a.startswith('--')]
    print_report(run(named or None, dry_run=dry), dry)
