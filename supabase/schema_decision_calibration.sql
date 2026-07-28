-- ═══════════════════════════════════════════════════════════
-- DECISION CALIBRATION — Build #1: Calibrated HITL Sigmoid Gate
-- ═══════════════════════════════════════════════════════════
--
-- TARGET PROJECT: Mycelium OS · zqrgazuaideuumksijhe
--
-- ⚠ PROJECT-ID DISCIPLINE — read before running this file.
--
--   HANDOFF.md names the Brain DB as `obtoinsjncbqdqgdeddl`. That reference
--   is STALE. The Brain DB migrated obtoinsjncbqdqgdeddl → zqrgazuaideuumksijhe
--   on 2026-04-28 (see agents/heartbeat.py Phase 13.3 note); the 99-thought
--   backfill completed 2026-05-01 (WHITELABEL.md Phase 11.5), which also
--   repointed the Railway service env vars.
--
--   `obtoinsjncbqdqgdeddl` is now the LIVE Heart of Juniper production backend
--   (real donor / grant / participant data). Running this file there would put
--   agent-orchestration infrastructure inside HOJ's production database.
--   DO NOT.
--
--   Both ids are real Supabase projects — obtoins is NOT "hallucinated" as
--   CLAUDE.md's HARD RULE states; it is the legacy project (created 2026-04-05,
--   named "jrih-command-center") that was later repurposed for HOJ. The 2026-05-05
--   incident was a write to the wrong-but-real project. Canon-debt noted.
--
-- Idempotent — safe to re-run.
-- ═══════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════
-- DECISION CALIBRATION LEDGER
-- One row per gated decision. `outcome` is the training label.
-- ═══════════════════════════════════════════════════════════

create table if not exists public.decision_calibration (
  id            uuid default uuid_generate_v4() primary key,
  tenant_id     uuid not null default 'f2d21a43-4ba7-4f7f-8bf8-49ef986ad3dc',
  agent         text not null,              -- juniper, lumen_grader, axiom, ...
  decision_ref  text not null,              -- pointer to the action/decision
  logit         double precision not null,  -- raw score z (pre-sigmoid, log-odds space)
  p             double precision not null,  -- calibrated sigma(A*z + B) at decision time
  tau           double precision not null,  -- threshold in force at decision time
  auto_executed boolean not null,
  outcome       smallint,                   -- 1 correct, 0 wrong, null = pending
  hitl_item_id  uuid references public.hitl_queue(id),  -- set when routed to HITL
  created_at    timestamptz default now(),
  resolved_at   timestamptz,
  constraint decision_calibration_outcome_chk check (outcome is null or outcome in (0, 1)),
  constraint decision_calibration_p_chk       check (p >= 0 and p <= 1),
  constraint decision_calibration_tau_chk     check (tau >= 0 and tau <= 1)
);

create index if not exists idx_deccal_agent   on public.decision_calibration(agent);
create index if not exists idx_deccal_created on public.decision_calibration(created_at desc);

-- Recalibration reads resolved rows per agent — partial index keeps the nightly job cheap.
create index if not exists idx_deccal_resolved
  on public.decision_calibration(agent, resolved_at desc)
  where outcome is not null;

-- Outcome sync joins back to the HITL row Alan resolved.
create index if not exists idx_deccal_hitl
  on public.decision_calibration(hitl_item_id)
  where hitl_item_id is not null;


-- ═══════════════════════════════════════════════════════════
-- GATE CONFIG
-- Per-agent tau + Platt calibration params. The nightly job writes here.
-- Defaults are deliberately a NO-OP calibration (A=1, B=0 → p = sigma(z)).
-- ═══════════════════════════════════════════════════════════

create table if not exists public.decision_gate_config (
  agent            text primary key,
  tau              double precision not null default 0.80,  -- auto-execute above this
  tau_floor        double precision not null default 0.60,  -- recalibration may tighten, never remove
  target_precision double precision not null default 0.95,  -- desired correctness of auto-executed actions
  platt_a          double precision not null default 1.0,   -- calibration slope
  platt_b          double precision not null default 0.0,   -- calibration intercept
  min_samples      integer          not null default 50,    -- refuse to refit below this
  max_tau_step     double precision not null default 0.10,  -- anti-whiplash clamp per run
  last_fit_at      timestamptz,
  last_fit_n       integer,
  updated_at       timestamptz default now(),
  constraint decision_gate_config_tau_chk   check (tau >= tau_floor and tau <= 1),
  constraint decision_gate_config_floor_chk check (tau_floor > 0 and tau_floor <= 1)
);

-- Seed the first gated decision path. Others are created on demand by the gate.
insert into public.decision_gate_config (agent) values ('juniper')
  on conflict (agent) do nothing;


-- ═══════════════════════════════════════════════════════════
-- STATS VIEW
-- Serves the Definition-of-Done checks: false-auto-action rate and
-- HITL-queue diversion rate, per agent, before vs after recalibration.
-- ═══════════════════════════════════════════════════════════

create or replace view public.decision_calibration_stats as
select
  agent,
  count(*)                                                          as n_total,
  count(*) filter (where auto_executed)                             as n_auto,
  count(*) filter (where not auto_executed)                         as n_hitl,
  count(*) filter (where outcome is not null)                       as n_resolved,
  count(*) filter (where auto_executed and outcome is not null)     as n_resolved_auto,
  count(*) filter (where auto_executed and outcome = 0)             as n_false_auto,
  -- precision on auto-executed actions; null until some auto rows are resolved
  avg(outcome::double precision) filter (where auto_executed and outcome is not null)
                                                                    as auto_precision,
  avg(outcome::double precision) filter (where outcome is not null) as overall_precision,
  max(created_at)                                                   as last_decision_at
from public.decision_calibration
group by agent;


-- ═══════════════════════════════════════════════════════════
-- RLS — service_role only, matching schema.sql / schema_juniper.sql convention
-- ═══════════════════════════════════════════════════════════

alter table public.decision_calibration  enable row level security;
alter table public.decision_gate_config  enable row level security;

drop policy if exists "service_role_all_decision_calibration" on public.decision_calibration;
create policy "service_role_all_decision_calibration" on public.decision_calibration
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

drop policy if exists "service_role_all_decision_gate_config" on public.decision_gate_config;
create policy "service_role_all_decision_gate_config" on public.decision_gate_config
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
