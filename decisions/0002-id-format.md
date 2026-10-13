# ADR 0002 — Entity ID format: UUIDv4

**Status:** accepted
**Date:** 2026-08-25
**Module:** 02 — Data Contracts & Conventions

## Context

Every domain entity (`Farmer`, `Field`, `WeatherReading`, …) needs an ID
that is stable, globally unique, and portable across the SQLite-dev and
Supabase-prod backends locked by CLAUDE.md rule #3. Candidates:

- **Integer autoincrement.** Cheap in a single DB, but sequences behave
  differently across SQLite and Postgres, and IDs are guessable — a
  farmer's IDs would leak record counts. Also fragile once a second
  writer (a batch job, an offline client) enters the picture.
- **UUIDv4.** Random 128-bit id, no coordinator needed, unambiguous
  across DBs (SQLite TEXT, Postgres `uuid`). Easy to generate on the
  device before a round-trip to the server.
- **ULID / UUIDv7.** Sortable, but requires a monotonic clock story and
  is a newer standard; benefits (index locality) are irrelevant at this
  project's scale.

## Decision

All entity IDs are **UUIDv4 strings**, rendered in the standard
lowercase 8-4-4-4-12 hyphenated form. Encoded as TEXT in SQLite and
`uuid` in Postgres by the Module 04 repository layer.

## Consequences

- Clients (including the mobile / offline PWA in Module 14) may mint IDs
  before contacting the server, which simplifies offline advisory
  submission.
- Slight index-locality cost in Postgres vs a monotonic ID; acceptable
  at this scale.
- IDs are opaque to clients; nothing may parse meaning out of them.
- `tools/check_specs.py` enforces the UUIDv4 shape on every fixture id.
