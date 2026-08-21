#!/usr/bin/env node
// Context Sync auto-init: drives the @context-sync/server MCP stdio server to
// register this project and seed its memory from .context-sync/seed.json.
//
// The context-sync tools (set_project, remember, ...) are MCP JSON-RPC tools,
// not shell subcommands, so we speak newline-delimited JSON-RPC over stdio.
//
// Usage: node scripts/context-sync-init.mjs [--repo-root <path>] [--dry-run]

import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
const DRY_RUN = process.argv.includes("--dry-run");
const REPO_ROOT = resolve(arg("--repo-root", resolve(__dirname, "..")));
const SEED_PATH = resolve(REPO_ROOT, ".context-sync/seed.json");

const seed = JSON.parse(readFileSync(SEED_PATH, "utf8"));
const memory = Array.isArray(seed.memory) ? seed.memory : [];

console.log(`[context-sync] repo:    ${seed.repo ?? "(unknown)"}`);
console.log(`[context-sync] path:    ${REPO_ROOT}`);
console.log(`[context-sync] purpose: ${seed.purpose ?? "(none)"}`);
console.log(`[context-sync] memory:  ${memory.length} entries`);

if (DRY_RUN) {
  console.log("[context-sync] --dry-run: seed parsed OK, not contacting server.");
  process.exit(0);
}

// Build the ordered list of tool calls.
const calls = [
  { name: "set_project", arguments: { path: REPO_ROOT, purpose: seed.purpose ?? "" } },
  ...memory.map((m) => ({ name: "remember", arguments: { type: m.type, content: m.content } })),
];

const child = spawn("npx", ["-y", "-p", "@context-sync/server", "context-sync"], {
  stdio: ["pipe", "pipe", "inherit"],
  env: process.env,
});

let buf = "";
let sawOutput = false;
const pending = new Map();
let nextId = 1;

function send(method, params) {
  const id = nextId++;
  const msg = { jsonrpc: "2.0", id, method, params };
  child.stdin.write(JSON.stringify(msg) + "\n");
  return new Promise((res, rej) => pending.set(id, { res, rej }));
}
function notify(method, params) {
  child.stdin.write(JSON.stringify({ jsonrpc: "2.0", method, params }) + "\n");
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// The server runs a DB migration and prints non-JSON startup lines before its
// stdin reader is ready, so initialize can race startup. Retry until answered.
async function initialize() {
  for (let i = 0; !sawOutput && i < 50; i++) await sleep(100); // wait for first server output
  await sleep(300);
  for (let attempt = 1; attempt <= 4; attempt++) {
    const id = nextId++;
    child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method: "initialize",
      params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "context-sync-init", version: "1.0.0" } } }) + "\n");
    const got = await Promise.race([
      new Promise((res) => pending.set(id, { res, rej: res })),
      sleep(3000).then(() => "__timeout__"),
    ]);
    pending.delete(id);
    if (got !== "__timeout__") return got;
    console.log(`[context-sync]   …initialize retry ${attempt}`);
  }
  throw new Error("server did not respond to initialize");
}

child.stdout.on("data", (chunk) => {
  sawOutput = true;
  buf += chunk.toString();
  let nl;
  while ((nl = buf.indexOf("\n")) !== -1) {
    const line = buf.slice(0, nl).trim();
    buf = buf.slice(nl + 1);
    if (!line) continue;
    let msg;
    try { msg = JSON.parse(line); } catch { continue; } // ignore non-JSON log lines
    if (msg.id != null && pending.has(msg.id)) {
      const { res, rej } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
    }
  }
});

const fail = (e) => { console.error(`[context-sync] FAILED: ${e?.message ?? e}`); child.kill(); process.exit(1); };
child.on("error", fail);

(async () => {
  await send("initialize", {
    protocolVersion: "2025-06-18",
    capabilities: {},
    clientInfo: { name: "context-sync-init", version: "1.0.0" },
  });
  notify("notifications/initialized", {});

  for (const c of calls) {
    const r = await send("tools/call", c);
    const detail = c.name === "remember" ? `${c.arguments.type}` : "";
    if (r?.isError) throw new Error(`${c.name} ${detail}: ${JSON.stringify(r.content)}`);
    console.log(`[context-sync]   ✓ ${c.name}${detail ? " (" + detail + ")" : ""}`);
  }

  console.log("[context-sync] done — project registered and memory seeded.");
  child.stdin.end();
  child.kill();
  process.exit(0);
})().catch(fail);
