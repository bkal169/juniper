-- JRIH Second Brain — Juniper Audit Tables
-- Run AFTER schema.sql
-- Target: Supabase project ubdhpacoqmlxudcvhyuu

-- ═══════════════════════════════════════════════════════════
-- JUNIPER AUDIT LOG
-- Every Juniper decision cycle logged here.
-- ═══════════════════════════════════════════════════════════

create table if not exists public.juniper_audit (
  id uuid default uuid_generate_v4() primary key,
  cycle_id text not null,                -- unique per cycle run
  division text not null,                -- jri, jr_capital, jr_realty, kintsugi, hoj
  phase text not null,                   -- perceive, reason, junior_gate, execute, log
  action_type text,                      -- email, deploy, task, research, content, contract, memory
  decision text,                         -- what Juniper decided to do
  confidence float,                      -- Juniper's confidence score
  junior_verdict text,                   -- approve, reject, revise
  junior_reason text,                    -- why Junior approved/rejected
  revision_count int default 0,          -- 0-2, max 2 revisions
  executed boolean default false,
  execution_result text,
  model_used text,                       -- which model handled this phase
  tokens_used int,
  cost_usd numeric(10,6),
  error text,
  metadata jsonb default '{}',
  created_at timestamptz default now()
);

create index if not exists idx_audit_cycle on public.juniper_audit(cycle_id);
create index if not exists idx_audit_division on public.juniper_audit(division);
create index if not exists idx_audit_created on public.juniper_audit(created_at desc);
create index if not exists idx_audit_verdict on public.juniper_audit(junior_verdict);

-- ═══════════════════════════════════════════════════════════
-- JUNIOR PATTERNS
-- Junior's self-improving memory. Rejection patterns.
-- ═══════════════════════════════════════════════════════════

create table if not exists public.junior_patterns (
  id uuid default uuid_generate_v4() primary key,
  pattern_type text not null,            -- rejection_reason, approval_pattern, edge_case
  division text,
  decision_type text,                    -- email, deploy, task, etc.
  description text not null,
  occurrence_count int default 1,
  is_rule boolean default false,         -- true = promoted to active rule
  rule_text text,                        -- the rule Junior wrote for itself
  first_seen timestamptz default now(),
  last_seen timestamptz default now(),
  created_at timestamptz default now()
);

create index if not exists idx_patterns_type on public.junior_patterns(pattern_type);
create index if not exists idx_patterns_rule on public.junior_patterns(is_rule) where is_rule = true;

-- ═══════════════════════════════════════════════════════════
-- JUNIPER STATS VIEW
-- Quick operational health snapshot.
-- ═══════════════════════════════════════════════════════════

create or replace function juniper_stats(days int default 7)
returns table (
  total_cycles bigint,
  approval_rate float,
  rejection_rate float,
  avg_confidence float,
  total_executions bigint,
  hitl_pending bigint,
  hitl_overdue bigint,
  thoughts_count bigint,
  thoughts_this_period bigint,
  top_division text,
  active_junior_rules bigint
)
language sql
as $$
  select
    (select count(*) from public.juniper_audit where created_at > now() - (days || ' days')::interval),
    (select count(*)::float / nullif(count(*), 0) from public.juniper_audit where junior_verdict = 'approve' and created_at > now() - (days || ' days')::interval),
    (select count(*)::float / nullif(count(*), 0) from public.juniper_audit where junior_verdict = 'reject' and created_at > now() - (days || ' days')::interval),
    (select avg(confidence) from public.juniper_audit where created_at > now() - (days || ' days')::interval),
    (select count(*) from public.juniper_audit where executed = true and created_at > now() - (days || ' days')::interval),
    (select count(*) from public.hitl_queue where status = 'pending'),
    (select count(*) from public.hitl_queue where status = 'pending' and created_at < now() - interval '48 hours'),
    (select count(*) from public.thoughts),
    (select count(*) from public.thoughts where created_at > now() - (days || ' days')::interval),
    (select division from public.juniper_audit where created_at > now() - (days || ' days')::interval group by division order by count(*) desc limit 1),
    (select count(*) from public.junior_patterns where is_rule = true);
$$;

-- ═══════════════════════════════════════════════════════════
-- GRAPH RELATIONSHIPS (Graphify bridge)
-- Stores entity connections from graph.json for hybrid search.
-- ═══════════════════════════════════════════════════════════

create table if not exists public.graph_relationships (
  id uuid default uuid_generate_v4() primary key,
  source_entity text not null,
  target_entity text not null,
  relationship_type text,               -- mentions, related_to, depends_on, part_of
  weight float default 1.0,
  source_file text,                     -- vault file path
  metadata jsonb default '{}',
  created_at timestamptz default now()
);

create index if not exists idx_graph_source on public.graph_relationships(source_entity);
create index if not exists idx_graph_target on public.graph_relationships(target_entity);

-- ═══════════════════════════════════════════════════════════
-- RLS for new tables
-- ═══════════════════════════════════════════════════════════

alter table public.juniper_audit enable row level security;
alter table public.junior_patterns enable row level security;
alter table public.graph_relationships enable row level security;

create policy "Service role full access on juniper_audit"
  on public.juniper_audit for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy "Service role full access on junior_patterns"
  on public.junior_patterns for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy "Service role full access on graph_relationships"
  on public.graph_relationships for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
