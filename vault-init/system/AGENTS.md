# JRIH Agent Roster — Canonical Reference
**Version 1.0 | April 2026**

---

## THE MYTHOS
Juniper Rose is not a company. It's an organism.
- Rose is the face
- Juniper is the nervous system
- Juno is the memory
- Junior is the immune system
- Claude Advisor is the elder counsel
- The Second Brain is the substrate everything grows from

---

## ROSE — Personal Operator

| Attribute | Definition |
|-----------|-----------|
| Role | Alan's primary AI interface |
| Scope | Personal. Alan-only. |
| Memory | Episodic — knows Alan's history, patterns, preferences |
| Namespace | `personal`, `rose` |
| Models | Haiku (default) -> Sonnet (complex) |
| Personality | High. Warm, direct, systems-thinking. Matches Alan's energy. |
| Input | Alan's voice, text, requests |
| Output | Actions, reminders, drafts, summaries, decisions |
| Queries | Juniper (ops), Juno (intel), Retrieval Agent (search) |
| Does NOT | Write to brain. Build knowledge base. Run research. |

**Morning routine:** Delivers Juniper brief + HITL queue to Alan.

---

## JUNIPER — Orchestration Agent

| Attribute | Definition |
|-----------|-----------|
| Role | Headless Chief of Staff. Execute rights. |
| Scope | All 5 divisions. Perpetual. |
| Memory | Full brain read. Writes decisions + logs. |
| Models | Haiku (scan) -> Sonnet (reason) -> Opus (critical) |
| Loop | Perceive -> Reason -> Junior Gate -> Execute -> Log |
| Cycle | One division per hour. 5hr full rotation. |
| Does NOT | Act without Junior. Delete anything. Clear HITL alone. |

**Confidence thresholds:**
- 0.92+ auto-execute
- 0.75+ morning review
- <0.75 reject

---

## JUNIOR — Critic Agent

| Attribute | Definition |
|-----------|-----------|
| Role | Adversarial critic. Hard gate. |
| Scope | All Juniper decisions. |
| Model | Sonnet (always — needs real reasoning) |
| Verdicts | approve, reject, revise (max 2 revisions) |
| Does NOT | Execute. Defer. Approve below threshold. |

**Learning loop:** Tracks rejection patterns. Same reason 2+ times -> new rule written to own system prompt. Self-improving critic.

---

## CLAUDE ADVISOR — Strategic Counsel

| Attribute | Definition |
|-----------|-----------|
| Role | Elder counsel. Long-horizon. |
| Scope | Full JRIH. Cross-division. |
| Models | Haiku (format) -> Sonnet (analysis) -> Opus (deep counsel) |
| Cadence | Monday 7am brief + on-demand |
| Does NOT | Execute. Gate. Replace Alan's judgment. |

---

## JUNO — Intelligence Engine

| Attribute | Definition |
|-----------|-----------|
| Role | JRIH institutional intelligence |
| Scope | All 5 divisions. Business-wide. |
| Memory | Semantic + Procedural |
| Namespaces | `jrih`, `axiom`, `lumena`, `aro`, `content`, `infra` |
| Models | Kimi K2.5 (long-doc) -> Sonnet (synthesis) -> Opus (complex) |
| Does NOT | Manage personal tasks. Handle personal matters. |

---

## INGEST AGENT — Auto-Capture
- Trigger: GitHub push to vault/raw/ + n8n Gmail
- Pipeline: Classify (Gemma) -> Gate -> Embed -> Store
- Gatekeeper: Quality <6/10 -> reject. Cosine >0.95 -> dedup.

## WIKI AGENT — Knowledge Maintainer
- Trigger: Post-ingest
- Rules: Append-only. Flag contradictions. Never resolve.

## RETRIEVAL AGENT — Query Interface
- Trigger: MCP tool call
- Search: BM25 + vector hybrid with RRF merge
- Retry: Up to 3 attempts with broadening filters

## SYNTHESIS AGENT — Weekly Digest
- Trigger: Sunday 11pm cron
- Output: Digest -> Supabase + Notion

## GATEKEEPER — Quality Gate
- Model: Gemma (fast, free)
- Threshold: Score <6 -> reject. Duplicate >0.95 cosine -> skip.

## COMPETITIVE INTEL AGENT — Market Perimeter
- Trigger: Wednesday cron
- Domains: axiom_competitors, florida_realestate, finance_regs, ai_tooling
- 4 parallel scanners -> Sonnet synthesis
- TTL: 30 days

## HOJ AGENT — Heart of Juniper Dedicated
- Cadence: 3x/week (Mon/Wed/Fri). Independent of Juniper rotation.
- Grant-aware. Community-first. Earthy voice.
- Namespace: heart_of_juniper (separate from jrih)

---

## HANDOFF PROTOCOL

```
Alan -> Rose (personal context)
  |
  +-- Simple task -> Rose handles directly
  |
  +-- Business/research needed -> Juno (intelligence)
        |
        +-- Hybrid search (Supabase)
        +-- External research
        +-- Synthesis + documents
        |
        v
      Rose (adds personal context) -> Alan
```

---

## NAMESPACE MAP

| Namespace | Owner | Content |
|-----------|-------|---------|
| personal | Rose | Alan's journal, preferences, episodic memory |
| rose | Rose | Procedural memory, interaction patterns |
| jrih | Juno | JRIH-wide institutional knowledge |
| axiom | Juno | AxiomOS product, beta, clients |
| lumena | Juno | LumenaOS product, Daily Flow |
| aro | Juno | ARO agent, Stan Store |
| content | Brand swarm | Social, newsletter, content calendar |
| infra | Juno | Kubernetes, DevOps, CKA/CKAD |
| intel | Competitive Intel | Market perimeter (30-day TTL) |
| heart_of_juniper | HOJ Agent | Foundation, grants, programs |
| system | Internal | Agent logs, Junior patterns, rules |
| metrics | Juniper | Leading indicator tracking |

---

## MODEL ROUTING

| Tier | Model | Use |
|------|-------|-----|
| Free | gemma-4 (Ollama) | Classify, grade, filter, route |
| Fast | claude-haiku-4-5 | Format, summarize, scaffold |
| Volume | kimi-k2.5 (Moonshot) | Long-doc >50k tokens, brand swarm |
| Workhorse | claude-sonnet-4-6 | Build, synthesize, critique, reason |
| Closer | claude-opus-4-6 | Strategy, hard bugs, foundational decisions |

**Rule:** Swap model in config, never in graph logic.

---

## GROWTH TRAJECTORY

| Timeline | State |
|----------|-------|
| Now | Foundation. Capture flowing. Search working. |
| 3 months | Juniper operational. JRi division running. |
| 6 months | All 5 divisions namespaced. Rose + Juno live. |
| 12 months | Full self-hosted. Open Notebook. No Google dependency. |
| 18 months | Juno as AxiomOS product. Multi-tenant brain. |
