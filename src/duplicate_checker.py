"""Wraps the `check_hitl_duplicate` RPC from 20260416000000_phase1_5_foundation.

Callers pass a candidate description and a similarity threshold; the RPC
returns up to 5 close matches from the last 7 days of pending approvals.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from supabase import Client, create_client


@dataclass
class DuplicateMatch:
    existing_id: str
    similarity: float


def _client() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def find_duplicates(description: str, threshold: float = 0.75) -> list[DuplicateMatch]:
    rows = _client().rpc(
        "check_hitl_duplicate",
        {"p_description": description, "p_threshold": threshold},
    ).execute()
    return [DuplicateMatch(**r) for r in rows.data]


if __name__ == "__main__":
    print("juniper.duplicate_checker — skeleton loaded")
