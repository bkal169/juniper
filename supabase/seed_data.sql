-- JRIH Second Brain — Seed Data (SQL-only, no Python required)
-- Target: Supabase project obtoinsjncbqdqgdeddl (JRIH Command Center = Brain)
-- Run this AFTER schema.sql and schema_juniper.sql
--
-- WHAT THIS DOES:
--   Inserts 17 foundational thoughts directly into public.thoughts.
--   The search_vector column is auto-populated by the existing trigger,
--   so BM25 full-text search will work immediately.
--
-- WHAT THIS DOES NOT DO:
--   Does not generate vector embeddings. The embedding column stays NULL
--   for these rows. That means vector similarity search won't find them,
--   but BM25 keyword search will. That is enough for MVB.
--
-- BACKFILL LATER:
--   When Python is available, run `python -m agents.backfill_embeddings`
--   (to be written) to fill in the embedding column for any NULL rows.
--   Until then, brain_search will fall back to BM25 and return results.

-- ═══════════════════════════════════════════════════════════
-- SAFETY: Make this script re-runnable
-- Delete any previous seeded rows from this exact seeder version
-- so the insert below is idempotent.
-- ═══════════════════════════════════════════════════════════

delete from public.thoughts
where metadata->>'seed_version' = 'v2-sql'
  and agent = 'brain-seeder-v2-sql';

-- ═══════════════════════════════════════════════════════════
-- 17 FOUNDATIONAL THOUGHTS
-- ═══════════════════════════════════════════════════════════

insert into public.thoughts (content, source, entry_type, agent, tags, confidence, metadata)
values

-- 1. JRIH Core
($seed$JRIH (Juniper Rose Investments & Holdings) is a multi-division holding company founded by Alan Augustin. Brooklyn-born, Sarasota-based. North star: $100M+ in assets. Five operating divisions: JRi (AI/SaaS), JR Capital (DAC funding, financial services), JR Realty (real estate, MLO, 2-15 insurance), Kintsugi Development Group (real estate development), Heart of Juniper Foundation (community philanthropy).$seed$,
 'jrih', 'reference', 'brain-seeder-v2-sql',
 array['founder','structure','alan','divisions'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 1}'::jsonb),

-- 2. Alan bio
($seed$Alan Augustin is the founder and principal of JRIH. Brooklyn-born, Sarasota-based. Background in real estate, finance, AI/SaaS. Licensed MLO and 2-15 insurance agent in Florida. Builder of AxiomOS and LumenaOS. Operator of Heart of Juniper Foundation.$seed$,
 'personal', 'reference', 'brain-seeder-v2-sql',
 array['alan','founder','bio'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 2}'::jsonb),

-- 3. JRi division
($seed$JRi (Juniper Rose Intelligence) is the AI/SaaS division of JRIH. Products: AxiomOS (AI-native operating system for knowledge workers), LumenaOS (agent-powered CRM/ERP for SMBs), ARO (Agent Revenue Optimization — monetized autonomous agents). JRi is the technology engine of the holding company.$seed$,
 'axiom', 'reference', 'brain-seeder-v2-sql',
 array['jri','axiom','lumena','aro','saas','ai'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 3}'::jsonb),

-- 4. JR Capital
($seed$JR Capital is the financial services division of JRIH. Focuses on DAC (Diversified Asset Capital) funding, bridge loans, and financial instruments. Works closely with JR Realty for deal financing. Revenue model: origination fees, spread income, advisory.$seed$,
 'jrih', 'reference', 'brain-seeder-v2-sql',
 array['jr_capital','finance','dac','funding'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 4}'::jsonb),

-- 5. JR Realty
($seed$JR Realty is the real estate division of JRIH. Covers residential and commercial transactions, MLO (Mortgage Loan Originator) services, and 2-15 insurance in Florida. Alan is licensed for both. Revenue: commissions, origination, insurance premiums.$seed$,
 'jrih', 'reference', 'brain-seeder-v2-sql',
 array['jr_realty','real_estate','mlo','insurance','florida'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 5}'::jsonb),

-- 6. Kintsugi Development
($seed$Kintsugi Development Group is the real estate development arm of JRIH. Named after the Japanese art of repairing with gold — finding beauty in broken things, adding value through renovation and development. Focus: Florida properties, value-add renovations, ground-up development.$seed$,
 'jrih', 'reference', 'brain-seeder-v2-sql',
 array['kintsugi','development','real_estate','florida'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 6}'::jsonb),

-- 7. Heart of Juniper Foundation
($seed$Heart of Juniper Foundation (HOJ) is the philanthropic arm of JRIH. Community-focused. Sarasota-based. Programs: youth mentorship, community grants, financial literacy workshops. Operates with separate governance but shared infrastructure. Dedicated HOJ agent runs 3x/week.$seed$,
 'heart_of_juniper', 'reference', 'brain-seeder-v2-sql',
 array['hoj','foundation','philanthropy','community'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 7}'::jsonb),

-- 8. AxiomOS product
($seed$AxiomOS is an AI-native operating system for knowledge workers. Built by JRi. Features: agent orchestration, second brain integration, workflow automation, MCP server integration. Target users: founders, operators, professionals who need AI-augmented decision-making. Tech stack: Next.js, Supabase, LangGraph, Vercel.$seed$,
 'axiom', 'reference', 'brain-seeder-v2-sql',
 array['axiom','product','saas','ai_os'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 8}'::jsonb),

-- 9. LumenaOS product
($seed$LumenaOS is an agent-powered CRM/ERP for SMBs. Built by JRi. Features: AI agents handle customer communication, lead routing, invoicing, and reporting. Target: small businesses who can't afford a full ops team. Lumen = light; the system illuminates business operations.$seed$,
 'lumena', 'reference', 'brain-seeder-v2-sql',
 array['lumena','product','crm','erp','smb'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 9}'::jsonb),

-- 10. ARO product
($seed$ARO (Agent Revenue Optimization) is JRi's monetized autonomous agent platform. Agents perform revenue-generating tasks: lead qualification, content creation, market research, competitive intelligence. Revenue model: per-agent subscription, usage-based pricing, enterprise licensing.$seed$,
 'aro', 'reference', 'brain-seeder-v2-sql',
 array['aro','agents','revenue','monetization'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 10}'::jsonb),

-- 11. Agent architecture
($seed$The JRIH Second Brain agent architecture: Rose (personal operator, Alan's interface), Juniper (headless orchestrator, runs JRIH operations, has execute rights), Junior (adversarial critic, gates Juniper decisions, self-improving), Juno (intelligence engine, research + synthesis), Claude Advisor (strategic counsel, elder voice). Supporting agents: Ingest, Wiki, Retrieval, Synthesis, Gatekeeper, Competitive Intel, HOJ Agent.$seed$,
 'system', 'reference', 'brain-seeder-v2-sql',
 array['agents','architecture','rose','juniper','junior','juno'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 11}'::jsonb),

-- 12. Juniper-Junior governance loop
($seed$Juniper-Junior governance loop: Juniper proposes an action -> Junior evaluates (confidence, risk, alignment) -> Junior verdict (approve/reject/revise) -> If approved and confidence >= 0.92, auto-execute. If 0.75-0.92, flag for morning review (HITL). If < 0.75 or Junior rejects, decision shelved. Max 2 revision cycles before escalation to HITL.$seed$,
 'system', 'reference', 'brain-seeder-v2-sql',
 array['governance','juniper','junior','hitl','confidence'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 12}'::jsonb),

-- 13. Model routing
($seed$Model routing strategy: gemma-4 (Ollama local, free) for classification/grading/filtering. Kimi k2.5 (Moonshot 128k) for long-doc ingestion and brand swarm workers. Claude Sonnet 4.6 for synthesis, reasoning, code generation, critique. Claude Opus 4.6 for strategy, architecture, hard bugs. text-embedding-3-small for all embeddings. Principle: best+highest use, no wasted tokens.$seed$,
 'system', 'reference', 'brain-seeder-v2-sql',
 array['models','routing','cost','optimization'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 13}'::jsonb),

-- 14. Infrastructure (CORRECT project IDs)
($seed$JRIH infrastructure: Supabase project obtoinsjncbqdqgdeddl (JRIH Command Center) is the canonical brain — Postgres + pgvector, persistent memory, thoughts table, HITL queue, Juniper audit log. Separate project ubdhpacoqmlxudcvhyuu is the AxiomOS/JRi product backend (deals, tenants, beta_requests, billing) and is NOT the brain. Railway for agent hosting. Vercel for web apps (team: team_k9pMkrpQoIolWK5TG0xkDSXD). Notion for LifeOS dashboard. n8n for workflow automation (bkalan169.app.n8n.cloud). GitHub for version control. Obsidian vault for local knowledge. Graphify for knowledge graph indexing.$seed$,
 'infra', 'reference', 'brain-seeder-v2-sql',
 array['infrastructure','supabase','railway','vercel','notion','n8n'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 14}'::jsonb),

-- 15. Vault structure
($seed$Vault structure follows modified PARA: raw/ (drop zone, agent trigger zone), wiki/ (AI-maintained entity pages), outputs/ (agent deliverables), projects/ (active work), areas/ (ongoing responsibilities), resources/ (reference material), archive/ (inactive), system/ (config). Naming: wiki pages = ENTITY_NAME.md, raw drops = YYYY-MM-DD_topic_source.md, outputs = YYYY-MM-DD_type_title.md.$seed$,
 'system', 'reference', 'brain-seeder-v2-sql',
 array['vault','para','structure','naming'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 15}'::jsonb),

-- 16. Growth trajectory
($seed$JRIH growth trajectory: Now — foundation, capture flowing, search working. 3 months — Juniper operational, JRi division running. 6 months — all 5 divisions namespaced, Rose + Juno live. 12 months — full self-hosted, Open Notebook, no Google dependency. 18 months — Juno as AxiomOS product, brain becomes what we sell.$seed$,
 'jrih', 'decision', 'brain-seeder-v2-sql',
 array['strategy','roadmap','growth','timeline'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 16}'::jsonb),

-- 17. Florida market
($seed$Florida market focus: Sarasota-Bradenton MSA for real estate (JR Realty, Kintsugi). Tampa Bay corridor for expansion. Florida regulatory environment: MLO licensing, 2-15 insurance, real estate development permits. Competitive advantage: local market knowledge + AI augmentation.$seed$,
 'intel', 'reference', 'brain-seeder-v2-sql',
 array['florida','market','sarasota','real_estate'],
 1.0,
 '{"seeded": true, "seed_version": "v2-sql", "seed_order": 17}'::jsonb);

-- ═══════════════════════════════════════════════════════════
-- VERIFICATION
-- Run these as separate queries after the insert above succeeds.
-- ═══════════════════════════════════════════════════════════

-- Total count (expect 17)
-- select count(*) from public.thoughts where agent = 'brain-seeder-v2-sql';

-- Breakdown by namespace (expect 9 rows)
-- select source, count(*) as n from public.thoughts
-- where agent = 'brain-seeder-v2-sql'
-- group by source order by n desc;

-- BM25 search test (expect multiple rows about Alan)
-- select id, source, content from public.thoughts
-- where search_vector @@ websearch_to_tsquery('english', 'Alan Augustin founder');

-- Embedding status (expect 17 rows with embedding IS NULL)
-- select count(*) as null_embeddings from public.thoughts
-- where embedding is null and agent = 'brain-seeder-v2-sql';
