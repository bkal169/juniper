# JRIH Second Brain — Handoff Document
**Version:** v2 — Seed JRIH Brain
**Date:** 2026-04-10
**Branch:** claude/seed-jrih-brain-v2-22JJP

## What Was Built

A complete second brain infrastructure for JRIH (Juniper Rose Investments & Holdings). This is the foundational layer that turns Alan's knowledge, decisions, and business operations into a persistent, searchable, AI-augmented memory system.

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  Alan (HITL)                                        │
│    ↕ Rose (personal operator)                       │
├─────────────────────────────────────────────────────┤
│  Juniper (orchestrator) ←→ Junior (adversarial QA)  │
│    ↕ LangGraph state machine                        │
├─────────────────────────────────────────────────────┤
│  Specialized Agents                                 │
│    Juno (intel) · HOJ · Advisor · Synthesis         │
├─────────────────────────────────────────────────────┤
│  Supabase (pgvector + BM25 hybrid search)           │
│  MCP Server (5 tools for Claude Desktop)            │
│  Cron (APScheduler on Railway)                      │
│  n8n (Gmail ingest workflow)                        │
│  GitHub Webhook (vault push → auto-ingest)          │
└─────────────────────────────────────────────────────┘
```

### File Manifest

| Path | Purpose |
|------|---------|
| `supabase/schema.sql` | Core tables: thoughts, hitl_queue, digests, metrics. Hybrid search function. |
| `supabase/schema_juniper.sql` | Juniper audit, Junior patterns, graph relationships. |
| `agents/config.py` | Model routing, Supabase client, embeddings, division config. |
| `agents/langgraph_agents.py` | LangGraph state machine: perceive → reason → junior_gate → execute → log. |
| `agents/juniper.py` | Juniper orchestrator: division rotation, cycle management. |
| `agents/junior.py` | Junior adversarial QA: pattern learning, rule evolution, gating. |
| `agents/specialized_agents.py` | Juno, HOJ, Advisor, Junior Learning, HITL Review agents. |
| `agents/hitl_review.py` | HITL queue management: 48hr escalation, digest summaries. |
| `agents/brain_seed_v2.py` | Foundational knowledge seeder (run once). |
| `agents/webhook.py` | GitHub webhook handler: push → ingest Markdown → Supabase. |
| `agents/cron_v2.py` | APScheduler: Juniper cycles, intel scans, HITL checks, digests. |
| `mcp/server.ts` | MCP server: brain_search, brain_store, brain_hitl, brain_stats, brain_recent. |
| `mcp/package.json` | MCP dependencies. |
| `mcp/claude-desktop-config.json` | Claude Desktop MCP config template. |
| `agents/n8n_gmail_workflow.json` | n8n workflow: Gmail → classify → Supabase. |
| `vault-init/CLAUDE.md` | Agent rules, namespaces, vault structure. |
| `vault-init/system/AGENTS.md` | Agent roster and capabilities. |
| `vault-init/system/prompts/rose_onboarding.md` | Rose persona + onboarding prompt. |
| `scripts/graphify_bridge.py` | Graphify → Supabase graph_relationships sync. |
| `scripts/post-commit` | Git hook: auto-push after commit. |
| `railway.toml` | Railway deployment config. |
| `requirements.txt` | Python dependencies. |
| `docs/ROLES.md` | Agent roles and escalation paths. |
| `.gitignore` | Standard ignores. |

### Deployment Steps

1. **Supabase**: Run `schema.sql` then `schema_juniper.sql` in SQL Editor
2. **Seed**: `SUPABASE_SERVICE_KEY=xxx python -m agents.brain_seed_v2`
3. **MCP**: Copy `mcp/claude-desktop-config.json` to `~/Library/Application Support/Claude/claude_desktop_config.json`, update paths
4. **Railway**: `railway up` (set env vars: SUPABASE_SERVICE_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY)
5. **n8n**: Import `agents/n8n_gmail_workflow.json`, configure Gmail OAuth + Supabase key
6. **GitHub Webhook**: Point vault repo webhook to Railway `/webhook/github` endpoint

### Environment Variables Required

| Variable | Where | Purpose |
|----------|-------|---------|
| `SUPABASE_URL` | Railway, MCP | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Railway, MCP, n8n | Supabase service role key |
| `OPENAI_API_KEY` | Railway | Embeddings (text-embedding-3-small) |
| `ANTHROPIC_API_KEY` | Railway | Claude models |
| `MOONSHOT_API_KEY` | Railway | Kimi long-doc model (optional) |
| `GITHUB_WEBHOOK_SECRET` | Railway | Webhook signature verification |

### What's Live vs. What Needs Activation

- **Live now**: Schema, MCP server, brain seeder, config
- **Needs Railway deploy**: Cron, webhook, Juniper cycles
- **Needs n8n setup**: Gmail ingest workflow
- **Needs Obsidian**: Vault structure, Graphify indexing
- **Future**: Rose persona activation, Juno research sprints, HOJ scheduling

### Key Design Decisions

1. **Hybrid search (BM25 + vector + RRF)** — catches both semantic and keyword matches
2. **Juniper-Junior loop** — adversarial QA prevents autonomous errors
3. **HITL with 48hr escalation** — nothing rots in the queue
4. **TTL on intel** — competitive intelligence auto-expires (30 days default)
5. **Model routing** — Gemma for free classification, Kimi for volume, Sonnet for work, Opus for strategy
6. **Append-only** — no deletes, ever. Contradictions flagged, not resolved.
