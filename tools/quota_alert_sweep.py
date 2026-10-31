#!/usr/bin/env python3
"""Checks every OpenRouter/Groq key pool's real remaining free-tier quota
(api/quota_monitor.py) and emails the admin (api/email_alerts.py) once any
pool drops below `_THRESHOLD_PCT` remaining. Run by
.github/workflows/quota_alert_sweep.yml on the same cron infrastructure
that already keeps Render awake and runs the push sweep.

At most one email per pool per calendar day (UTC), tracked via the
`quota_alerts_sent` table -- so a pool sitting below the threshold all
day doesn't spam an email every run.

Usage:
    python tools/quota_alert_sweep.py --backend sqlite --db-path agro_mirai.db
    python tools/quota_alert_sweep.py --backend supabase   # used in production
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("quota_alert_sweep")

_THRESHOLD_PCT = 20.0


def build_store(backend: str, db_path: str | None):
    if backend == "sqlite":
        from agro_mirai.persistence.sqlite_store import SQLiteDataStore

        return SQLiteDataStore(db_path or "agro_mirai.db")
    if backend == "supabase":
        from agro_mirai.persistence.supabase_store import SupabaseDataStore

        return SupabaseDataStore()
    raise ValueError(f"unknown backend: {backend!r}")


def _format_report(pool: dict) -> str:
    lines = [f"{pool['label']}: {pool['total_remaining']}/{pool['total_limit']} remaining ({pool['pct_remaining']}%)", ""]
    for k in pool["keys"]:
        lines.append(f"  - {k['provider']} ...{k['suffix']}: {k['remaining']}/{k['limit']} remaining")
    return "\n".join(lines)


def sweep(store) -> int:
    from agro_mirai.api.email_alerts import send_alert_email
    from agro_mirai.api.quota_monitor import check_all_pools

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pools = check_all_pools()
    alerted = 0

    low_pools = [p for p in pools.values() if p["pct_remaining"] is not None and p["pct_remaining"] <= _THRESHOLD_PCT]
    logger.info("checked %d pools, %d below %s%% remaining", len(pools), len(low_pools), _THRESHOLD_PCT)

    for pool in low_pools:
        if store.has_quota_alert_sent_today(pool["pool"], today):
            logger.info("%s: already alerted today, skipping", pool["pool"])
            continue

        subject = f"AGRO MIRAI: {pool['label']} API quota low ({pool['pct_remaining']}% remaining)"
        body = (
            f"One of this project's API key pools is running low on today's free-tier quota.\n\n"
            f"{_format_report(pool)}\n\n"
            f"This resets at each key's own 24h cycle. No action needed unless it actually "
            f"hits 0 -- the app falls back to the next key/provider automatically either way.\n"
        )
        sent = send_alert_email(subject, body)
        if sent:
            store.mark_quota_alert_sent(pool["pool"], today, datetime.now(timezone.utc))
            alerted += 1
            logger.info("%s: alert email sent", pool["pool"])
        else:
            logger.warning("%s: alert email failed to send (will retry next run)", pool["pool"])

    return alerted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["sqlite", "supabase"], default="sqlite")
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args(argv)

    store = build_store(args.backend, args.db_path)
    alerted = sweep(store)
    logger.info("done: %d alert(s) sent", alerted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
