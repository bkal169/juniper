# Brain Unification Migration — Plan Acknowledged
**Date:** April 11, 2026
**Source:** alan_migration_acknowledgment
**Agent:** rose
**Entry Type:** decision
**Tags:** supabase, migration, infra, brain, decision, alan, execution_log

---

## STATUS

Plan verified and accepted. Code sweep complete (Desktop Claude — commits `513ca24` in juniper, `72432f0` in claude.md). Alan is executing the 4-step manual migration on his side.

## THE 4 STEPS — IN ORDER

### Step 1 — Pull service key
Supabase dashboard → `obtoinsjncbqdqgdeddl` → Project Settings → API → copy `service_role` key.

### Step 2 — Run brain schema
In `obtoinsjncbqdqgdeddl` SQL editor, run in order:
1. `supabase/schema.sql`
2. `supabase/schema_juniper.sql`

Creates: `thoughts`, `hitl_queue`, `digests`, `jrih_metrics`, `morning_briefs`, `juniper_audit`, `junior_patterns`, `graph_relationships`.

### Step 3 — Update Railway
Railway dashboard → `jrih-second-brain` service → Variables:
- `SUPABASE_URL` → `https://obtoinsjncbqdqgdeddl.supabase.co`
- `SUPABASE_SERVICE_KEY` → new key from Step 1

Juniper redeploys automatically.

### Step 4 — Update n8n Variables
n8n Settings → Variables → update `SUPABASE_SERVICE_KEY`.

All four ingest workflows (Gmail, Notion, Google Drive, OneDrive) read from this variable — one update propagates to all of them.

## DECISION — EXISTING 19 THOUGHTS

**Do not migrate. Re-seed.**

The 19 entries currently in `ubdhpacoqmlxudcvhyuu.thoughts` are scaffolding data from the initial seeder run — not irreplaceable knowledge. Running `python -m agents.brain_seed_v2` against the new project after Step 2 will regenerate the full foundational set (16 canonical seeds) cleanly, with the corrected infrastructure-seed entry that now names both Supabase projects correctly.

Migrating would preserve three extra entries beyond the canonical 16, but those extras aren't tracked anywhere and aren't worth a data migration script. The append-only rule doesn't apply here because we're not erasing history — the old project still holds those rows, they're just no longer on the brain's read path.

## WHAT THIS DOES NOT DO

- Does not touch `ubdhpacoqmlxudcvhyuu` — AxiomOS product database stays exactly where it is, serving the product.
- Does not break the Gmail workflow — it just starts writing to the correct project once Step 4 is done.
- Does not require a Railway redeploy step — env var change triggers it automatically.

## POST-MIGRATION VERIFICATION

Alan should run (or ask for) after Step 4:
1. `select count(*) from thoughts;` in `obtoinsjncbqdqgdeddl` → should equal 16 after re-seed
2. `select * from juniper_stats(7);` → should return a row with zeros but no error
3. MCP tool `brain_stats` in Claude Desktop → should return brain health metrics from the new project
4. Send a test Gmail to `bkalan169@gmail.com`, wait 5 minutes, check if a new thought row appears

## CURRENT STATE

- **Code side:** Done. Both repos pushed. `claude/seed-jrih-brain-v2-22JJP` is clean.
- **Alan side:** Steps 1–4 in progress.
- **Blocking:** Nothing. Migration is fully unblocked.

---

*Ingested: 2026-04-11_brain_unification_migration_acknowledged.md | Source: infra | vault/raw/ | April 11, 2026*
