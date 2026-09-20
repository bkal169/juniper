"""Thread-safe circuit breaker for protecting Supabase calls.

States:
  CLOSED   — normal operation, all calls pass through
  OPEN     — too many failures; calls are rejected immediately
  HALF_OPEN — testing recovery; one probe call is allowed
"""
from __future__ import annotations

import logging
import time
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any

_LOG_DIR = Path(__file__).parent.parent.parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler(_LOG_DIR / "circuit_breaker.log"),
        logging.StreamHandler(),
    ],
    format="%(asctime)s [circuit_breaker] %(levelname)s %(message)s",
)
logger = logging.getLogger("circuit_breaker")


class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is OPEN."""


class CircuitBreaker:
    """Protect a callable against cascading failures.

    Args:
        failure_threshold: number of failures in *failure_window_s* seconds before OPEN
        failure_window_s:  rolling window for counting failures (seconds)
        recovery_timeout_s: how long to stay OPEN before trying HALF_OPEN
        call_timeout_s:  elapsed time beyond which a call counts as a failure
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        failure_window_s: float = 60.0,
        recovery_timeout_s: float = 30.0,
        call_timeout_s: float = 3.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._failure_window_s = failure_window_s
        self._recovery_timeout_s = recovery_timeout_s
        self._call_timeout_s = call_timeout_s

        self._state = State.CLOSED
        self._failure_times: list[float] = []
        self._last_open_at: float = 0.0
        self._half_open_probe_in_flight: bool = False
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def state(self) -> State:
        return self._state

    def get_state(self) -> dict[str, Any]:
        """Return current circuit state as a serialisable dict."""
        with self._lock:
            last_failure = self._failure_times[-1] if self._failure_times else None
            return {
                "state": self._state.value,
                "failure_count": len(self._failure_times),
                "last_failure_time": last_failure,
                "last_open_at": self._last_open_at if self._last_open_at else None,
            }

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED — for use by ops/runbook recovery."""
        with self._lock:
            self._state = State.CLOSED
            self._failure_times.clear()
            self._last_open_at = 0.0
            self._half_open_probe_in_flight = False
        logger.info("CircuitBreaker manually reset → CLOSED")

    def call(self, fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Execute *fn* guarded by the circuit breaker.

        Raises:
            CircuitOpenError: if the circuit is OPEN and recovery window hasn't elapsed
            TimeoutError: if the call exceeded *call_timeout_s*
            Any exception raised by *fn* (also recorded as a failure)
        """
        self._maybe_transition_to_half_open()

        with self._lock:
            if self._state == State.OPEN:
                elapsed = time.monotonic() - self._last_open_at
                raise CircuitOpenError(
                    f"circuit OPEN — {elapsed:.0f}s / {self._recovery_timeout_s}s elapsed"
                )
            if self._state == State.HALF_OPEN:
                if self._half_open_probe_in_flight:
                    raise CircuitOpenError("circuit HALF_OPEN — probe already in flight")
                self._half_open_probe_in_flight = True

        start = time.monotonic()
        try:
            result = fn(*args, **kwargs)
            elapsed = time.monotonic() - start
            if elapsed > self._call_timeout_s:
                self._record_failure(f"slow call ({elapsed:.1f}s > {self._call_timeout_s}s timeout)")
                raise TimeoutError(
                    f"call took {elapsed:.1f}s, exceeding {self._call_timeout_s}s threshold"
                )
            self._record_success()
            return result
        except (CircuitOpenError, TimeoutError):
            raise
        except Exception as exc:
            self._record_failure(str(exc))
            raise

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _maybe_transition_to_half_open(self) -> None:
        with self._lock:
            if (
                self._state == State.OPEN
                and time.monotonic() - self._last_open_at >= self._recovery_timeout_s
            ):
                self._state = State.HALF_OPEN
                self._half_open_probe_in_flight = False
                logger.info("CircuitBreaker → HALF_OPEN (testing recovery)")

    def _record_success(self) -> None:
        with self._lock:
            self._half_open_probe_in_flight = False
            if self._state == State.HALF_OPEN:
                self._state = State.CLOSED
                self._failure_times.clear()
                logger.info("CircuitBreaker → CLOSED (recovery succeeded)")

    def _record_failure(self, reason: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._half_open_probe_in_flight = False
            # Prune failures outside the rolling window
            cutoff = now - self._failure_window_s
            self._failure_times = [t for t in self._failure_times if t >= cutoff]
            self._failure_times.append(now)

            if self._state != State.OPEN and (
                self._state == State.HALF_OPEN
                or len(self._failure_times) >= self._failure_threshold
            ):
                self._state = State.OPEN
                self._last_open_at = now
                logger.warning(
                    "CircuitBreaker → OPEN (reason=%r, failures=%d in %ds window)",
                    reason,
                    len(self._failure_times),
                    int(self._failure_window_s),
                )
