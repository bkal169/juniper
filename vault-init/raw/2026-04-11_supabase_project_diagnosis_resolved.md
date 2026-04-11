# Supabase Project Diagnosis — RESOLVED
**Date:** April 11, 2026
**Source:** rose_juniper_diagnostic_session
**Agent:** rose
**Entry Type:** decision
**Tags:** supabase, infra, architecture, brain, command_center, resolved, jrih

---

## CONTEXT

This file resolves the flag raised earlier today in `2026-04-11_ingest_integration_status.md`. That earlier drop is preserved (append-only rule) — this is the answer to the question it asked.

## THE QUESTION

"Which Supabase project is the canonical JRIH Second Brain — `ubdhpacoqmlxudcvhyuu` or `obtoinsjncbqdqgdeddl`?"

## THE DIAGNOSIS

Alan ran schema inspection against both projects. Results:

### `ubdhpacoqmlxudcvhyuu` — AxiomOS / JRi Product Database
- Tables: `deals`, `tenants`, `beta_requests`, `billing`, financial models
- Purpose: Product backend for AxiomOS (JRi division)
- **NOT the brain.** This is a product database for a SaaS app.

### `obtoinsjncbqdqgdeddl` — JRIH Command Center
- Tables: `divisions`, `goals`, `tasks`, `leads`, HOJ programs, CRM, income, content
- Purpose: The actual JRIH business operating system
- **This IS the brain.** The command center and the brain are one thing.

## THE RESOLUTION

The command center IS the brain. They share one Supabase project: `obtoinsjncbqdqgdeddl`.

The brain tables (`thoughts`, `hitl_queue`, `juniper_audit`, `junior_patterns`, `graph_relationships`, `morning_briefs`, `digests`, `jrih_metrics`) do not yet exist in that project. They need to be created there, not in the AxiomOS product database.

## WHY ONE PROJECT, NOT TWO

- Single source of truth — command center queries brain tables directly
- No sync lag — the dashboard sees real-time agent writes
- One set of ops — one backup schedule, one service key, one access control
- Lower cost — one Supabase plan instead of two
- No split-brain risk between operator view and agent writes

The command center dashboard is the human view of the same data agents write. They should live together.

## REMEDIATION ACTIONS

### Brain Infrastructure (code side) — `bkal169/juniper`
- [x] Update `agents/config.py` SUPABASE_URL default
- [x] Update `mcp/server.ts` SUPABASE_URL default
- [x] Update `mcp/claude-desktop-config.json`
- [x] Update `agents/n8n_gmail_workflow.json` URL
- [x] Update `supabase/schema.sql` header comment
- [x] Update `supabase/schema_juniper.sql` header comment
- [x] Update `railway.toml` env var comment
- [x] Update `agents/brain_seed_v2.py` infrastructure seed

### Reference Material — `bkal169/claude.md`
- [x] Update `CLAUDE.md` INFRASTRUCTURE section

### Supabase Migration (Alan-side, Supabase dashboard)
- [ ] Run `schema.sql` in `obtoinsjncbqdqgdeddl` SQL editor
- [ ] Run `schema_juniper.sql` in `obtoinsjncbqdqgdeddl` SQL editor
- [ ] Migrate existing 19 `thoughts` rows from `ubdhpacoqmlxudcvhyuu` → `obtoinsjncbqdqgdeddl`
- [ ] Pull service role key from Supabase dashboard → Project Settings → API
- [ ] Set `SUPABASE_SERVICE_KEY` in Railway env vars
- [ ] Set `SUPABASE_SERVICE_KEY` in n8n Variables

### Workflow Migration (n8n)
- [ ] Update Gmail → Brain workflow (swap URL to `obtoinsjncbqdqgdeddl`)
- [ ] Update Notion → Brain Sync workflow
- [ ] Update Google Drive → Brain Sync workflow
- [ ] Update OneDrive → Brain Sync workflow

### Post-migration Verification
- [ ] Confirm `brain_stats()` returns non-zero thought count
- [ ] Confirm hybrid search still works against migrated data
- [ ] Confirm command center dashboard can read `thoughts` table directly

## WHAT TO DO WITH `ubdhpacoqmlxudcvhyuu`

Leave it alone. It's the AxiomOS product database and stays exactly where it is, serving the product. This is a naming/discovery issue, not a "wrong data in wrong place" issue for the AxiomOS tables. The only thing that needed to move was the brain, and the brain was never meant to live there in the first place — it was placed there by my bad assumption, not by any intentional architecture decision.

## LESSONS

1. **Project IDs in drop files can mislead.** The seed drop file I pulled this from listed `ubdhpacoqmlxudcvhyuu` as "the Supabase project" without saying which project that actually was. I should have asked before hardcoding.
2. **The command center IS the brain.** Not a view of it, not a wrapper, not a separate service — the same project. Dashboard reads the agent writes.
3. **Append-only works.** The earlier flag drop stayed intact; this resolution drop is its counterpart. Full audit trail preserved.

---

*Ingested: 2026-04-11_supabase_project_diagnosis_resolved.md | Source: infra | vault/raw/ | April 11, 2026*
