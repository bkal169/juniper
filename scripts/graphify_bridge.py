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


GRAPH_PATH = os.path.expanduser('~/jrih-vault/graphify-out/graph.json')
VAULT_PATH = os.path.expanduser('~/jrih-vault')


def load_graph() -> dict:
    """Load graph.json from Graphify output."""
    if not os.path.exists(GRAPH_PATH):
        print(f"  graph.json not found at {GRAPH_PATH}")
        print(f"  Run: /graphify {VAULT_PATH}")
        return {}

    with open(GRAPH_PATH, 'r') as f:
        return json.load(f)


def sync_to_supabase():
    """Parse graph.json and write relationships to Supabase."""
    graph = load_graph()
    if not graph:
        return

    nodes = graph.get('nodes', [])
    edges = graph.get('edges', graph.get('links', []))

    print(f"  Graph loaded: {len(nodes)} nodes, {len(edges)} edges")

    # Clear existing relationships (full sync)
    sb.table('graph_relationships').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()

    # Insert edges
    batch = []
    for edge in edges:
        source = edge.get('source', edge.get('from', ''))
        target = edge.get('target', edge.get('to', ''))
        if not source or not target:
            continue

        # Normalize entity names
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
            'metadata': {k: v for k, v in edge.items() if k not in ('source', 'target', 'from', 'to', 'type', 'label', 'weight', 'file')},
        })

    # Insert in batches of 100
    for i in range(0, len(batch), 100):
        chunk = batch[i:i+100]
        sb.table('graph_relationships').insert(chunk).execute()

    print(f"  Synced {len(batch)} relationships to Supabase")

    # Also store node data as searchable entries
    for node in nodes[:50]:  # Top 50 most connected
        name = node.get('id', node.get('name', ''))
        if not name:
            continue

        connections = [e for e in edges if str(e.get('source', e.get('from', ''))) == str(name) or str(e.get('target', e.get('to', ''))) == str(name)]

        if len(connections) >= 2:  # Only store well-connected nodes
            connected_to = set()
            for e in connections:
                s = str(e.get('source', e.get('from', '')))
                t = str(e.get('target', e.get('to', '')))
                if s != str(name):
                    connected_to.add(s)
                if t != str(name):
                    connected_to.add(t)

            entry = f"GRAPH ENTITY: {name}\nConnections ({len(connected_to)}): {', '.join(list(connected_to)[:20])}"

            # Upsert: check if exists
            existing = sb.table('thoughts') \
                .select('id') \
                .eq('agent', 'graphify-bridge') \
                .ilike('content', f'%GRAPH ENTITY: {name}%') \
                .limit(1) \
                .execute()

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
                    'tags': ['graph', 'entity', name.lower().replace(' ', '_')],
                    'confidence': 0.9,
                }).execute()

    print(f"  Node entries updated in brain")


def run_reindex():
    """Full Graphify re-index, then sync."""
    print(f"  Running full Graphify re-index on {VAULT_PATH}...")
    try:
        result = subprocess.run(
            ['graphify', VAULT_PATH],
            capture_output=True, text=True, timeout=300,
            cwd=VAULT_PATH,
        )
        print(f"  Graphify output: {result.stdout[:500]}")
        if result.returncode != 0:
            print(f"  Graphify errors: {result.stderr[:500]}")
    except FileNotFoundError:
        print("  graphify not found. Install: pip install graphifyy && graphify install")
        return
    except subprocess.TimeoutExpired:
        print("  Graphify timed out (>5min)")
        return

    sync_to_supabase()


def query_connections(entity: str):
    """Find everything connected to an entity."""
    # Search graph_relationships table
    as_source = sb.table('graph_relationships') \
        .select('target_entity, relationship_type, weight') \
        .ilike('source_entity', f'%{entity}%') \
        .execute()

    as_target = sb.table('graph_relationships') \
        .select('source_entity, relationship_type, weight') \
        .ilike('target_entity', f'%{entity}%') \
        .execute()

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
