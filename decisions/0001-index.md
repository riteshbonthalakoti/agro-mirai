# ADR Index

One entry per architectural decision record.

- `0002-id-format.md` — Entity IDs are UUIDv4 strings.
- `0003-single-farmer-tenancy.md` — One `Farmer` per user account; no
  multi-tenant sharing in `v1`.
- `0004-gee-timeout-and-fallback.md` — Earth Engine call timeout, cloud
  cover ceiling, lookback window, and buffer radius for the NDVI
  live/cache fallback.
- `0005-migration-generation.md` — SQLite/Postgres migrations are
  generated from `schema.yaml`, not hand-written.
- `0006-missing-data-policy.md` — Weather is required (hard error if
  absent); soil and NDVI are optional with explicit `*_data_available`
  flags and `None`-propagation, never a silent `0.0`.
