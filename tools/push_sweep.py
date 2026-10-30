#!/usr/bin/env python3
"""Periodic Android push sweep (Module 59) -- the thing that makes push
notifications actually *proactive* rather than a copy of the in-app
screen. The disease-scan push (value_endpoints.py's compute_disease_risk_
image) only fires at the moment a farmer scans a leaf; this script is
what notifies a farmer who hasn't opened the app at all, by running the
same cheap, in-process irrigation-urgency model the app itself uses and
pushing when it comes back "high" -- exactly the kind of weather-driven
change a closed app would otherwise never surface.

Intentionally scoped to irrigation only, not disease risk or crop
recommendation: both of those need either a fresh photo (disease) or
are a once-in-a-season decision (crop), neither of which make sense to
poll unprompted. Irrigation urgency genuinely drifts day to day with
weather, which is exactly the "find out even with the app closed" case
push exists for.

Deduplicated against the field's own saved irrigation-advice history
(no new table needed): skips the push if a high-urgency advice for the
same field was already saved within `_DEDUP_WINDOW`, so a multi-day dry
spell doesn't push every single run.

Run by .github/workflows/push_sweep.yml on the same cron infrastructure
that already keeps the Render free tier awake (see keep_alive.yml) --
every few hours, not every 12 minutes: irrigation urgency does not
change meaningfully faster than that, and it saves a trained-model
prediction per field per run across every registered farmer.

Usage:
    python tools/push_sweep.py --backend sqlite --db-path agro_mirai.db
    python tools/push_sweep.py --backend supabase   # needs SUPABASE_URL/KEY, used in production
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("push_sweep")

_DEDUP_WINDOW = timedelta(hours=20)


def build_store(backend: str, db_path: str | None):
    if backend == "sqlite":
        from agro_mirai.persistence.sqlite_store import SQLiteDataStore

        return SQLiteDataStore(db_path or "agro_mirai.db")
    if backend == "supabase":
        from agro_mirai.persistence.supabase_store import SupabaseDataStore

        return SupabaseDataStore()
    raise ValueError(f"unknown backend: {backend!r}")


def sweep(store) -> int:
    from agro_mirai.api import value_endpoints
    from agro_mirai.api.errors import ApiError
    from agro_mirai.api.push_client import send_push_to_farmer
    from agro_mirai.models.irrigation_prediction_model import IrrigationPredictionModel

    ext = {"irrigation_model": IrrigationPredictionModel()}
    pushed = 0

    farmer_ids = store.list_farmer_ids_with_push_tokens()
    logger.info("farmers with a registered device: %d", len(farmer_ids))

    for farmer_id in farmer_ids:
        try:
            fields = store.list_fields(farmer_id)
        except Exception as exc:  # one farmer's bad data must never stop the sweep
            logger.warning("farmer=%s: could not list fields: %s", farmer_id, exc)
            continue

        for field in fields:
            try:
                previous = store.get_latest_irrigation_advice(farmer_id, field.id)
                already_notified_recently = (
                    previous is not None
                    and previous.urgency == "high"
                    and datetime.now(timezone.utc) - previous.created_at < _DEDUP_WINDOW
                )

                advice = value_endpoints.compute_irrigation(store, ext, farmer_id, field.id)
            except ApiError as exc:
                # 422 (missing weather/soil data for this field) is routine, not a bug
                logger.info("field=%s: skipped (%s)", field.id, exc.code if hasattr(exc, "code") else exc)
                continue
            except Exception as exc:
                logger.warning("field=%s: unexpected error: %s", field.id, exc)
                continue

            if advice.get("urgency") != "high" or already_notified_recently:
                continue

            mm = advice.get("recommended_depth_mm")
            title = f"\U0001f4a7 Irrigation needed — {field.name}"
            body = f"{round(mm, 1)} mm recommended today. Tap for details." if mm else "Your field needs water today. Tap for details."
            sent = send_push_to_farmer(
                store, farmer_id, title, body,
                data={"accountId": farmer_id, "fieldId": field.id, "screen": "home"},
            )
            if sent:
                pushed += 1
                logger.info("field=%s: pushed to %d device(s)", field.id, sent)

    return pushed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["sqlite", "supabase"], default="sqlite")
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args(argv)

    store = build_store(args.backend, args.db_path)
    pushed = sweep(store)
    logger.info("done: %d field(s) pushed", pushed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
