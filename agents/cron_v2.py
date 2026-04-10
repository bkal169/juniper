"""
JRIH — Cron v2 Scheduler
8 jobs. Deploy to Railway.

Schedule:
  3:00 AM  — TTL cleanup (nightly)
  6:00 AM  — Morning brief (daily)
  7:00 AM  — Claude Advisor weekly brief (Monday only)
  10:00 AM — HOJ cycle (Mon/Wed/Fri)
  2:00 PM  — Competitive Intel scan (Wednesday only)
  11:00 PM — Weekly digest (Sunday only)
  2:00 AM  — Junior learning loop (Saturday only)
  2:30 AM  — Graphify re-index (Saturday only)

Usage:
  python cron_v2.py           # start scheduler
  python cron_v2.py brief     # manual morning brief
  python cron_v2.py digest    # manual weekly digest
  python cron_v2.py intel     # manual intel scan
  python cron_v2.py hoj       # manual HOJ cycle
  python cron_v2.py advisor   # manual advisor brief
  python cron_v2.py learn     # manual Junior learning
"""

import sys
import time
import subprocess
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import sb


# ═══════════════════════════════════════════════════════════
# JOB DEFINITIONS
# ═══════════════════════════════════════════════════════════

def job_ttl_cleanup():
    """3am: Clean expired thoughts."""
    try:
        result = sb.rpc('cleanup_expired_thoughts').execute()
        deleted = result.data if result.data else 0
        print(f"[{datetime.utcnow().strftime('%H:%M')}] TTL cleanup: {deleted} expired entries removed")
    except Exception as e:
        print(f"[TTL cleanup] Error: {e}")


def job_morning_brief():
    """6am: Generate morning brief."""
    try:
        from juniper import generate_brief
        brief = generate_brief()
        print(f"[{datetime.utcnow().strftime('%H:%M')}] Morning brief generated ({len(brief)} chars)")
    except Exception as e:
        print(f"[Morning brief] Error: {e}")


def job_advisor_weekly():
    """Monday 7am: Claude Advisor weekly strategic brief."""
    try:
        from specialized_agents import advisor_weekly_brief
        advisor_weekly_brief()
        print(f"[{datetime.utcnow().strftime('%H:%M')}] Advisor weekly brief generated")
    except Exception as e:
        print(f"[Advisor brief] Error: {e}")


def job_hoj_cycle():
    """Mon/Wed/Fri 10am: HOJ dedicated cycle."""
    try:
        from specialized_agents import run_hoj_cycle
        run_hoj_cycle()
        print(f"[{datetime.utcnow().strftime('%H:%M')}] HOJ cycle complete")
    except Exception as e:
        print(f"[HOJ cycle] Error: {e}")


def job_intel_scan():
    """Wednesday 2pm: Competitive intel scan."""
    try:
        from specialized_agents import run_intel_scan
        run_intel_scan()
        print(f"[{datetime.utcnow().strftime('%H:%M')}] Intel scan complete")
    except Exception as e:
        print(f"[Intel scan] Error: {e}")


def job_weekly_digest():
    """Sunday 11pm: Weekly synthesis digest."""
    try:
        from langgraph_agents import synthesis_graph
        now = datetime.utcnow()
        week_label = f"{now.year}-W{now.isocalendar()[1]:02d}"
        result = synthesis_graph.invoke({
            'period': week_label,
            'thoughts': [],
            'digest': '',
            'status': '',
        })
        print(f"[{datetime.utcnow().strftime('%H:%M')}] Weekly digest generated: {week_label}")
    except Exception as e:
        print(f"[Weekly digest] Error: {e}")


def job_junior_learning():
    """Saturday 2am: Junior self-improvement loop."""
    try:
        from junior import run_learning_loop
        rules = run_learning_loop()
        print(f"[{datetime.utcnow().strftime('%H:%M')}] Junior learning: {len(rules or [])} new rules")
    except Exception as e:
        print(f"[Junior learning] Error: {e}")


def job_graphify_reindex():
    """Saturday 2:30am: Full Graphify re-index."""
    try:
        result = subprocess.run(
            ['python', 'scripts/graphify_bridge.py', 'reindex'],
            capture_output=True, text=True, timeout=300,
        )
        print(f"[{datetime.utcnow().strftime('%H:%M')}] Graphify re-index: {result.stdout[:200]}")
    except Exception as e:
        print(f"[Graphify] Error: {e}")


# ═══════════════════════════════════════════════════════════
# HITL ESCALATION CHECK (runs with morning brief)
# ═══════════════════════════════════════════════════════════

def check_hitl_escalation():
    """Check for items older than 48hrs. Escalate."""
    try:
        overdue = sb.table('hitl_queue') \
            .select('id, title, item_type, created_at') \
            .eq('status', 'pending') \
            .is_('escalated_at', 'null') \
            .execute()

        for item in (overdue.data or []):
            created = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
            age_hours = (datetime.utcnow().replace(tzinfo=created.tzinfo) - created).total_seconds() / 3600

            if age_hours > 48:
                sb.table('hitl_queue').update({
                    'escalated_at': datetime.utcnow().isoformat(),
                }).eq('id', item['id']).execute()
                print(f"  ESCALATION: HITL item '{item['title'][:50]}' is {age_hours:.0f}h old")

    except Exception as e:
        print(f"[HITL escalation] Error: {e}")


# ═══════════════════════════════════════════════════════════
# SCHEDULER
# ═══════════════════════════════════════════════════════════

def start_scheduler():
    scheduler = BlockingScheduler(timezone='US/Eastern')

    # Nightly TTL cleanup — 3:00 AM daily
    scheduler.add_job(job_ttl_cleanup, CronTrigger(hour=3, minute=0))

    # Morning brief — 6:00 AM daily
    scheduler.add_job(job_morning_brief, CronTrigger(hour=6, minute=0))

    # HITL escalation check — 6:05 AM daily
    scheduler.add_job(check_hitl_escalation, CronTrigger(hour=6, minute=5))

    # Claude Advisor — Monday 7:00 AM
    scheduler.add_job(job_advisor_weekly, CronTrigger(day_of_week='mon', hour=7, minute=0))

    # HOJ cycle — Mon/Wed/Fri 10:00 AM
    scheduler.add_job(job_hoj_cycle, CronTrigger(day_of_week='mon,wed,fri', hour=10, minute=0))

    # Competitive Intel — Wednesday 2:00 PM
    scheduler.add_job(job_intel_scan, CronTrigger(day_of_week='wed', hour=14, minute=0))

    # Weekly digest — Sunday 11:00 PM
    scheduler.add_job(job_weekly_digest, CronTrigger(day_of_week='sun', hour=23, minute=0))

    # Junior learning — Saturday 2:00 AM
    scheduler.add_job(job_junior_learning, CronTrigger(day_of_week='sat', hour=2, minute=0))

    # Graphify re-index — Saturday 2:30 AM
    scheduler.add_job(job_graphify_reindex, CronTrigger(day_of_week='sat', hour=2, minute=30))

    print(f"\n{'='*60}")
    print(f"JRIH CRON v2 — 9 scheduled jobs")
    print(f"{'='*60}")
    print(f"  3:00 AM daily      — TTL cleanup")
    print(f"  6:00 AM daily      — Morning brief")
    print(f"  6:05 AM daily      — HITL escalation check")
    print(f"  7:00 AM Monday     — Claude Advisor weekly")
    print(f"  10:00 AM Mon/W/F   — HOJ cycle")
    print(f"  2:00 PM Wednesday  — Competitive Intel scan")
    print(f"  11:00 PM Sunday    — Weekly digest")
    print(f"  2:00 AM Saturday   — Junior learning loop")
    print(f"  2:30 AM Saturday   — Graphify re-index")
    print(f"{'='*60}")
    print(f"  Started: {datetime.utcnow().isoformat()}")
    print(f"  Timezone: US/Eastern\n")

    scheduler.start()


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        jobs = {
            'brief': job_morning_brief,
            'digest': job_weekly_digest,
            'intel': job_intel_scan,
            'hoj': job_hoj_cycle,
            'advisor': job_advisor_weekly,
            'learn': job_junior_learning,
            'cleanup': job_ttl_cleanup,
            'graphify': job_graphify_reindex,
            'escalate': check_hitl_escalation,
        }
        if cmd in jobs:
            jobs[cmd]()
        else:
            print(f"Unknown command: {cmd}")
            print(f"Available: {', '.join(jobs.keys())}")
    else:
        start_scheduler()
