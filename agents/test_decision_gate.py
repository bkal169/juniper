"""
JRIH — self-contained checks for the calibrated HITL sigmoid gate.

    python test_decision_gate.py

Plain stdlib, no pytest (requirements.txt has none), no database. It stubs
`config` in sys.modules so the gate's math can be exercised without Supabase
credentials — the DB paths are not under test here, the decision math is.

Exits non-zero on failure so it can gate a deploy.
"""

import math
import random
import sys
import types

# ── Stub `config` before importing the modules under test ────────────────────
if 'config' not in sys.modules:
    _stub = types.ModuleType('config')
    _stub.SUPABASE_URL = 'https://zqrgazuaideuumksijhe.supabase.co'

    class _NoDB:
        def table(self, *a, **k):
            raise RuntimeError('database not exercised by these tests')

    _stub.sb = _NoDB()
    sys.modules['config'] = _stub

from decision_gate import sigmoid, logit, odds            # noqa: E402
from recalibrate_gate import (                            # noqa: E402
    fit_platt, derive_tau, brier, log_loss,
)

_failures = []


def check(name: str, cond: bool, extra: str = '') -> None:
    status = 'PASS' if cond else 'FAIL'
    print(f'  {status}  {name}{(" " + extra) if extra else ""}')
    if not cond:
        _failures.append(name)


def test_sigmoid_and_logit() -> None:
    print('\n[1] sigmoid stability + logit roundtrip')
    check('sigmoid(1000) does not overflow', abs(sigmoid(1000.0) - 1.0) < 1e-12)
    check('sigmoid(-1000) does not overflow', sigmoid(-1000.0) < 1e-12)
    check('sigmoid(0) == 0.5', abs(sigmoid(0.0) - 0.5) < 1e-15)
    err = max(abs(logit(sigmoid(v)) - v) for v in (-8, -3, -0.5, 0, 0.5, 3, 8))
    check('logit(sigmoid(z)) == z', err < 1e-9, f'maxerr={err:.2e}')
    check('odds(0.95) ~= 19:1', abs(odds(0.95) - 19.0) < 1e-9)


def test_platt_recovers_parameters() -> None:
    print('\n[2] Platt recovers known parameters')
    random.seed(42)
    a_true, b_true = 1.8, -0.6
    z = [random.uniform(-4, 4) for _ in range(4000)]
    y = [1 if random.random() < sigmoid(a_true * zi + b_true) else 0 for zi in z]
    a, b = fit_platt(z, y)
    print(f'       true A={a_true} B={b_true}  ->  fit A={a:.3f} B={b:.3f}')
    check('A recovered', abs(a - a_true) < 0.25)
    check('B recovered', abs(b - b_true) < 0.25)


def test_calibration_improves_overconfident_scorer() -> None:
    print('\n[3] calibration improves a miscalibrated scorer')
    random.seed(7)
    # Raw scorer is overconfident: the true relationship is far flatter than z implies.
    z = [random.uniform(-6, 6) for _ in range(3000)]
    y = [1 if random.random() < sigmoid(0.35 * v + 0.2) else 0 for v in z]
    p_raw = [sigmoid(v) for v in z]                 # uncalibrated (A=1, B=0)
    a, b = fit_platt(z, y)
    p_cal = [sigmoid(a * v + b) for v in z]
    br, bc = brier(p_raw, y), brier(p_cal, y)
    lr, lc = log_loss(p_raw, y), log_loss(p_cal, y)
    print(f'       brier {br:.4f} -> {bc:.4f} | log_loss {lr:.4f} -> {lc:.4f}')
    check('brier improves', bc < br)
    check('log loss improves', lc < lr)


def test_one_class_batch_is_safe() -> None:
    print('\n[4] one-class batch degrades to identity (no infinities)')
    a, b = fit_platt([0.1, 0.5, 2.0, -1.0], [1, 1, 1, 1])
    check('identity calibration returned', a == 1.0 and b == 0.0, f'A={a} B={b}')
    a2, b2 = fit_platt([0.1, 0.5], [0, 0])
    check('finite params', math.isfinite(a2) and math.isfinite(b2))


def test_derive_tau() -> None:
    print('\n[5] derive_tau honours the target precision')
    p = [0.99] * 40 + [0.90] * 40 + [0.55] * 40
    y = [1] * 39 + [0] + [1] * 34 + [0] * 6 + [1] * 20 + [0] * 20
    tau = derive_tau(p, y, 0.95)
    print(f'       tau@0.95 = {tau}')
    check('a threshold was chosen', tau is not None)
    if tau is not None:
        subset = [(pi, yi) for pi, yi in zip(p, y) if pi > tau]
        precision = sum(v for _, v in subset) / len(subset)
        check('subset meets target', precision >= 0.95,
              f'precision={precision:.3f} n={len(subset)}')
    check('unreachable target returns None', derive_tau(p, y, 0.999999) is None)


if __name__ == '__main__':
    test_sigmoid_and_logit()
    test_platt_recovers_parameters()
    test_calibration_improves_overconfident_scorer()
    test_one_class_batch_is_safe()
    test_derive_tau()

    if _failures:
        print(f'\n{len(_failures)} FAILED: {", ".join(_failures)}\n')
        sys.exit(1)
    print('\nAll checks passed.\n')
