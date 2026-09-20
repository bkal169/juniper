"""Write-Ahead Log for durable Supabase writes.

Usage pattern:
    entry_id = wal_append({"type": "upsert_graph", ...})
    supabase_write(...)          # actual write
    wal_commit(entry_id)         # mark as committed

On startup call wal_replay() and re-submit any uncommitted entries.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

_DEFAULT_WAL_FILE = Path(__file__).parent.parent.parent.parent / "data" / "wal.jsonl"

# Module-level lock prevents concurrent replay/commit races on startup
_WAL_LOCK = Lock()


def _wal_path() -> Path:
    env_path = os.environ.get("JUNIPER_WAL_PATH")
    return Path(env_path) if env_path else _DEFAULT_WAL_FILE


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def wal_append(entry: dict) -> str:
    """Durably record *entry* before the Supabase write.

    Returns the assigned *_wal_id* string so the caller can commit later.
    fsyncs to guarantee durability across process crashes.
    """
    wal_file = _wal_path()
    wal_file.parent.mkdir(parents=True, exist_ok=True)
    entry_id = str(uuid.uuid4())
    record = {**entry, "_wal_id": entry_id, "_wal_committed": False}
    with _WAL_LOCK:
        with wal_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    logger.debug("WAL append id=%s type=%s", entry_id, entry.get("type", "unknown"))
    return entry_id


def wal_replay() -> list[dict]:
    """Return all uncommitted WAL entries (safe to call on every startup).

    Holds _WAL_LOCK for the duration so concurrent startup calls don't
    both replay the same entries.
    """
    wal_file = _wal_path()
    with _WAL_LOCK:
        if not wal_file.exists():
            return []

        pending: list[dict] = []
        for line in wal_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if not record.get("_wal_committed", False):
                    pending.append(record)
            except json.JSONDecodeError:
                logger.warning("WAL: skipping malformed line: %.80r", line)

        if pending:
            logger.info("WAL replay: %d uncommitted entries", len(pending))
        return pending


def wal_commit(entry_id: str) -> None:
    """Mark *entry_id* as committed so it is skipped on next replay."""
    wal_file = _wal_path()
    with _WAL_LOCK:
        if not wal_file.exists():
            return

        lines = wal_file.read_text(encoding="utf-8").splitlines()
        new_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
                if record.get("_wal_id") == entry_id:
                    record["_wal_committed"] = True
                    logger.debug("WAL commit id=%s", entry_id)
                new_lines.append(json.dumps(record))
            except json.JSONDecodeError:
                new_lines.append(stripped)

        wal_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def wal_stats() -> dict[str, int]:
    """Return counts of pending and committed entries in the WAL."""
    wal_file = _wal_path()
    with _WAL_LOCK:
        if not wal_file.exists():
            return {"pending": 0, "committed": 0}

        pending = committed = 0
        for line in wal_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("_wal_committed", False):
                    committed += 1
                else:
                    pending += 1
            except json.JSONDecodeError:
                pass
        return {"pending": pending, "committed": committed}


def flush() -> None:
    """No-op — all writes are synchronous. Called by SIGTERM handler."""
    logger.info("WAL flush (no pending in-memory state)")
