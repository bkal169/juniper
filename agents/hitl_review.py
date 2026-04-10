"""
JRIH — HITL Review CLI
Alan reviews queue each morning. Approve/reject/defer.

Usage:
  python hitl_review.py               # show pending items
  python hitl_review.py approve <id>  # approve item
  python hitl_review.py reject <id> "reason"
  python hitl_review.py defer <id>
  python hitl_review.py stats
"""

import sys
import json
from datetime import datetime

from config import sb


def show_queue():
    """Show all pending HITL items, ordered by priority."""
    result = sb.rpc('get_pending_hitl', {'max_items': 20}).execute()
    items = result.data or []

    if not items:
        print("\n  HITL queue is empty. All clear.\n")
        return

    print(f"\n{'='*70}")
    print(f"  HITL QUEUE — {len(items)} pending items")
    print(f"{'='*70}\n")

    for i, item in enumerate(items, 1):
        age = item.get('age_hours', 0)
        urgent = ' ** OVERDUE **' if age > 48 else (' * >24h *' if age > 24 else '')
        print(f"  [{i}] {item['item_type'].upper()}{urgent}")
        print(f"      ID:         {item['id']}")
        print(f"      Title:      {item['title'][:80]}")
        print(f"      Division:   {item.get('division', 'unknown')}")
        print(f"      Confidence: {item.get('confidence', 'N/A')}")
        print(f"      Age:        {age:.1f} hours")
        print(f"      Created:    {item['created_at']}")
        if item.get('context'):
            ctx = item['context'][:200]
            print(f"      Context:    {ctx}")
        print()

    print(f"{'='*70}")
    print(f"  Commands: approve <id> | reject <id> 'reason' | defer <id>")
    print(f"{'='*70}\n")


def approve_item(item_id: str):
    """Approve a HITL item."""
    sb.table('hitl_queue').update({
        'status': 'approved',
        'resolution': 'Approved by Alan',
        'resolved_at': datetime.utcnow().isoformat(),
        'resolved_by': 'alan',
    }).eq('id', item_id).execute()
    print(f"  Approved: {item_id}")


def reject_item(item_id: str, reason: str = 'Rejected by Alan'):
    """Reject a HITL item."""
    sb.table('hitl_queue').update({
        'status': 'rejected',
        'resolution': reason,
        'resolved_at': datetime.utcnow().isoformat(),
        'resolved_by': 'alan',
    }).eq('id', item_id).execute()
    print(f"  Rejected: {item_id} — {reason}")


def defer_item(item_id: str):
    """Defer a HITL item (resets 48hr clock)."""
    sb.table('hitl_queue').update({
        'status': 'pending',  # stays pending
        'created_at': datetime.utcnow().isoformat(),  # reset clock
        'escalated_at': None,
    }).eq('id', item_id).execute()
    print(f"  Deferred: {item_id} — 48hr clock reset")


def show_stats():
    """Show HITL stats."""
    all_items = sb.table('hitl_queue') \
        .select('status, item_type, created_at, resolved_at') \
        .execute()
    items = all_items.data or []

    total = len(items)
    pending = sum(1 for i in items if i['status'] == 'pending')
    approved = sum(1 for i in items if i['status'] == 'approved')
    rejected = sum(1 for i in items if i['status'] == 'rejected')
    deferred = sum(1 for i in items if i['status'] == 'deferred')

    # Type breakdown
    types = {}
    for i in items:
        t = i['item_type']
        types[t] = types.get(t, 0) + 1

    print(f"\n{'='*50}")
    print(f"  HITL STATS")
    print(f"{'='*50}")
    print(f"  Total:    {total}")
    print(f"  Pending:  {pending}")
    print(f"  Approved: {approved}")
    print(f"  Rejected: {rejected}")
    print(f"  Deferred: {deferred}")
    print(f"\n  By type:")
    for t, c in sorted(types.items()):
        print(f"    {t}: {c}")
    print(f"{'='*50}\n")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        show_queue()
    else:
        cmd = sys.argv[1]
        if cmd == 'approve' and len(sys.argv) > 2:
            approve_item(sys.argv[2])
        elif cmd == 'reject' and len(sys.argv) > 2:
            reason = sys.argv[3] if len(sys.argv) > 3 else 'Rejected by Alan'
            reject_item(sys.argv[2], reason)
        elif cmd == 'defer' and len(sys.argv) > 2:
            defer_item(sys.argv[2])
        elif cmd == 'stats':
            show_stats()
        else:
            print("Usage: python hitl_review.py [approve|reject|defer <id>|stats]")
