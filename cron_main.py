"""Top-level cron entrypoint.

Railway/nixpacks was auto-detecting agents/juniper.py as the start command,
silently ignoring per-service startCommand overrides. Putting this wrapper at
the repo root gives nixpacks a clear, unambiguous module to point startCommand
at: `python cron_main.py`.
"""
import sys
import os

# Make agents/ importable (this file lives at repo root)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents"))

from cron_v2 import start_scheduler  # noqa: E402

if __name__ == "__main__":
    start_scheduler()
