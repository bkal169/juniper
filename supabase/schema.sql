-- JRIH Second Brain — Core Schema
-- Target: Supabase project ubdhpacoqmlxudcvhyuu
-- Run this FIRST, then schema_juniper.sql

-- ═══════════════════════════════════════════════════════════
-- EXTENSIONS
-- ═══════════════════════════════════════════════════════════

create extension if not exists "uuid-ossp";
create extension if not exists "vector";

-- ═══════════════════════════════════════════════════════════
-- CORE TABLE: thoughts
-- Every piece of knowledge in the brain lives here.
-- ═══════════════════════════════════════════════════════════

create table if not exists public.thoughts (
  id uuid default uuid_generate_v4() primary key,
  title text,                                    -- optional short title (auto-generated or manual)
  content text not null,
  summary text,                                  -- AI-generated summary (first 2 sentences or LLM)
  source text not null,                          -- namespace: jrih, axiom, lumena, aro, personal, content, infra, intel, heart_of_juniper, system, metrics
  entry_type text not null default 'observation', -- observation, decision, task, reference, insight, question, flagged
  agent text,                                     -- which agent wrote this
  tags text[] default '{}',
  embedding vector(1536),                         -- text-embedding-3-small
  confidence float default 1.0,
  ttl interval,                                   -- null = permanent, else auto-expire
  expires_at timestamptz,                         -- computed from ttl on insert
  search_vector tsvector,                         -- BM25 full-text search
  metadata jsonb default '{}',                    -- flexible extra data
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Full-text search index
create index if not exists idx_thoughts_search on public.thoughts using gin(search_vector);

-- Vector similarity (HNSW for speed)
create index if not exists idx_thoughts_embedding on public.thoughts
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

-- Common query patterns
create index if not exists idx_thoughts_source on public.thoughts(source);
create index if not exists idx_thoughts_entry_type on public.thoughts(entry_type);
create index if not exists idx_thoughts_agent on public.thoughts(agent);
create index if not exists idx_thoughts_created on public.thoughts(created_at desc);
create index if not exists idx_thoughts_tags on public.thoughts using gin(tags);
create index if not exists idx_thoughts_expires on public.thoughts(expires_at) where expires_at is not null;

-- Auto-update search_vector on insert/update
create or replace function update_search_vector()
returns trigger as $$
begin
  new.search_vector := to_tsvector('english', coalesce(new.content, '') || ' ' || coalesce(new.source, '') || ' ' || coalesce(array_to_string(new.tags, ' '), ''));
  if new.ttl is not null and new.expires_at is null then
    new.expires_at := now() + new.ttl;
  end if;
  new.updated_at := now();
  return new;
end;
$$ language plpgsql;

create or replace trigger thoughts_search_vector_trigger
  before insert or update on public.thoughts
  for each row execute function update_search_vector();

-- ═══════════════════════════════════════════════════════════
-- HITL QUEUE
-- Items waiting for Alan's decision.
-- ═══════════════════════════════════════════════════════════

create table if not exists public.hitl_queue (
  id uuid default uuid_generate_v4() primary key,
  item_type text not null,              -- conflict, high_stakes, low_confidence, junior_reject, hoj_grant
  title text not null,
  context text,                         -- full context for decision
  source_thought_id uuid references public.thoughts(id),
  agent text,                           -- which agent flagged this
  division text,                        -- jri, jr_capital, jr_realty, kintsugi, hoj
  confidence float,
  status text default 'pending',        -- pending, approved, rejected, deferred, redirected
  resolution text,                      -- Alan's decision reason
  resolved_at timestamptz,
  resolved_by text default 'alan',
  created_at timestamptz default now(),
  escalated_at timestamptz              -- set when 48hr rule triggers
);

create index if not exists idx_hitl_status on public.hitl_queue(status);
create index if not exists idx_hitl_created on public.hitl_queue(created_at desc);

-- ═══════════════════════════════════════════════════════════
-- DIGESTS
-- Weekly synthesis outputs.
-- ═══════════════════════════════════════════════════════════

create table if not exists public.digests (
  id uuid default uuid_generate_v4() primary key,
  week_label text not null,             -- e.g. "2026-W15"
  content text not null,
  sources jsonb default '[]',           -- thought IDs that contributed
  agent text default 'synthesis-agent',
  created_at timestamptz default now()
);

-- ═══════════════════════════════════════════════════════════
-- METRICS
-- Leading indicator tracking. Juniper writes weekly.
-- ═══════════════════════════════════════════════════════════

create table if not exists public.jrih_metrics (
  id uuid default uuid_generate_v4() primary key,
  period text not null,                 -- "2026-W15" or "2026-04"
  metric_name text not null,
  metric_value numeric,
  metric_unit text,                     -- dollars, count, percent, rate
  division text,                        -- jri, jr_capital, jr_realty, kintsugi, hoj, jrih
  notes text,
  agent text default 'juniper',
  created_at timestamptz default now()
);

create index if not exists idx_metrics_period on public.jrih_metrics(period);
create index if not exists idx_metrics_name on public.jrih_metrics(metric_name);

-- ═══════════════════════════════════════════════════════════
-- HYBRID SEARCH FUNCTION
-- BM25 + vector similarity with RRF merge.
-- ═══════════════════════════════════════════════════════════

create or replace function hybrid_search(
  query_text text,
  query_embedding vector(1536),
  match_count int default 10,
  source_filter text default null,
  entry_type_filter text default null,
  rrf_k int default 60
)
returns table (
  id uuid,
  content text,
  source text,
  entry_type text,
  agent text,
  tags text[],
  confidence float,
  created_at timestamptz,
  metadata jsonb,
  rrf_score float
)
language plpgsql
as $$
begin
  return query
  with vector_results as (
    select
      t.id,
      row_number() over (order by t.embedding <=> query_embedding) as vector_rank
    from public.thoughts t
    where (source_filter is null or t.source = source_filter)
      and (entry_type_filter is null or t.entry_type = entry_type_filter)
      and t.embedding is not null
      and (t.expires_at is null or t.expires_at > now())
    order by t.embedding <=> query_embedding
    limit match_count * 3
  ),
  text_results as (
    select
      t.id,
      row_number() over (order by ts_rank_cd(t.search_vector, websearch_to_tsquery('english', query_text)) desc) as text_rank
    from public.thoughts t
    where t.search_vector @@ websearch_to_tsquery('english', query_text)
      and (source_filter is null or t.source = source_filter)
      and (entry_type_filter is null or t.entry_type = entry_type_filter)
      and (t.expires_at is null or t.expires_at > now())
    limit match_count * 3
  ),
  rrf_scores as (
    select
      coalesce(v.id, t.id) as id,
      coalesce(1.0 / (rrf_k + v.vector_rank), 0.0) +
      coalesce(1.0 / (rrf_k + t.text_rank), 0.0) as score
    from vector_results v
    full outer join text_results t on v.id = t.id
  )
  select
    th.id,
    th.content,
    th.source,
    th.entry_type,
    th.agent,
    th.tags,
    th.confidence,
    th.created_at,
    th.metadata,
    r.score::float as rrf_score
  from rrf_scores r
  join public.thoughts th on th.id = r.id
  order by r.score desc
  limit match_count;
end;
$$;

-- ═══════════════════════════════════════════════════════════
-- HELPER: get pending HITL items
-- ═══════════════════════════════════════════════════════════

create or replace function get_pending_hitl(max_items int default 20)
returns table (
  id uuid,
  item_type text,
  title text,
  context text,
  division text,
  confidence float,
  age_hours float,
  created_at timestamptz
)
language sql
as $$
  select
    h.id,
    h.item_type,
    h.title,
    h.context,
    h.division,
    h.confidence,
    extract(epoch from (now() - h.created_at)) / 3600.0 as age_hours,
    h.created_at
  from public.hitl_queue h
  where h.status = 'pending'
  order by
    case when h.item_type = 'high_stakes' then 0
         when h.item_type = 'hoj_grant' then 1
         when h.item_type = 'junior_reject' then 2
         when h.item_type = 'conflict' then 3
         else 4 end,
    h.created_at asc
  limit max_items;
$$;

-- ═══════════════════════════════════════════════════════════
-- TTL CLEANUP (called by pg_cron nightly at 3am)
-- ═══════════════════════════════════════════════════════════

create or replace function cleanup_expired_thoughts()
returns int
language plpgsql
as $$
declare
  deleted_count int;
begin
  delete from public.thoughts
  where expires_at is not null and expires_at < now();
  get diagnostics deleted_count = row_count;
  return deleted_count;
end;
$$;

-- Schedule nightly cleanup (requires pg_cron extension)
-- select cron.schedule('ttl-cleanup', '0 3 * * *', 'select cleanup_expired_thoughts()');

-- ═══════════════════════════════════════════════════════════
-- MORNING BRIEFS
-- Auto-generated daily summaries for Alan.
-- ═══════════════════════════════════════════════════════════

create table if not exists public.morning_briefs (
  id uuid default uuid_generate_v4() primary key,
  brief_date date not null unique,
  content text not null,
  hitl_summary text,                    -- pending HITL items digest
  division_highlights jsonb default '{}',
  agent text default 'synthesis-agent',
  created_at timestamptz default now()
);

create index if not exists idx_briefs_date on public.morning_briefs(brief_date desc);

-- ═══════════════════════════════════════════════════════════
-- RLS POLICIES
-- ═══════════════════════════════════════════════════════════

alter table public.thoughts enable row level security;
alter table public.hitl_queue enable row level security;
alter table public.digests enable row level security;
alter table public.jrih_metrics enable row level security;

-- Service role has full access (agents use service key)
create policy "Service role full access on thoughts"
  on public.thoughts for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy "Service role full access on hitl_queue"
  on public.hitl_queue for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy "Service role full access on digests"
  on public.digests for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy "Service role full access on jrih_metrics"
  on public.jrih_metrics for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

alter table public.morning_briefs enable row level security;

create policy "Service role full access on morning_briefs"
  on public.morning_briefs for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
