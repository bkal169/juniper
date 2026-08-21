#!/usr/bin/env sh
# Thin wrapper: register this project with Context Sync and seed its memory.
# Requires Node (already a prerequisite of the context-sync MCP server).
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
exec node "$DIR/context-sync-init.mjs" --repo-root "$(cd "$DIR/.." && pwd)" "$@"
