"""
JRIH — Juniper Heartbeat Monitor
Runs as a Railway cron job every 15 minutes.

Checks agent_action_log for Juniper's last cycle.
Sends Resend alert to bkalan169@gmail.com if silent > 4 hours.

Required env vars:
  SUPABASE_URL          — must point to Brain DB (obtoinsjncbqdqgdeddl)
  SUPABASE_SERVICE_KEY  — service-role key for Brain DB
  RESEND_API_KEY        — Resend API key (add in Railway service env vars)
  ALERT_EMAIL           — override recipient (default: bkalan169@gmail.com)
  HEARTBEAT_SILENCE_HOURS — silence threshold in hours (default: 4)
"""

import os
import sys
import json
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError

# ─────────────────────────────────────────────
# CONFIG  (stdlib only — no heavy config.py)
# ─────────────────────────────────────────────

SUPABASE_URL   = os.environ.get("SUPABASE_URL", "").rstrip("/")
# Accept either naming convention (Railway uses ROLE_KEY, local .env uses SERVICE_KEY)
SUPABASE_KEY   = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
ALERT_EMAIL    = os.environ.get("ALERT_EMAIL", "bkalan169@gmail.com")
SILENCE_HOURS  = int(os.environ.get("HEARTBEAT_SILENCE_HOURS", "4"))

assert SUPABASE_URL, "SUPABASE_URL is required"
assert SUPABASE_KEY, "SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY) is required"
# Phase 13.3: dropped legacy-DB hardcoded assertion. The Brain DB migrated from
# obtoinsjncbqdqgdeddl (legacy/paused) to zqrgazuaideuumksijhe (active) on
# 2026-04-28 and this assertion was preventing the heartbeat from being repointed.
# Soft-warn instead of hard-fail so misconfig is visible but not crash-loop.
if "supabase.co" not in SUPABASE_URL:
    print(f"[heartbeat] WARNING: SUPABASE_URL doesn't look like a Supabase host: {SUPABASE_URL}", flush=True)


# ─────────────────────────────────────────────
# SUPABASE QUERY
# ─────────────────────────────────────────────

def get_last_juniper_action() -> dict | None:
    """
    Query agent_action_log for the most recent Juniper entry.
    Returns the row dict or None if no rows found.
    """
    url = (
        f"{SUPABASE_URL}/rest/v1/agent_action_log"
        f"?agent_id=eq.juniper"
        f"&order=created_at.desc"
        f"&limit=1"
        f"&select=id,agent_id,action_type,created_at"
    )
    req = Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    })
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data[0] if data else None
    except Exception as e:
        print(f"[heartbeat] Supabase query error: {e}", flush=True)
        return None


# ─────────────────────────────────────────────
# RESEND ALERT
# ─────────────────────────────────────────────

def send_alert(last_ts: str | None, silence_hours: float) -> bool:
    """Send alert email via Resend API."""
    if not RESEND_API_KEY:
        print("[heartbeat] RESEND_API_KEY not set — skipping email alert", flush=True)
        return False

    if last_ts:
        last_str = f"Last seen: {last_ts} UTC"
        details = (
            f"Juniper has been silent for <strong>{silence_hours:.1f} hours</strong> "
            f"(threshold: {SILENCE_HOURS}h)."
        )
    else:
        last_str = "No entries found in agent_action_log"
        details = "Juniper has <strong>never</strong> written to agent_action_log, or the table is empty."

    payload = {
        # 2026-05-02 parity fix: Vercel TS heartbeat (src/app/api/cron/heartbeat/route.ts)
        # was switched to onboarding@resend.dev today after alerts.jrih.dev domain
        # was found unverified on Resend. Mirroring the same change here so this
        # standalone-Railway-cron alternative path doesn't 403 if reactivated.
        # To restore branded sender: verify alerts.jrih.dev DNS in Resend dashboard.
        "from": "Juniper Monitor <onboarding@resend.dev>",
        "to": [ALERT_EMAIL],
        "subject": f"🚨 Juniper SILENT — {silence_hours:.1f}h with no activity",
        "html": f"""
<h2 style="color:#c00">⚠️ Juniper Heartbeat Alert</h2>
<p>{details}</p>
<p><strong>{last_str}</strong></p>
<p>
  <a href="https://railway.app/project/f922ba92-c4d2-4688-9cf3-cd0c908dfc28"
     style="color:#0066cc">View Railway logs → jrih-second-brain</a>
</p>
<hr>
<small>Sent by <code>agents/heartbeat.py</code> cron — Railway project jrih-second-brain</small>
""",
    }

    req = Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            print(f"[heartbeat] Alert sent. Resend ID: {result.get('id')}", flush=True)
            return True
    except URLError as e:
        print(f"[heartbeat] Resend error: {e}", flush=True)
        return False


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    now = datetime.now(timezone.utc)
    print(f"[heartbeat] Check at {now.isoformat()}", flush=True)

    row = get_last_juniper_action()

    if row is None:
        print("[heartbeat] No Juniper activity found in agent_action_log — alerting.", flush=True)
        send_alert(None, 9999.0)
        sys.exit(1)

    last_ts_str = row["created_at"]

    # Parse ISO timestamp (Supabase: "2026-04-23T10:15:00.123456+00:00" or "...Z")
    try:
        last_ts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
    except ValueError:
        last_ts = datetime.fromisoformat(last_ts_str[:19]).replace(tzinfo=timezone.utc)

    silence = now - last_ts
    silence_hours = silence.total_seconds() / 3600

    print(
        f"[heartbeat] Last Juniper action: {last_ts_str} "
        f"({silence_hours:.2f}h ago, action_type={row.get('action_type')})",
        flush=True,
    )

    if silence > timedelta(hours=SILENCE_HOURS):
        print(f"[heartbeat] ALERT — silent > {SILENCE_HOURS}h. Firing alert.", flush=True)
        send_alert(last_ts_str, silence_hours)
        sys.exit(1)   # non-zero exit → Railway marks the cron run red in the dashboard
    else:
        print(f"[heartbeat] OK — Juniper alive. Last seen {silence_hours:.2f}h ago.", flush=True)
        sys.exit(0)


if __name__ == "__main__":
    main()
