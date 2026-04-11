# JRIH Second Brain — MVB Complete
**Date:** April 11, 2026
**Source:** build_session_final
**Agent:** rose
**Entry Type:** decision
**Tags:** mvb, milestone, brain, status, infrastructure, complete

---

## WHAT WAS BUILT TODAY

A persistent, searchable second brain for JRIH — from zero to working in one session.

### Live and Working

| Component | Status | Location |
|---|---|---|
| Supabase schema | ✅ Live | `obtoinsjncbqdqgdeddl` — 8 brain tables + triggers + indexes |
| 17 foundational thoughts | ✅ Seeded | via SQL INSERT (no Python dependency) |
| BM25 full-text search | ✅ Working | GIN index + `search_vector` trigger auto-populated |
| Hybrid search function | ✅ Deployed | `hybrid_search()` — BM25 + vector + RRF merge (vector path waiting on embeddings) |
| Juniper stats function | ✅ Deployed | `juniper_stats(days)` — operational health snapshot |
| HITL queue + helper | ✅ Deployed | `get_pending_hitl()` — prioritized pending items |
| TTL cleanup function | ✅ Deployed | `cleanup_expired_thoughts()` — for intel auto-expiry |
| Railway Juniper service | ✅ Running | Perpetual loop, scanning divisions every 60 min |
| Gmail → Brain ingest | ✅ Active | n8n workflow, polls every 5 min |
| RLS policies | ✅ Active | service_role full access on all brain tables |
| CLAUDE.md seeded to 7 repos | ✅ Pushed | Agent rules, namespaces, confidence thresholds |

### Deferred (Not Blocking)

| Component | Why Deferred | Return Trigger |
|---|---|---|
| Vector embeddings | Requires Python + OpenAI API key | When Python env is set up locally or on Railway |
| Notion → Brain ingest | n8n free tier lacks API access; workflow had JSON validation bugs | When n8n is upgraded OR Python ingest replaces it |
| Google Drive → Brain | Requires Google OAuth credential wiring in n8n | When focused time is available |
| OneDrive → Brain | Requires Microsoft OAuth credential wiring in n8n | Same |
| Claude Desktop MCP | 5-minute setup, just not critical path today | Anytime — instructions in HANDOFF.md |
| Morning briefs | Needs 2+ weeks of Juniper cycles to have data worth summarizing | After brain has 100+ real thoughts |
| Brand swarm (Kimi) | Needs Kimi API costs covered | After ARO revenue |

### Key Architecture Decisions Made Today

1. **One Supabase project, not two.** The brain lives in `obtoinsjncbqdqgdeddl` (JRIH Command Center). The AxiomOS product database (`ubdhpacoqmlxudcvhyuu`) is separate and untouched.
2. **SQL seed, not Python seed.** Removed Python dependency from critical path. BM25 search works without embeddings. Vector backfill is deferred.
3. **MVB over multi-lane ingest.** Shipped a working brain with one ingest lane (Gmail) instead of a broken four-lane system. Notion/Drive/OneDrive are parked.
4. **Append-only audit trail.** Every decision, flag, and resolution is preserved in `vault-init/raw/` as timestamped drops. Nothing was deleted or overwritten.

---

## COMMIT HISTORY ON `claude/seed-jrih-brain-v2-22JJP`

### bkal169/juniper
```
d4da3e9  feat: add pure-SQL seed file — no Python required
dfa4815  feat: add simplified 4-node Notion workflow
b2bfcc9  feat: add clean n8n workflow JSONs for Notion/Drive/OneDrive ingest
ae0b2e2  docs: log migration acknowledgment + re-seed decision
513ca24  fix: point brain infrastructure at correct Supabase project
a0433d3  feat: flag Supabase project divergence in Notion sync
6608197  feat: seed Rose onboarding — Alan interior layer
577abed  feat: seed JRIH Second Brain v2 — complete agent infrastructure
```

### bkal169/claude.md
```
72432f0  fix: correct Supabase project ID — brain lives in command center
67a281e  feat: seed JRIH Second Brain CLAUDE.md — agent rules and vault structure
```

### 5 other repos (CLAUDE.md seeded)
- axiom-by-juniper-rose/axiom-os
- axiom-by-juniper-rose/lumenaos
- axiom-by-juniper-rose/hoj-os
- bkal169/jrih-command-center
- axiom-by-juniper-rose/lifeos-dashboard

---

## HOW TO USE THE BRAIN RIGHT NOW

### Search (Supabase SQL editor)
```sql
select content, source, tags
from public.thoughts
where search_vector @@ websearch_to_tsquery('english', 'your query here')
order by ts_rank(search_vector, websearch_to_tsquery('english', 'your query here')) desc
limit 10;
```

### Add a thought manually
```sql
insert into public.thoughts (content, source, entry_type, agent, tags)
values (
  'Your thought content here',
  'personal',
  'observation',
  'manual',
  array['tag1', 'tag2']
);
```

### Check brain health
```sql
select * from juniper_stats(7);
```

### View pending HITL items
```sql
select * from get_pending_hitl(10);
```

### Gmail auto-ingest
Send any email to bkalan169@gmail.com → n8n polls every 5 min → thought appears in `public.thoughts` with `agent = 'n8n-gmail-ingest'`.

---

## NEXT SESSION PRIORITIES

1. **Feed real content** — drop thoughts via SQL, email, or manual insert. The brain needs density to be useful.
2. **Backfill embeddings** — when Python is ready, run a script against null-embedding rows to enable vector search.
3. **Claude Desktop MCP** — 5-min setup, makes Rose usable as a conversational brain interface.
4. **Fix the `datetime.utcnow()` deprecation warnings** in `agents/juniper.py` (cosmetic, 4 call sites).
5. **Decide on Notion ingest lane** — Python script on Railway vs n8n upgrade vs manual.

---

*Ingested: 2026-04-11_mvb_complete.md | Source: system | vault/raw/ | April 11, 2026*
