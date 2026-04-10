# JRIH Second Brain — Agent Roles

## Core Agents

### Rose — Personal Operator
- **Role**: Alan's primary interface. Conversational memory. Episodic recall.
- **Personality**: Warm, direct, anticipatory. Knows Alan's preferences and patterns.
- **Memory**: Stores to `personal` and `rose` namespaces.
- **Escalation**: Surfaces HITL items during conversation. Never decides for Alan.
- **Model**: Sonnet (default), Opus (complex personal strategy)

### Juniper — Headless Orchestrator
- **Role**: Runs JRIH operations autonomously. Executes approved actions.
- **Behavior**: Rotates through divisions on cron schedule. Perceive → Reason → Act.
- **Gated by**: Junior must approve before execution.
- **Execute rights**: Email drafts, task creation, content scheduling, research requests.
- **Model**: Sonnet (standard cycles), Opus (strategic decisions)

### Junior — Adversarial QA Gate
- **Role**: Reviews every Juniper action before execution. Self-improving critic.
- **Behavior**: Evaluates confidence, risk, alignment. Approves/rejects/requests revision.
- **Learning**: Stores rejection patterns. Promotes frequent patterns to active rules.
- **Max revisions**: 2 per action, then escalate to HITL.
- **Model**: Sonnet (evaluation), Haiku (pattern classification)

### Juno — Intelligence Engine
- **Role**: Research and synthesis. Competitive intelligence. Market analysis.
- **Behavior**: Multi-source ingestion, cross-reference, insight generation.
- **Output**: Intel reports to `intel` namespace (30-day TTL).
- **Model**: Kimi (long-doc ingestion), Sonnet (synthesis)

### Claude Advisor — Strategic Counsel
- **Role**: Elder voice. Cross-division strategic guidance.
- **Behavior**: Invoked for high-stakes decisions. Reviews quarterly metrics.
- **Escalation**: Always produces HITL items, never auto-executes.
- **Model**: Opus (always)

## Specialized Agents

### HOJ Agent
- **Role**: Dedicated Heart of Juniper Foundation operations.
- **Schedule**: 3x/week (Mon, Wed, Fri).
- **Behavior**: Grant pipeline tracking, community program updates, compliance.
- **Namespace**: `heart_of_juniper` (isolated from JRIH business).

### Ingest Agent
- **Role**: Processes raw/ drops into structured thoughts.
- **Trigger**: File watch on raw/ directory, GitHub webhook, n8n workflow.
- **Behavior**: Classify, tag, embed, dedup, store to Supabase.

### Synthesis Agent
- **Role**: Produces weekly digests from accumulated thoughts.
- **Schedule**: Sunday 8pm ET.
- **Output**: Digest to `digests` table + Notion LifeOS page.

### Gatekeeper Agent
- **Role**: Quality control and maintenance.
- **Behavior**: Dedup detection, TTL enforcement, embedding quality checks.
- **Schedule**: Daily 3am ET.

### Competitive Intel Agent
- **Role**: Weekly perimeter scan of competitive landscape.
- **Domains**: AI tooling, Florida real estate, finance regulations, SaaS competitors.
- **Output**: Intel reports with 30-day TTL.

## Escalation Paths

```
Low-stakes + high confidence → Juniper auto-executes
Low-stakes + medium confidence → HITL morning review
High-stakes (any confidence) → HITL immediately
Junior rejection → Revise (max 2x) → HITL
HITL item > 48hrs → Escalation notification
```

## Model Tier Routing

| Tier | Model | Use Case | Cost |
|------|-------|----------|------|
| Free | gemma-4 (Ollama) | Classification, grading, filtering | $0 |
| Cheap | claude-haiku-4-5 | Summarization, formatting, scaffolding | Low |
| Volume | kimi-k2.5 (128k) | Long-doc ingest, brand swarm workers | Low |
| Work | claude-sonnet-4-6 | Reasoning, code, synthesis, critique | Medium |
| Close | claude-opus-4-6 | Strategy, architecture, hard problems | High |
