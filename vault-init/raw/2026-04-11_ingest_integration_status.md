# Ingest Integration Status — April 11, 2026
**Date:** April 11, 2026
**Source:** n8n_workflow_build_session
**Agent:** rose
**Entry Type:** observation
**Tags:** n8n, ingest, notion, google_drive, onedrive, supabase, infra, workflow, flag

---

## WORKFLOWS CREATED (not yet active)

Three n8n workflows built to feed the Second Brain from outside sources:

| Workflow | URL | Purpose |
|----------|-----|---------|
| Notion → Brain Sync | bkalan169.app.n8n.cloud/workflow/tjLeUOXRFr0FmK0F | Pull Notion pages, embed, write to `thoughts` |
| Google Drive → Brain Sync | bkalan169.app.n8n.cloud/workflow/GxILaplyxl0Fjc2r | Watch Drive folder, ingest docs |
| OneDrive → Brain Sync | bkalan169.app.n8n.cloud/workflow/9nNUqryfL0heWbl7 | Watch OneDrive folder, ingest docs |

Combined with the existing Gmail → Brain workflow, this gives the brain four external ingest lanes:
1. Gmail (email)
2. Notion (structured pages)
3. Google Drive (docs)
4. OneDrive (docs)

Plus the internal lanes: GitHub webhook (vault pushes) and cron (agent-generated thoughts).

---

## ACTIVATION — WHAT'S BLOCKING

Each workflow needs env vars set in n8n (Settings → Variables) before toggling Active:

- `NOTION_API_KEY` — from notion.so/my-integrations
- `GOOGLE_ACCESS_TOKEN` — Google Cloud OAuth app
- `MICROSOFT_ACCESS_TOKEN` — Azure OAuth app
- `SUPABASE_SERVICE_KEY` — same key already used by Gmail workflow

All four workflows target the brain Supabase project: `ubdhpacoqmlxudcvhyuu`.

---

## ⚠️ CRITICAL FLAG — SUPABASE PROJECT DIVERGENCE

**Problem:** An existing n8n workflow named `JRIH — Notion Task Sync` is writing to a **different Supabase project**: `obtoinsjncbqdqgdeddl` — NOT the brain's `ubdhpacoqmlxudcvhyuu`.

**Why this matters:**
- Split-brain problem — notion task data is landing in a project the brain can't see
- Hybrid search won't find it, Juniper can't reason about it, Junior can't gate it
- The more this runs, the more out-of-sync the two projects become
- Every HITL item built from Notion tasks will be invisible to the brain

**Second finding:** The existing Notion Task Sync workflow is missing the `Authorization` header on its Notion API requests — meaning the Notion credential configured in n8n may not actually be wired to that workflow either. Worth verifying before copying the credential reference into the new Brain Sync workflows.

**Required decision (HITL candidate):**
Option A — Migrate `obtoinsjncbqdqgdeddl` data to brain project, retire the old project.
Option B — Keep both projects, build a bridge sync from `obtoinsjncbqdqgdeddl` → `ubdhpacoqmlxudcvhyuu`.
Option C — Update the Notion Task Sync workflow to point at the brain project directly, accept data loss on the old project.

**Recommended:** Option A, but only after confirming what else reads from `obtoinsjncbqdqgdeddl`. If anything in production depends on it, Option B is safer.

---

## ACTION ITEMS

- [ ] Set n8n env vars: `NOTION_API_KEY`, `GOOGLE_ACCESS_TOKEN`, `MICROSOFT_ACCESS_TOKEN`, `SUPABASE_SERVICE_KEY`
- [ ] Toggle Active on: Notion → Brain, Google Drive → Brain, OneDrive → Brain
- [ ] **Decide on `obtoinsjncbqdqgdeddl` project fate (HITL)**
- [ ] Audit the old `JRIH — Notion Task Sync` workflow for missing Authorization header
- [ ] Document: which tools or dashboards currently read from `obtoinsjncbqdqgdeddl`
- [ ] Once resolved, confirm brain receives Notion page embeddings via brain_stats()

---

*Ingested: 2026-04-11_ingest_integration_status.md | Source: infra | vault/raw/ | April 11, 2026*
