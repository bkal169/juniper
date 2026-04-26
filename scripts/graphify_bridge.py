"""
JRIH — Graphify Bridge Script
Parses graph.json -> writes key relationships to Supabase.
Enables Retrieval Agent to query graph connections via hybrid search.

Usage:
  python graphify_bridge.py sync     # Sync graph.json -> Supabase
  python graphify_bridge.py reindex  # Full Graphify re-index + sync
  python graphify_bridge.py query "AxiomOS"  # Find connected entities
"""

import sys
import json
import os
import subprocess
from datetime import datetime

from config import sb


# ── Correct paths (patched 2026-04-14) ───────────────────────────────────────
# graph.json is produced by _graphify.ps1 and lives in jrih-brain-graph.
# The vault that was indexed is lifeos-full (C:\Users\bkala\lifeos-full).
GRAPH_PATH = r'C:\Users\bkala\jrih-brain-graph\lifeos-full\graph.json'
VAULT_PATH = r'C:\Users\bkala\jrih-brain-graph\lifeos-full'

# Fallback: also check the OneDrive vault location
_VAULT_ALT = r'C:\Users\bkala\OneDrive\Documents\Life OS'


def load_graph() -> dict:
    """Load graph.json from Graphify output."""
    if not os.path.exists(GRAPH_PATH):
        print(f"  graph.json not found at {GRAPH_PATH}")
        print(f"  Run: graphify \"{VAULT_PATH}\"")
        return {}

    with open(GRAPH_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _expand_hyperedges(graph: dict) -> tuple[list, list]:
    """
    Normalise graphify's output format.

    graphify produces a structure with top-level 'graph.hyperedges' —
    each hyperedge has:
        id, label, nodes (list of node-ids), relation, source_file, …

    We flatten these into pairwise edges so sync_to_supabase() can
    write one row per pair of connected nodes.

    Also handles the legacy format where the file has top-level
    'nodes' + ('edges' | 'links') arrays.
    """
    # Legacy format: top-level nodes/edges
    if 'nodes' in graph and ('edges' in graph or 'links' in graph):
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', graph.get('links', []))
        return nodes, edges

    # Graphify format: graph.hyperedges
    hyperedges = (
        graph.get('graph', {}).get('hyperedges', [])
        or graph.get('hyperedges', [])
    )

    if not hyperedges:
        return [], []

    # Collect unique node ids
    node_set: set[str] = set()
    pairwise: list[dict] = []

    for he in hyperedges:
        members = he.get('nodes', [])
        relation = he.get('relation', he.get('type', 'related_to'))
        source_file = he.get('source_file', '')
        confidence = he.get('confidence_score', 1.0)

        # Record all node ids
        for m in members:
            node_set.add(str(m))

        # Expand to pairwise edges (fan-out from first member)
        if len(members) >= 2:
            anchor = str(members[0])
            for peer in members[1:]:
                pairwise.append({
                    'source': anchor,
                    'target': str(peer),
                    'type': relation,
                    'file': source_file,
                    'weight': confidence,
                })

    nodes = [{'id': n} for n in node_set]
    return nodes, pairwise


def sync_to_supabase():
    """Parse graph.json and write relationships to Supabase."""
    graph = load_graph()
    if not graph:
        return

    nodes, edges = _expand_hyperedges(graph)

    print(f"  Graph loaded: {len(nodes)} nodes, {len(edges)} pairwise edges")

    if not edges:
        print("  No edges to sync — check graph.json structure.")
        return

    # Clear existing relationships (full sync)
    sb.table('graph_relationships').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()

    # Insert edges in batches of 100
    batch = []
    for edge in edges:
        source = edge.get('source', edge.get('from', ''))
        target = edge.get('target', edge.get('to', ''))
        if not source or not target:
            continue

        # Normalise dict nodes (legacy format)
        if isinstance(source, dict):
            source = source.get('id', source.get('name', str(source)))
        if isinstance(target, dict):
            target = target.get('id', target.get('name', str(target)))

        batch.append({
            'source_entity': str(source),
            'target_entity': str(target),
            'relationship_type': edge.get('type', edge.get('label', 'related_to')),
            'weight': edge.get('weight', 1.0),
            'source_file': edge.get('file', ''),
            'metadata': {k: v for k, v in edge.items()
                         if k not in ('source', 'target', 'from', 'to', 'type', 'label', 'weight', 'file')},
        })

    for i in range(0, len(batch), 100):
        chunk = batch[i:i + 100]
        sb.table('graph_relationships').insert(chunk).execute()

    print(f"  Synced {len(batch)} relationships to Supabase")

    # Store well-connected node entries in thoughts for retrieval
    # Build connection map
    conn_map: dict[str, set[str]] = {}
    for e in edges:
        s = str(e.get('source', e.get('from', '')))
        t = str(e.get('target', e.get('to', '')))
        conn_map.setdefault(s, set()).add(t)
        conn_map.setdefault(t, set()).add(s)

    updated = 0
    for node in nodes:
        name = node.get('id', node.get('name', ''))
        if not name:
            continue

        connected_to = conn_map.get(str(name), set())
        if len(connected_to) < 2:
            continue

        entry = (
            f"GRAPH ENTITY: {name}\n"
            f"Connections ({len(connected_to)}): {', '.join(list(connected_to)[:20])}"
        )

        existing = (
            sb.table('thoughts')
            .select('id')
            .eq('agent', 'graphify-bridge')
            .ilike('content', f'%GRAPH ENTITY: {name}%')
            .limit(1)
            .execute()
        )

        if existing.data:
            sb.table('thoughts').update({
                'content': entry,
                'updated_at': datetime.utcnow().isoformat(),
            }).eq('id', existing.data[0]['id']).execute()
        else:
            sb.table('thoughts').insert({
                'content': entry,
                'source': 'system',
                'entry_type': 'reference',
                'agent': 'graphify-bridge',
                'tags': ['graph', 'entity', name.lower().replace(' ', '_')[:50]],
                'confidence': 0.9,
            }).execute()

        updated += 1

    print(f"  {updated} node entries updated in brain")


def run_reindex():
    """Full Graphify re-index, then sync."""
    print(f"  Running full Graphify re-index on {_VAULT_ALT}...")
    try:
        result = subprocess.run(
            ['graphify', _VAULT_ALT],
            capture_output=True, text=True, timeout=300,
            cwd=_VAULT_ALT,
        )
        print(f"  Graphify output: {result.stdout[:500]}")
        if result.returncode != 0:
            print(f"  Graphify errors: {result.stderr[:500]}")
    except FileNotFoundError:
        print("  graphify not found. Install: pip install graphify && graphify install")
        return
    except subprocess.TimeoutExpired:
        print("  Graphify timed out (>5min)")
        return

    sync_to_supabase()


def query_connections(entity: str):
    """Find everything connected to an entity."""
    as_source = (
        sb.table('graph_relationships')
        .select('target_entity, relationship_type, weight')
        .ilike('source_entity', f'%{entity}%')
        .execute()
    )

    as_target = (
        sb.table('graph_relationships')
        .select('source_entity, relationship_type, weight')
        .ilike('target_entity', f'%{entity}%')
        .execute()
    )

    connections = []
    for r in (as_source.data or []):
        connections.append(f"  -> {r['target_entity']} ({r['relationship_type']}, weight: {r['weight']})")
    for r in (as_target.data or []):
        connections.append(f"  <- {r['source_entity']} ({r['relationship_type']}, weight: {r['weight']})")

    if connections:
        print(f"\n  Connections for '{entity}':")
        for c in connections:
            print(c)
        print(f"\n  Total: {len(connections)} connections")
    else:
        print(f"\n  No connections found for '{entity}'")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python graphify_bridge.py sync     # Sync graph.json -> Supabase")
        print("  python graphify_bridge.py reindex   # Full re-index + sync")
        print('  python graphify_bridge.py query "entity"  # Find connections')
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'sync':
        sync_to_supabase()
    elif cmd == 'reindex':
        run_reindex()
    elif cmd == 'query' and len(sys.argv) > 2:
        query_connections(sys.argv[2])
