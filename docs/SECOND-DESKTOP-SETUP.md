# JrIH Brain MCP — Second Desktop Setup Runbook

**Purpose:** Connect a second Windows desktop to the shared `jrih-brain` MCP server so both machines hit the same Supabase backend.

**Backend:** Shared Supabase project. No separate DB setup needed — the brain is shared across desktops.

---

## Prerequisites

- Windows machine with Claude Desktop installed
- Node.js installed
- Access to the `juniper/mcp/` folder (via OneDrive sync or manual copy)

---

## Step 1 — Get the MCP server file on machine 2

Server lives on machine 1 at:
`C:\Users\bkala\juniper\mcp\server.ts`

Two options:
1. **Same OneDrive account** — folder may already be synced. Verify the path resolves on machine 2.
2. **Manual copy** — copy the entire `C:\Users\bkala\juniper\mcp\` folder to the same path on machine 2.

Keep the path identical across machines so the config block is portable.

---

## Step 2 — Verify Node + tsx

Open PowerShell / terminal:

```
node --version
npx tsx --version
```

If `tsx` is missing:

```
npm install -g tsx
```

---

## Step 3 — Edit `claude_desktop_config.json`

Path: `C:\Users\[username]\AppData\Roaming\Claude\claude_desktop_config.json`

Add inside the `"mcpServers"` object:

```json
"jrih-brain": {
  "command": "npx",
  "args": [
    "tsx",
    "C:\\Users\\bkala\\juniper\\mcp\\server.ts"
  ],
  "env": {
    "SUPABASE_URL": "https://obtoinsjncbqdqgdeddl.supabase.co",
    "SUPABASE_SERVICE_KEY": "<service_role_key>",
    "OPENAI_API_KEY": "<openai_key>"
  }
}
```

**Notes:**
- Adjust the `args` path if the Windows username differs on machine 2.
- If `mcpServers` already has entries, add a comma before `"jrih-brain"`. One trailing/missing comma silently breaks every MCP.
- If Claude Desktop (GUI app) can't find `npx`, use the absolute path: `"command": "C:\\Program Files\\nodejs\\npx.cmd"` — Windows needs `.cmd`, not bare `npx`, when launched by GUI apps.

---

## Step 4 — Restart Claude Desktop

Fully quit (from the tray) and reopen. The `jrih-brain` MCP should appear connected.

Verify in chat:
> check jrih brain stats

It should pull live data from Supabase.

---

## Troubleshooting

- **MCP not appearing:** validate JSON at jsonlint.com — one stray comma breaks the whole config.
- **Connects but errors:** check the log at
  `%APPDATA%\Claude\logs\mcp-server-jrih-brain.log`
  — tsx/path/env errors surface there.
- **"command not found" style errors:** switch to absolute `npx.cmd` path (see Step 3 notes).
- **Env var issues:** confirm no stray whitespace or line breaks inside the key strings in the JSON.

---

## Security Notes

- `SUPABASE_SERVICE_KEY` bypasses RLS — treat like a root credential. Never commit to git, paste into chat, or share in screenshots.
- Rotate keys if exposed:
  - Supabase → Project Settings → API → roll `service_role` key
  - OpenAI → platform.openai.com → API keys → revoke + reissue
- After rotating, update the config on **every** machine.

---

## Quick Checklist

- [ ] `server.ts` accessible at expected path on machine 2
- [ ] `node --version` and `npx tsx --version` both return versions
- [ ] `claude_desktop_config.json` has `jrih-brain` block with valid JSON
- [ ] Correct username in args path
- [ ] Claude Desktop fully restarted
- [ ] "check jrih brain stats" returns live data
