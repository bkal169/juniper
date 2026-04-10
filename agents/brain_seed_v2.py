"""
JRIH Second Brain — Brain Seeder v2
Seeds foundational knowledge into Supabase thoughts table.
Run once to bootstrap, then feed the brain through agents.

Usage:
    python -m agents.brain_seed_v2
"""

import uuid
from datetime import datetime, timezone
from agents.config import sb, embed

SEEDS = [
    # ─── JRIH Core ───────────────────────────────────────────
    {
        "content": "JRIH (Juniper Rose Investments & Holdings) is a multi-division holding company founded by Alan Augustin. Brooklyn-born, Sarasota-based. North star: $100M+ in assets. Five operating divisions: JRi (AI/SaaS), JR Capital (DAC funding, financial services), JR Realty (real estate, MLO, 2-15 insurance), Kintsugi Development Group (real estate development), Heart of Juniper Foundation (community philanthropy).",
        "source": "jrih",
        "entry_type": "reference",
        "tags": ["founder", "structure", "alan", "divisions"],
        "agent": "brain-seeder-v2",
    },
    {
        "content": "Alan Augustin is the founder and principal of JRIH. Brooklyn-born, Sarasota-based. Background in real estate, finance, AI/SaaS. Licensed MLO and 2-15 insurance agent in Florida. Builder of AxiomOS and LumenaOS. Operator of Heart of Juniper Foundation.",
        "source": "personal",
        "entry_type": "reference",
        "tags": ["alan", "founder", "bio"],
        "agent": "brain-seeder-v2",
    },
    # ─── Divisions ────────────────────────────────────────────
    {
        "content": "JRi (Juniper Rose Intelligence) is the AI/SaaS division of JRIH. Products: AxiomOS (AI-native operating system for knowledge workers), LumenaOS (agent-powered CRM/ERP for SMBs), ARO (Agent Revenue Optimization — monetized autonomous agents). JRi is the technology engine of the holding company.",
        "source": "axiom",
        "entry_type": "reference",
        "tags": ["jri", "axiom", "lumena", "aro", "saas", "ai"],
        "agent": "brain-seeder-v2",
    },
    {
        "content": "JR Capital is the financial services division of JRIH. Focuses on DAC (Diversified Asset Capital) funding, bridge loans, and financial instruments. Works closely with JR Realty for deal financing. Revenue model: origination fees, spread income, advisory.",
        "source": "jrih",
        "entry_type": "reference",
        "tags": ["jr_capital", "finance", "dac", "funding"],
        "agent": "brain-seeder-v2",
    },
    {
        "content": "JR Realty is the real estate division of JRIH. Covers residential and commercial transactions, MLO (Mortgage Loan Originator) services, and 2-15 insurance in Florida. Alan is licensed for both. Revenue: commissions, origination, insurance premiums.",
        "source": "jrih",
        "entry_type": "reference",
        "tags": ["jr_realty", "real_estate", "mlo", "insurance", "florida"],
        "agent": "brain-seeder-v2",
    },
    {
        "content": "Kintsugi Development Group is the real estate development arm of JRIH. Named after the Japanese art of repairing with gold — finding beauty in broken things, adding value through renovation and development. Focus: Florida properties, value-add renovations, ground-up development.",
        "source": "jrih",
        "entry_type": "reference",
        "tags": ["kintsugi", "development", "real_estate", "florida"],
        "agent": "brain-seeder-v2",
    },
    {
        "content": "Heart of Juniper Foundation (HOJ) is the philanthropic arm of JRIH. Community-focused. Sarasota-based. Programs: youth mentorship, community grants, financial literacy workshops. Operates with separate governance but shared infrastructure. Dedicated HOJ agent runs 3x/week.",
        "source": "heart_of_juniper",
        "entry_type": "reference",
        "tags": ["hoj", "foundation", "philanthropy", "community"],
        "agent": "brain-seeder-v2",
    },
    # ─── Products ─────────────────────────────────────────────
    {
        "content": "AxiomOS is an AI-native operating system for knowledge workers. Built by JRi. Features: agent orchestration, second brain integration, workflow automation, MCP server integration. Target users: founders, operators, professionals who need AI-augmented decision-making. Tech stack: Next.js, Supabase, LangGraph, Vercel.",
        "source": "axiom",
        "entry_type": "reference",
        "tags": ["axiom", "product", "saas", "ai_os"],
        "agent": "brain-seeder-v2",
    },
    {
        "content": "LumenaOS is an agent-powered CRM/ERP for SMBs. Built by JRi. Features: AI agents handle customer communication, lead routing, invoicing, and reporting. Target: small businesses who can't afford a full ops team. Lumen = light; the system illuminates business operations.",
        "source": "lumena",
        "entry_type": "reference",
        "tags": ["lumena", "product", "crm", "erp", "smb"],
        "agent": "brain-seeder-v2",
    },
    {
        "content": "ARO (Agent Revenue Optimization) is JRi's monetized autonomous agent platform. Agents perform revenue-generating tasks: lead qualification, content creation, market research, competitive intelligence. Revenue model: per-agent subscription, usage-based pricing, enterprise licensing.",
        "source": "aro",
        "entry_type": "reference",
        "tags": ["aro", "agents", "revenue", "monetization"],
        "agent": "brain-seeder-v2",
    },
    # ─── Agent Architecture ──────────────────────────────────
    {
        "content": "The JRIH Second Brain agent architecture: Rose (personal operator, Alan's interface), Juniper (headless orchestrator, runs JRIH operations, has execute rights), Junior (adversarial critic, gates Juniper decisions, self-improving), Juno (intelligence engine, research + synthesis), Claude Advisor (strategic counsel, elder voice). Supporting agents: Ingest, Wiki, Retrieval, Synthesis, Gatekeeper, Competitive Intel, HOJ Agent.",
        "source": "system",
        "entry_type": "reference",
        "tags": ["agents", "architecture", "rose", "juniper", "junior", "juno"],
        "agent": "brain-seeder-v2",
    },
    {
        "content": "Juniper-Junior governance loop: Juniper proposes an action -> Junior evaluates (confidence, risk, alignment) -> Junior verdict (approve/reject/revise) -> If approved and confidence >= 0.92, auto-execute. If 0.75-0.92, flag for morning review (HITL). If < 0.75 or Junior rejects, decision shelved. Max 2 revision cycles before escalation to HITL.",
        "source": "system",
        "entry_type": "reference",
        "tags": ["governance", "juniper", "junior", "hitl", "confidence"],
        "agent": "brain-seeder-v2",
    },
    # ─── Model Routing ────────────────────────────────────────
    {
        "content": "Model routing strategy: gemma-4 (Ollama local, free) for classification/grading/filtering. Kimi k2.5 (Moonshot 128k) for long-doc ingestion and brand swarm workers. Claude Sonnet 4.6 for synthesis, reasoning, code generation, critique. Claude Opus 4.6 for strategy, architecture, hard bugs. text-embedding-3-small for all embeddings. Principle: best+highest use, no wasted tokens.",
        "source": "system",
        "entry_type": "reference",
        "tags": ["models", "routing", "cost", "optimization"],
        "agent": "brain-seeder-v2",
    },
    # ─── Infrastructure ───────────────────────────────────────
    {
        "content": "JRIH infrastructure: Supabase (Postgres + pgvector, project: ubdhpacoqmlxudcvhyuu) for persistent memory. Railway for agent hosting. Vercel for web apps (team: team_k9pMkrpQoIolWK5TG0xkDSXD). Notion for LifeOS dashboard. n8n for workflow automation (bkalan169.app.n8n.cloud). GitHub for version control. Obsidian vault for local knowledge. Graphify for knowledge graph indexing.",
        "source": "infra",
        "entry_type": "reference",
        "tags": ["infrastructure", "supabase", "railway", "vercel", "notion", "n8n"],
        "agent": "brain-seeder-v2",
    },
    {
        "content": "Vault structure follows modified PARA: raw/ (drop zone, agent trigger zone), wiki/ (AI-maintained entity pages), outputs/ (agent deliverables), projects/ (active work), areas/ (ongoing responsibilities), resources/ (reference material), archive/ (inactive), system/ (config). Naming: wiki pages = ENTITY_NAME.md, raw drops = YYYY-MM-DD_topic_source.md, outputs = YYYY-MM-DD_type_title.md.",
        "source": "system",
        "entry_type": "reference",
        "tags": ["vault", "para", "structure", "naming"],
        "agent": "brain-seeder-v2",
    },
    # ─── Strategic Context ────────────────────────────────────
    {
        "content": "JRIH growth trajectory: Now — foundation, capture flowing, search working. 3 months — Juniper operational, JRi division running. 6 months — all 5 divisions namespaced, Rose + Juno live. 12 months — full self-hosted, Open Notebook, no Google dependency. 18 months — Juno as AxiomOS product, brain becomes what we sell.",
        "source": "jrih",
        "entry_type": "decision",
        "tags": ["strategy", "roadmap", "growth", "timeline"],
        "agent": "brain-seeder-v2",
    },
    {
        "content": "Florida market focus: Sarasota-Bradenton MSA for real estate (JR Realty, Kintsugi). Tampa Bay corridor for expansion. Florida regulatory environment: MLO licensing, 2-15 insurance, real estate development permits. Competitive advantage: local market knowledge + AI augmentation.",
        "source": "intel",
        "entry_type": "reference",
        "tags": ["florida", "market", "sarasota", "real_estate"],
        "agent": "brain-seeder-v2",
    },
]


def seed_brain():
    """Seed foundational knowledge into Supabase."""
    print(f"[brain-seeder-v2] Seeding {len(SEEDS)} foundational thoughts...")
    inserted = 0
    errors = 0

    for seed in SEEDS:
        try:
            # Generate embedding
            vec = embed(seed["content"])

            row = {
                "id": str(uuid.uuid4()),
                "content": seed["content"],
                "source": seed["source"],
                "entry_type": seed["entry_type"],
                "agent": seed["agent"],
                "tags": seed["tags"],
                "embedding": vec,
                "confidence": 1.0,
                "metadata": {
                    "seeded": True,
                    "seed_version": "v2",
                    "seeded_at": datetime.now(timezone.utc).isoformat(),
                },
            }

            sb.table("thoughts").insert(row).execute()
            inserted += 1
            print(f"  [{inserted}/{len(SEEDS)}] {seed['source']}: {seed['content'][:60]}...")

        except Exception as e:
            errors += 1
            print(f"  [ERROR] {seed['source']}: {e}")

    print(f"\n[brain-seeder-v2] Done. Inserted: {inserted}, Errors: {errors}")
    return inserted, errors


if __name__ == "__main__":
    seed_brain()
