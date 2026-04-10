# JRIH Second Brain — Wake-Up Briefing

**Read this first when resuming work on this system.**

## Quick Context

You're looking at the JRIH Second Brain — a multi-agent system that serves as the operational memory and decision engine for Juniper Rose Investments & Holdings (JRIH). Founded by Alan Augustin.

**This is not a chatbot.** It's a persistent knowledge system with:
- **Supabase** as the brain (pgvector + BM25 hybrid search)
- **Juniper** as the autonomous orchestrator (LangGraph state machine)
- **Junior** as the adversarial QA gate (self-improving critic)
- **MCP server** giving Claude Desktop direct brain access
- **Cron jobs** running Juniper cycles, intel scans, and digests on Railway

## Branch

All work happens on: `claude/seed-jrih-brain-v2-22JJP`

## Repos

| Repo | What's There |
|------|-------------|
| `bkal169/juniper` | **This repo.** All agents, schemas, MCP, cron. |
| `bkal169/claude.md` | Vault-init CLAUDE.md + reference materials |
| `axiom-by-juniper-rose/axiom-os` | AxiomOS — gets CLAUDE.md seeded |
| `axiom-by-juniper-rose/lumenaos` | LumenaOS — gets CLAUDE.md seeded |
| `axiom-by-juniper-rose/hoj-os` | HOJ Foundation — gets CLAUDE.md seeded |
| `bkal169/jrih-command-center` | Command center dashboard — gets CLAUDE.md seeded |
| `axiom-by-juniper-rose/lifeos-dashboard` | LifeOS Notion integration |

## The 5 Divisions

1. **JRi** — AI/SaaS: AxiomOS, LumenaOS, ARO
2. **JR Capital** — DAC funding, financial services
3. **JR Realty** — Real estate, MLO, 2-15 insurance (Florida)
4. **Kintsugi Development** — Real estate development
5. **Heart of Juniper (HOJ)** — Community philanthropy

## Agent Architecture

```
Alan ←→ Rose (personal operator)
         ↓
Juniper (orchestrator) ←→ Junior (QA gate)
         ↓
[Juno | HOJ | Advisor | Intel | Synthesis]
         ↓
Supabase (thoughts table, hybrid search)
```

## Key Rules

- **Never delete, always append**
- **Junior approves before Juniper executes**
- **Confidence ≥ 0.92 = auto-execute, 0.75-0.92 = HITL review, < 0.75 = shelved**
- **48hr HITL escalation** — nothing rots in the queue
- **Model routing** — use the cheapest model that can do the job

## To Resume Development

1. `cd juniper && git checkout claude/seed-jrih-brain-v2-22JJP`
2. Read `HANDOFF.md` for full file manifest and deployment steps
3. Read `agents/config.py` for model routing and infrastructure constants
4. Check `tasks/todo_v2.md` for current task state
