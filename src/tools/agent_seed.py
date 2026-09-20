"""Seed Phase 0 + Phase 1 agent roster into kg_nodes.

Upserts agents into the kg_nodes table as node_type="agent". Safe to run
multiple times — uses on_conflict="label" so existing rows are updated,
not duplicated.

Roster history:
- Phase 0 (2026-04-25): Alfred, Vision, OpenClaw, AxiomOS Agent
- Phase 1 (2026-05-03): Sage (JRR brokerage), Bishop (AxiomOS SDR)

Run:
    cd juniper
    poetry run python -m src.tools.agent_seed
"""
from __future__ import annotations

import os

from supabase import Client, create_client


# ---------------------------------------------------------------------------
# Phase 0 agents
# ---------------------------------------------------------------------------

PHASE0_AGENTS: list[dict] = [
    {
        "label": "Alfred",
        "node_type": "agent",
        "confidence": 1.0,
        "metadata": {
            "role": "Investment Intelligence",
            "color": "#f59e0b",
            "reports_to": "Juno",
            "phase": 0,
            "status": "scaffold",
            "owns": ["portfolio_tracking", "roi_scoring", "market_data", "investment_thesis"],
            "data_sources": ["robinhood", "moomoo", "yahoo_finance"],
        },
    },
    {
        "label": "Vision",
        "node_type": "agent",
        "confidence": 1.0,
        "metadata": {
            "role": "Visual & Image Processing",
            "color": "#22d3ee",
            "reports_to": "Juniper",
            "phase": 0,
            "status": "scaffold",
            "owns": ["property_photo_analysis", "document_scanning", "listing_image_qa", "brand_visual_review"],
            "model_primary": "claude-sonnet-4-6",
        },
    },
    {
        "label": "OpenClaw",
        "node_type": "agent",
        "confidence": 1.0,
        "metadata": {
            "role": "Autonomous Web Research",
            "color": "#f97316",
            "reports_to": "Junior",
            "phase": 0,
            "status": "active",
            "owns": ["web_scraping", "property_market_data", "competitive_intel", "deal_prospecting"],
            "daemon_url": "http://127.0.0.1:18788",
            "public_url": "https://openclaw.jrih.dev",
            "tool_module": "src.tools.openclaw",
        },
    },
    {
        "label": "AxiomOS Agent",
        "node_type": "agent",
        "confidence": 1.0,
        "metadata": {
            "role": "Execution Arm",
            "color": "#818cf8",
            "reports_to": "Juno",
            "phase": 0,
            "status": "scaffold",
            "owns": ["outreach_sequences", "deal_stage_tracking", "investor_comms", "crm_ops"],
            "hitl_required": True,
            "systems": ["apollo", "axiom_pipeline", "n8n"],
        },
    },
]


# ---------------------------------------------------------------------------
# Phase 1 agents — Revenue Pod completion (Sage + Bishop spawned 2026-05-03)
# ---------------------------------------------------------------------------

PHASE1_AGENTS: list[dict] = [
    {
        "label": "Sage",
        "node_type": "agent",
        "confidence": 1.0,
        "metadata": {
            "role": "JRR Brokerage Agent",
            "color": "#8b5cf6",
            "reports_to": "Juniper",
            "phase": 1,
            "status": "scaffold",
            "spawned": "2026-05-03",
            "owns": [
                "jrr_listings",
                "jrr_buyer_rep",
                "jrr_transactions",
                "jrr_sphere_farm",
                "mls_sync",
                "showing_coord",
                "transaction_milestones",
                "close_coord",
            ],
            "tables": [
                "sage_listings",
                "sage_buyers",
                "sage_transactions",
                "sage_sphere",
            ],
            "vertical": "real_estate_brokerage",
            "scope_exclusions": ["land_dev", "rei_partnerships", "wholesale"],
            "quarterback_for": ["JRR_listings_buyers"],
            "posture": "advisory_coordinating",
            "compliance": ["respa", "fair_housing", "mls_rules", "florida_real_estate_law"],
        },
    },
    {
        "label": "Bishop",
        "node_type": "agent",
        "confidence": 1.0,
        "metadata": {
            "role": "AxiomOS Sales Development",
            "color": "#06b6d4",
            "reports_to": "Juniper",
            "phase": 1,
            "status": "scaffold",
            "spawned": "2026-05-03",
            "owns": [
                "axiomos_outbound",
                "icp_prospecting",
                "sequence_management",
                "demo_scheduling",
                "proposal_drafts",
            ],
            "tables": [
                "bishop_pipeline",
                "bishop_sequences",
                "bishop_demos",
            ],
            "icp_segments": ["family_office", "mid_market", "agency", "re_team"],
            "icp_disqualifiers": ["pre_revenue", "enterprise_500m_plus", "single_operator", "regulated_unapproved"],
            "voice_register": "operator_to_operator_peer",
            "quarterback_for": ["axiomos_whitelabel_automation"],
            "compliance": ["can_spam", "gdpr", "ccpa"],
            "send_ceilings": {"first_touch_per_day": 30, "first_touch_per_hour": 5, "follow_up_per_day": 100},
        },
    },
]


# Combined roster for one-shot seeding
ALL_AGENTS: list[dict] = PHASE0_AGENTS + PHASE1_AGENTS


def _client() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def seed_agents(dry_run: bool = False) -> list[str]:
    """Upsert Phase 0 + Phase 1 agents into kg_nodes. Returns list of seeded labels."""
    if dry_run:
        print("[agent_seed] DRY RUN — would upsert:")
        for a in ALL_AGENTS:
            print(f"  {a['label']} ({a['metadata']['role']}) [phase {a['metadata']['phase']}]")
        return [a["label"] for a in ALL_AGENTS]

    client = _client()
    seeded: list[str] = []

    for agent in ALL_AGENTS:
        client.table("kg_nodes").upsert(
            {
                "label": agent["label"],
                "node_type": agent["node_type"],
                "confidence": agent["confidence"],
                "metadata": agent["metadata"],
            },
            on_conflict="label",
        ).execute()
        seeded.append(agent["label"])
        print(f"[agent_seed] ✓ upserted: {agent['label']} [phase {agent['metadata']['phase']}]")

    return seeded


if __name__ == "__main__":
    import sys

    dry = "--dry-run" in sys.argv
    labels = seed_agents(dry_run=dry)
    print(f"[agent_seed] done — {len(labels)} agents seeded: {', '.join(labels)}")
