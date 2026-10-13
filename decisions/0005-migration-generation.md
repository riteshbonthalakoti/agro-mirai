# ADR 0005 — Generate SQLite/Postgres migrations from schema.yaml

**Status:** accepted
**Date:** 2026-08-25
**Module:** 04 — Storage Layer

## Context

Module 04 needs DDL for both backends locked by CLAUDE.md rule #3
(SQLite dev, Supabase Postgres prod) for all 10 entities in
`specs/core/schema.yaml` (~90 fields total). Two ways to produce it:

- **Hand-write both dialects**, verifying field-by-field against
  `schema.yaml`. Works, but every future additive change (CLAUDE.md
  rule #2 — schema changes are additive-only, expected to keep
  happening as modules 05-15 land) has to be applied twice by hand, and
  nothing catches a missed field or a type mismatch between the two
  dialects until a runtime error surfaces it.
- **Generate both dialects from schema.yaml.** The schema is already
  structured, machine-readable YAML — the same document
  `tools/check_specs.py` parses to validate the golden fixture. A small
  generator (`tools/gen_migrations.py`) walks `entities` once and emits
  both `CREATE TABLE` sets from one type-mapping table, so a field added
  to `schema.yaml` regenerates both dialects in one command and can't
  drift between them.

## Decision

Migrations are **generated**, not hand-written.
`tools/gen_migrations.py` reads `specs/core/schema.yaml` and writes
`migrations/sqlite/001_init.sql` and `migrations/postgres/001_init.sql`
deterministically (table/column order follows schema.yaml's entity/field
order). The output is checked into git like any other migration file —
generation is a build step run by the developer, not something that
happens at deploy time.

Type mapping: `uuid`→TEXT/uuid, `timestamp`→TEXT/timestamptz,
`date`→TEXT/date, `string`→TEXT/text, `int`→INTEGER/integer,
`float`→REAL/double precision, `bool`→INTEGER/boolean,
`list`→TEXT(JSON)/jsonb. `ref` fields become foreign keys with
`ON DELETE CASCADE` (matches `delete_field`'s documented cascade
behaviour in `repository-interface.md`).

## Consequences

- A schema.yaml change (additive field, new entity) is one command
  (`python tools/gen_migrations.py`) away from a correct, matching pair
  of DDL files — no manual dialect-sync step to forget.
- Migration files are still reviewed and committed like hand-written
  ones; regeneration is a deliberate, visible diff, not a hidden
  runtime translation layer.
- The generator only handles the mechanical, additive-safe case (new
  table, new nullable/required column, new FK). A genuinely breaking
  change (rename, drop) is out of scope for `v1` per CLAUDE.md rule #2
  and would need a new schema version and a hand-reviewed migration
  regardless.
- SQLite has no native `boolean`/`jsonb`; those fields round-trip
  through the store layer (`sqlite_store.py`), not the DDL, which is why
  `is_forecast`/`helpful` are `INTEGER` and `alternatives`/`source_refs`
  are `TEXT` (JSON-encoded) in the SQLite dialect only.
