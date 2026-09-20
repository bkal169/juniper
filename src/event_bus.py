"""Supabase polling consumer for `agent_learning_bus` with handler registry.

Usage:
    bus = EventBus()

    @bus.on("junior", "task.completed")
    async def _(ev: BusEvent) -> None:
        ...

    await bus.run()  # blocks, drains agent_learning_bus on poll_interval

Implementation note: Supabase's Python client doesn't have a first-class
realtime websocket API yet, so we poll `agent_learning_bus` on an interval.
This is intentional — polling keeps the service trivially redeployable and
the event volume is low (hundreds/day, not thousands/sec).

Schema mapping (table column → BusEvent field):
    id                 → id
    source_agent_id    → source
    signal_type        → kind
    target_agent_id    → ref_type   (preserved as the routing target)
    id (uuid as str)   → ref_id     (preserved for handler back-references)
    payload (jsonb)    → payload
    created_at         → occurred_at

After successful handler dispatch, `applied=true` is written back so we
don't re-fire. The select filter `applied=eq.false` enforces signal-loss
contract — every row is processed exactly once.
"""
from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable

from supabase import Client, create_client

Handler = Callable[["BusEvent"], Awaitable[None]]

_DEFAULT_TENANT = "f2d21a43-4ba7-4f7f-8bf8-49ef986ad3dc"


def _wl_tenant_id() -> str:
    return os.environ.get("WL_TENANT_ID", _DEFAULT_TENANT)


@dataclass
class BusEvent:
    id: str  # uuid string from agent_learning_bus.id
    source: str  # source_agent_id
    kind: str  # signal_type
    ref_type: str | None  # target_agent_id (preserved for handler routing)
    ref_id: str | None  # row id (uuid as string)
    payload: dict
    occurred_at: datetime


class EventBus:
    def __init__(self, poll_interval_s: float = 2.0) -> None:
        self._client: Client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
        self._handlers: dict[tuple[str, str], list[Handler]] = {}
        self._poll_interval = poll_interval_s
        self._stop = asyncio.Event()
        # last seen created_at (cursor) — used only on cold start so we don't
        # re-fire historical applied=false rows that pre-date this deploy.
        self._cursor_created_at: str | None = None

    def on(self, source: str, kind: str) -> Callable[[Handler], Handler]:
        def decorator(fn: Handler) -> Handler:
            self._handlers.setdefault((source, kind), []).append(fn)
            return fn
        return decorator

    async def emit(self, event: BusEvent) -> None:
        # target_agent_id is NOT NULL on the live table; default to 'broadcast'
        # when the caller didn't specify a target.
        target = event.ref_type or "broadcast"
        self._client.table("agent_learning_bus").insert({
            "signal_type":     event.kind,
            "source_agent_id": event.source,
            "target_agent_id": target,
            "payload":         event.payload,
            "applied":         False,
            "wl_tenant_id":    _wl_tenant_id(),
        }).execute()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.stop)
            except NotImplementedError:
                pass

        # Cold start: leave cursor None so the first poll drains the entire
        # applied=false backlog. Subsequent polls advance the cursor naturally
        # via _drain_once. Pre-Phase-14.3 behavior pinned cursor to NOW() and
        # silently dropped historical signals on every restart — that bug left
        # 60+ unapplied rows accumulating across reboots. Now we drain them.
        self._cursor_created_at = None

        while not self._stop.is_set():
            try:
                await self._drain_once()
            except Exception as e:
                print(f"[event_bus] poll error: {e!r}")

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval)
            except asyncio.TimeoutError:
                pass

    async def _latest_created_at(self) -> str | None:
        rows = (
            self._client.table("agent_learning_bus")
            .select("created_at")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if rows.data:
            return rows.data[0]["created_at"]
        return None

    async def _drain_once(self) -> None:
        q = (
            self._client.table("agent_learning_bus")
            .select("id,source_agent_id,signal_type,target_agent_id,payload,created_at")
            .eq("applied", False)
        )
        if self._cursor_created_at is not None:
            q = q.gte("created_at", self._cursor_created_at)
        rows = q.order("created_at").limit(500).execute()

        for raw in rows.data:
            try:
                ts_raw = raw.get("created_at") or ""
                occurred_at = datetime.fromisoformat(
                    ts_raw.replace("Z", "+00:00")
                ).astimezone(timezone.utc) if ts_raw else datetime.now(timezone.utc)
            except Exception:
                occurred_at = datetime.now(timezone.utc)

            ev = BusEvent(
                id=str(raw["id"]),
                source=raw.get("source_agent_id") or "",
                kind=raw.get("signal_type") or "",
                ref_type=raw.get("target_agent_id"),
                ref_id=str(raw["id"]),
                payload=raw.get("payload") or {},
                occurred_at=occurred_at,
            )

            handlers = self._handlers.get((ev.source, ev.kind), [])
            dispatched_ok = True
            for handler in handlers:
                try:
                    await handler(ev)
                except Exception as e:
                    dispatched_ok = False
                    print(
                        f"[event_bus] handler {handler.__name__} error on "
                        f"{ev.source}/{ev.kind}: {e!r}"
                    )

            # Mark applied=true only after a clean pass (or when there are no
            # registered handlers — we still mark to stop re-polling that row).
            if dispatched_ok:
                try:
                    self._client.table("agent_learning_bus").update(
                        {"applied": True}
                    ).eq("id", ev.id).execute()
                except Exception as e:
                    print(f"[event_bus] failed to mark applied id={ev.id}: {e!r}")

            # Advance cursor regardless so we don't re-scan the same row.
            self._cursor_created_at = raw.get("created_at") or self._cursor_created_at


if __name__ == "__main__":
    bus = EventBus()

    @bus.on("budget_guard", "budget.exceeded")
    async def _on_budget_exceeded(ev: BusEvent) -> None:
        print(f"[event_bus] BUDGET EXCEEDED: {ev.payload}")

    @bus.on("juniper", "embeddings.stale")
    async def _on_stale(ev: BusEvent) -> None:
        print(f"[event_bus] stale embeddings: {ev.payload.get('count')}")

    asyncio.run(bus.run())
