# JRIH Second Brain — Task Tracker v2

## Completed

- [x] Supabase schema: thoughts, hitl_queue, digests, metrics
- [x] Supabase schema: juniper_audit, junior_patterns, graph_relationships
- [x] Hybrid search function (BM25 + vector + RRF)
- [x] Agent config: model routing, Supabase client, embeddings
- [x] LangGraph state machine: perceive → reason → junior_gate → execute → log
- [x] Juniper orchestrator: division rotation, cycle management
- [x] Junior adversarial QA: pattern learning, rule evolution, gating
- [x] Specialized agents: Juno, HOJ, Advisor, Junior Learning, HITL Review
- [x] HITL review agent: 48hr escalation, digest summaries
- [x] Cron scheduler: APScheduler on Railway
- [x] MCP server: 5 tools (search, store, hitl, stats, recent)
- [x] Brain seeder v2: 16 foundational thoughts
- [x] GitHub webhook ingest: push → parse → embed → Supabase
- [x] n8n Gmail workflow: Gmail → classify → Supabase
- [x] Vault-init: CLAUDE.md, AGENTS.md, rose_onboarding.md
- [x] Graphify bridge script
- [x] Railway deployment config
- [x] Claude Desktop MCP config template
- [x] HANDOFF.md and WAKEUP.md
- [x] Push to all repos on claude/seed-jrih-brain-v2-22JJP

## Next Up (Post-Seed)

- [ ] Deploy agents to Railway (set env vars)
- [ ] Run brain_seed_v2.py against live Supabase
- [ ] Run schema.sql + schema_juniper.sql in Supabase SQL Editor
- [ ] Configure MCP in Claude Desktop
- [ ] Set up n8n Gmail workflow with OAuth
- [ ] Configure GitHub webhook on vault repo
- [ ] First Juniper cycle test (single division)
- [ ] Rose persona activation in Claude Desktop
- [ ] Graphify initial vault index
- [ ] HITL dashboard in LifeOS (Notion or custom)

## Backlog

- [ ] Juno research sprint implementation (multi-source synthesis)
- [ ] Brand swarm (Kimi workers for multi-channel content)
- [ ] Morning brief email (auto-generated, sent to Alan)
- [ ] Notion sync (LifeOS dashboard bidirectional)
- [ ] Junior self-improvement cycle (weekly pattern review)
- [ ] Full-text search UI in AxiomOS
- [ ] Agent cost tracking dashboard
- [ ] Vault backup automation (S3 or R2)
- [ ] Open Notebook integration (self-hosted, no Google)
