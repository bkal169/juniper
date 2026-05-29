# Context Sync — Memory Backend

This repository uses **[Context Sync](https://github.com/Intina47/context-sync)**
(`@context-sync/server`) as its local-first persistent-memory backend for AI
coding assistants (Claude Code, Cursor, Zed, Continue — any MCP client).

Context Sync stores project identity, decisions, constraints, and caveats in a
local SQLite store keyed by project path, so an agent resumes where the last
session ended instead of re-deriving context every time.

## Registered server

The MCP server is registered in [`.mcp.json`](./.mcp.json):

```json
"context-sync": { "command": "npx", "args": ["-y", "-p", "@context-sync/server", "context-sync"], "type": "stdio" }
```

`npx -y` fetches and runs the server on first use — no manual global install
required. All repos in this fleet share one local store keyed by path; set
`CONTEXT_SYNC_DB_PATH` to pin a custom location if needed.

## Tools

`set_project` · `remember` · `recall` · `read_file` · `search` · `structure` · `git` · `notion` (read-only)

## First-session bootstrap (auto-init)

Run once per environment to register this repo and seed its memory in one command:

```sh
sh scripts/context-sync-init.sh        # set_project + install git hooks + remember() the seed
sh scripts/context-sync-init.sh --dry-run   # validate .context-sync/seed.json without contacting the server
```

The script drives the MCP server over stdio (the tools are JSON-RPC, not shell
subcommands), reads structured identity from [`.context-sync/seed.json`](./.context-sync/seed.json),
calls `set_project`, then `remember`s each entry. Edit `seed.json` to evolve the
seeded memory; re-run to re-apply.

### Manual equivalent

In a fresh environment, call `set_project({ path: "<absolute path to this repo>" })`
(this also installs git context-capture hooks), then seed the identity below with
`remember` so it persists across sessions.

## Seed identity

- **Project:** Juniper (`bkal169/juniper`)
- **What it is:** Alan's war room + Legacy — autonomous agent runtime.
- **Stack:** Python agent (cron_main.py, agents/, mcp/), Supabase, deployed on Railway.
- **Notes:** See HANDOFF.md and WAKEUP.md for operating handoff. vault-init/ seeds agent memory.
