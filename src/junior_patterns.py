"""Junior self-improvement loop — harvests patterns from approvals + feedback.

Reads recent `agent_approvals` outcomes, groups by (action_type, agent_role),
and updates `junior_patterns.success_count` / `failure_count`.
"""
from __future__ import annotations

import os

from supabase import Client, create_client


def _client() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def harvest_recent(hours: int = 24) -> int:
    """Scan resolved approvals, update junior_patterns, return rows touched."""
    # Skeleton — real implementation groups by (action, role) and upserts.
    _ = hours
    return 0


if __name__ == "__main__":
    print("juniper.junior_patterns — skeleton loaded")
