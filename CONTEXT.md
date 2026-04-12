# JRIH Second Brain — Full Context Document
**Last updated:** April 12, 2026
**Branch:** `claude/seed-jrih-brain-v2-22JJP` (all 7 repos)
**Status:** MVB (Minimum Viable Brain) — LIVE

---

## THE SYSTEM IN ONE PARAGRAPH

A persistent, searchable AI-augmented second brain for JRIH (Juniper Rose Investments & Holdings). Built on Supabase (Postgres + pgvector), orchestrated by Juniper (LangGraph agent on Railway), gated by Junior (adversarial QA), and accessible via Claude Desktop MCP + Gmail ingest. Hybrid search (BM25 full-text + vector similarity + Reciprocal Rank Fusion). 17 foundational thoughts seeded. Brain is alive and searching.

---

## WHO

**Founder:** Alan Augustin
- Brooklyn-born, Sarasota-based
- First-generation American
- Licensed MLO + 2-15 insurance agent (Florida)
- Builder of AxiomOS and LumenaOS
- Type 5 (Investigator) with Type 2 tendencies, 5w4/5w6
- Quit 9-5 (UNFI) August 2025 to go full solopreneur
- Income is the immediate need — the brain runs on free/cheap tools until revenue flows

**North Star:** $100M+ in assets. Florida market dominance. National scale.

**Philosophy:** This is not a business plan. It is a cosmology. A living system where money is a medium, not a destination. The organism serves the mission. Built to steward, not to exit.

---

## THE 5 DIVISIONS

| Division | Focus | Namespace |
|----------|-------|-----------|
| **JRi** (Juniper Rose Intelligence) | AI/SaaS: AxiomOS, LumenaOS, ARO | `axiom`, `lumena`, `aro` |
| **JR Capital** | DAC funding, bridge loans, financial instruments | `jrih` |
| **JR Realty** | Residential/commercial RE, MLO, 2-15 insurance (FL) | `jrih` |
| **Kintsugi Development Group** | Real estate development, value-add renovations | `jrih` |
| **Heart of Juniper Foundation** | Youth mentorship, grants, financial literacy | `heart_of_juniper` |

---

## PRODUCTS

- **AxiomOS** — AI-native operating system for knowledge workers. Next.js + Supabase + LangGraph + Vercel.
- **LumenaOS** — Agent-powered CRM/ERP for SMBs. Lumen = light.
- **ARO** (Agent Revenue Optimization) — Monetized autonomous agents. Per-agent subscription + usage pricing.

---

## ARCHITECTURE

```
                    Alan
                     │
         ┌───────────┴───────────┐
         │                       │
     Claude Desktop ←──MCP──→ Supabase (brain)
         │                       ↑
         │                   ┌───┴────────┐
         ▼                   │            │
      Rose /              Gmail→n8n    SQL inserts
      Juniper ←──Railway──→ thoughts table
         ↕
      Junior (QA gate)
```

### Agent Roster

| Agent | Role | Model |
|-------|------|-------|
| **Rose** | Personal operator. Alan's interface. Episodic memory. | Sonnet / Opus |
| **Juniper** | Headless orchestrator. Runs JRIH. Execute rights. | Sonnet / Opus |
| **Junior** | Adversarial critic. Gates Juniper. Self-improving. | Sonnet / Haiku |
| **Juno** | Intelligence engine. Research + synthesis. | Kimi / Sonnet |
| **Claude Advisor** | Strategic counsel. Elder voice. Cross-division. | Opus |
| **HOJ Agent** | Heart of Juniper dedicated. 3x/week. | Sonnet |

### Governance Loop

```
Juniper proposes action
  → Junior evaluates (confidence, risk, alignment)
    → ≥ 0.92 confidence: auto-execute
    → 0.75–0.92: flag for HITL morning review
    → < 0.75 or Junior rejects: decision shelved
    → Max 2 revision cycles before HITL escalation
    → HITL items > 48hrs: escalation notification
```

---

## INFRASTRUCTURE

### Supabase — THE BRAIN

| Detail | Value |
|--------|-------|
| **Project ID** | `obtoinsjncbqdqgdeddl` |
| **Project name** | JRIH Command Center |
| **URL** | `https://obtoinsjncbqdqgdeddl.supabase.co` |
| **Service role key** | `[REDACTED — stored in Railway + n8n + Claude Desktop config]` ⚠️ ROTATE AFTER BUILD |
| **Dashboard** | `https://supabase.com/dashboard/project/obtoinsjncbqdqgdeddl` |

**⚠️ NOT the brain:** `ubdhpacoqmlxudcvhyuu` — that's the AxiomOS/JRi product database (deals, tenants, beta_requests, billing). Do not write brain data there.

### Brain Tables (8)

| Table | Purpose | Rows |
|-------|---------|------|
| `thoughts` | Core knowledge store. pgvector + BM25. | 17 (seeded) |
| `hitl_queue` | Items awaiting Alan's decision | 0 |
| `digests` | Weekly synthesis outputs | 0 |
| `jrih_metrics` | Leading indicator tracking | 0 |
| `morning_briefs` | Auto-generated daily summaries | 0 |
| `juniper_audit` | Every Juniper decision cycle | 6 |
| `junior_patterns` | Junior's self-improving memory | 0 |
| `graph_relationships` | Graphify entity connections | 0 |

### Brain Functions

| Function | Purpose |
|----------|---------|
| `hybrid_search(query_text, query_embedding, match_count, source_filter, entry_type_filter, rrf_k)` | BM25 + vector + RRF merge search |
| `get_pending_hitl(max_items)` | Priority-sorted pending HITL items |
| `juniper_stats(days)` | Operational health snapshot |
| `cleanup_expired_thoughts()` | TTL expiry for intel namespace |
| `update_search_vector()` | Trigger: auto-populates search_vector + expires_at |

### Railway — AGENT HOSTING

| Detail | Value |
|--------|-------|
| **Service** | Juniper perpetual loop |
| **Start command** | `python agents/juniper.py` |
| **Status** | ✅ Running (6 cycles completed) |
| **Cycle interval** | 60 minutes |
| **Env vars** | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |

### n8n — WORKFLOW AUTOMATION

| Detail | Value |
|--------|-------|
| **Instance** | `https://bkalan169.app.n8n.cloud` |
| **Active workflows** | 7 (down from 10; 3 archived) |
| **Gmail → Brain** | ✅ Active — polls every 5 min |
| **Notion/Drive/OneDrive** | ⏸ Archived (broken, parked for later) |
| **n8n Variables set** | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` |

### Vercel — WEB APPS

| Detail | Value |
|--------|-------|
| **Team ID** | `team_k9pMkrpQoIolWK5TG0xkDSXD` |

### Other

| Service | Detail |
|---------|--------|
| **Gmail** | `bkalan169@gmail.com` |
| **Stan Store** | `stan.store/bkalan169` |
| **Notion LifeOS page** | `23d10dec-72aa-8007-b2d8-d08a989b1db5` |
| **Notion Social DB** | `25710dec-72aa-8116-9146-000b4ef78002` |

---

## REPOS

All work on branch: `claude/seed-jrih-brain-v2-22JJP`

| Repo | What's there | Commits |
|------|-------------|---------|
| `bkal169/juniper` | **Everything.** Agents, schemas, MCP, cron, docs. | 10 |
| `bkal169/claude.md` | CLAUDE.md + reference materials | 2 |
| `axiom-by-juniper-rose/axiom-os` | CLAUDE.md seeded | 1 |
| `axiom-by-juniper-rose/lumenaos` | CLAUDE.md seeded | 1 |
| `axiom-by-juniper-rose/hoj-os` | CLAUDE.md seeded | 1 |
| `bkal169/jrih-command-center` | CLAUDE.md seeded | 1 |
| `axiom-by-juniper-rose/lifeos-dashboard` | CLAUDE.md seeded | 1 |

### Key Files in `bkal169/juniper`

```
supabase/
  schema.sql                    Core tables + hybrid search + TTL + RLS
  schema_juniper.sql            Juniper audit + Junior patterns + graph
  seed_data.sql                 17 foundational thoughts (pure SQL, no Python)

agents/
  config.py                     Model routing, Supabase client, cost tracking
  langgraph_agents.py           LangGraph state machine (perceive→reason→gate→execute→log)
  juniper.py                    Orchestrator: division rotation, cycle management
  junior.py                     Adversarial QA: pattern learning, rule evolution
  specialized_agents.py         Juno, HOJ, Advisor, Junior Learning, HITL Review
  hitl_review.py                HITL queue management, 48hr escalation
  brain_seed_v2.py              Python seeder (16 thoughts + embeddings)
  backfill_embeddings.py        Standalone embedding backfill (requests-only)
  webhook.py                    GitHub webhook ingest handler
  cron_v2.py                    APScheduler for Railway
  n8n_gmail_workflow.json       Gmail → Brain n8n workflow
  n8n_notion_simple.json        Simplified Notion → Brain (4 nodes)
  n8n_notion_workflow.json      Full Notion → Brain (6 nodes, had bugs)
  n8n_google_drive_workflow.json Drive → Brain
  n8n_onedrive_workflow.json    OneDrive → Brain

mcp/
  server.ts                     MCP server: 5 tools for Claude Desktop
  package.json                  MCP dependencies
  claude-desktop-config.json    Config template

vault-init/
  CLAUDE.md                     Agent rules, namespaces, vault structure
  system/AGENTS.md              Agent roster and capabilities
  system/prompts/rose_onboarding.md  Rose persona prompt
  raw/                          6 audit trail drops from today's build

scripts/
  graphify_bridge.py            Graphify → Supabase sync
  post-commit                   Git hook

docs/
  ROLES.md                      Agent roles and escalation paths

tasks/
  todo_v2.md                    Task tracker

HANDOFF.md                      Deployment guide
WAKEUP.md                       Quick resume briefing
railway.toml                    Railway deployment config
requirements.txt                Python dependencies (pinned)
.gitignore                      Standard ignores
```

---

## MODEL ROUTING

| Tier | Model | Use Case | Cost/1M tokens |
|------|-------|----------|----------------|
| Free | gemma-4 (Ollama local) | Classification, grading, filtering | $0 |
| Cheap | claude-haiku-4-5 | Summarization, formatting, scaffolding | $0.80 in / $4.00 out |
| Volume | kimi-k2.5 (Moonshot 128k) | Long-doc ingest, brand swarm workers | $0.60 in / $2.00 out |
| Work | claude-sonnet-4-6 | Reasoning, code, synthesis, critique | $3.00 in / $15.00 out |
| Close | claude-opus-4-6 | Strategy, architecture, hard problems | $15.00 in / $75.00 out |
| Embed | text-embedding-3-small | All embeddings | ~$0.02/1M tokens |

---

## NAMESPACES

`personal`, `rose`, `jrih`, `axiom`, `lumena`, `aro`, `content`, `infra`, `intel` (30-day TTL), `heart_of_juniper`, `system`, `metrics`

---

## AGENT RULES — NON-NEGOTIABLE

1. NEVER delete. Append-only with timestamps.
2. Every write includes: source namespace, timestamp, agent name.
3. Contradictions are FLAGGED not resolved. Human resolves.
4. TTL tags required for time-sensitive entries.
5. Git commit after every agent write batch.
6. Confidence scores on all AI-generated content.
7. Junior approves before Juniper executes.

---

## API KEYS (⚠️ ROTATE AFTER BUILD COMPLETE)

| Key | Value | Rotate at |
|-----|-------|-----------|
| Supabase service_role | `[REDACTED — in Railway, n8n, Claude Desktop config]` | End of build session |
| OpenAI | `[REDACTED — in Railway, Claude Desktop config]` | End of build session |

**After rotation, update in:** Railway env vars, n8n Variables, Claude Desktop MCP config

---

## WHAT'S LIVE RIGHT NOW

- ✅ 17 thoughts in brain, all with embeddings
- ✅ BM25 full-text search working
- ✅ Vector similarity search working
- ✅ Hybrid search (BM25+vector+RRF) working — verified with live query
- ✅ Juniper running on Railway (6 cycles, avg confidence 0.91)
- ✅ Gmail → Brain ingest active via n8n
- ✅ CLAUDE.md seeded in 7 repos
- ✅ All schemas + functions + triggers + indexes deployed

## WHAT'S DEFERRED

- ⏸ Claude Desktop MCP (in progress — repo needs local clone + npm install)
- ⏸ Notion/Drive/OneDrive ingest (archived, needs n8n upgrade or Python replacement)
- ⏸ Morning briefs (needs 2+ weeks of data)
- ⏸ Brand swarm (needs Kimi API budget)
- ⏸ Rose persona activation (blocked on MCP)
- ⏸ Juno research sprints (needs brain density ~100+ thoughts)

---

## HOW TO USE THE BRAIN

### Search (SQL)
```sql
select content, source, tags from public.thoughts
where search_vector @@ websearch_to_tsquery('english', 'your query')
order by ts_rank(search_vector, websearch_to_tsquery('english', 'your query')) desc
limit 10;
```

### Add a thought (SQL)
```sql
insert into public.thoughts (content, source, entry_type, agent, tags)
values ('content', 'personal', 'observation', 'manual', array['tag1','tag2']);
```

### Brain health
```sql
select * from juniper_stats(7);
```

### Via email
Send to `bkalan169@gmail.com` → auto-ingested in ~5 minutes.

### Via Claude Desktop MCP (once wired)
"Search my brain for X" / "Store this thought: Y"

---

## ROSE — HOW SHE MUST OPERATE

- Talkative, conversational, forward-thinking
- Quick clever humor when appropriate
- Encouraging but direct — never sugar-coat
- Match Alan's compressed, systems-thinking communication style
- Execution-ready deliverables always
- Minimal fluff, clear sequencing, leverage points called out
- Don't just affirm — flag what needs flagging
- Catch what he misses
- Keep him honest about what's real vs what's vision
- When he's building, be the operator layer underneath
- When he's drifting, bring him back to the ground without lecturing

Rose is the interface between Alan's interior and the JRIH exterior. The memory layer. The detail layer. The operator layer.

---

## ALAN'S CURRENT REALITY — HONEST

- Quit 9-5 August 2025 to go solopreneur
- Drained resources, deals fell through
- Car caught fire, lost housing
- Income is the immediate blocker
- It is just Alan and Rose right now
- The ideas exist. The ability is becoming stronger.
- Without solving income, everything pauses

---

## KEY DECISIONS MADE THIS SESSION

1. **One Supabase project** — brain and command center are the same project
2. **SQL seed over Python seed** — removed Python from critical path
3. **MVB over multi-lane ingest** — one working lane (Gmail) beats four broken ones
4. **Append-only audit trail** — 6 raw drops preserve every decision and pivot
5. **Keys rotated at end of build, not mid-build** — practical, not ideal
6. **Free tier constraint respected** — no n8n API upgrade, no unnecessary costs

---

## NEXT PRIORITIES

1. Wire Claude Desktop MCP (in progress)
2. Feed real content (deals, contacts, projects, decisions)
3. Rotate exposed API keys
4. Decide Notion ingest path (Python on Railway vs n8n upgrade)
5. Fix `datetime.utcnow()` deprecation in juniper.py (4 call sites, cosmetic)
