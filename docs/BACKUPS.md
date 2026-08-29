# Supabase backups

`tools/backup_supabase.py` exports every core table (see `TABLES` in that
file — `farmers`, `fields`, `weather_readings`, `soil_samples`,
`ndvi_readings`, `crop_recommendations`, `irrigation_advices`,
`disease_risk_alerts`, `advisories`, `feedback_entries`) to one
timestamped local JSON file.

## Running it

```bash
SUPABASE_URL=https://<project-ref>.supabase.co SUPABASE_KEY=<key> \
  python tools/backup_supabase.py --out-dir backups
```

Uses the same `SUPABASE_URL`/`SUPABASE_KEY` env vars as `SupabaseDataStore`
— point it at the deployed instance's own credentials to back up its
actual data (get them from the Render dashboard's env vars, or
`supabase projects list` / the Supabase dashboard for the project URL and
service-role key). Writes `backups/agro_mirai_backup_<UTC-timestamp>.json`.
`backups/` is gitignored — a backup file is data, not something to commit.

## How often

**Manual only — there is no scheduled/automated backup.** Render's free
tier doesn't give this project an easy cron mechanism, and standing one
up (a separate scheduler service, a third-party cron-to-webhook, etc.) is
out of scope for this module. Run it by hand:

- Before any schema migration (`migrations/postgres/*.sql`).
- Before any bulk data operation (re-seeding, a Module 17 multi-tenant
  migration).
- Periodically during active demo/grading windows, since that's when the
  data is most valuable and most likely to be touched.

If this becomes a recurring pain, the fix is a real scheduled job (Render
paid cron, GitHub Actions on a `schedule:` trigger, or similar) calling
this same script — not a bigger ad-hoc script.

## Restoring

There is no automated restore path. A backup JSON file is one dict of
`{table_name: [rows]}`; restoring means re-inserting those rows via the
Supabase client or `psql`, table by table, in an order that respects
foreign keys (`farmers` → `fields` → everything else). This has not been
exercised end-to-end — treat it as a starting point, not a tested
runbook, until it has been.
