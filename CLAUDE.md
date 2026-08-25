# AGRO MIRAI

AI-driven smart agriculture advisory system — VTU Sem 7 capstone, BITM Dept. of AIML.

## Hard rules [LOCKED]

1. **CLI-first, always.** Before touching any external service (GitHub,
   Supabase, Render, Google Cloud/Earth Engine, Hugging Face, Kaggle), use
   its official CLI. Never hand-describe a dashboard click-path when a CLI
   command does the same thing.
2. **Additive-only data contracts.** Once a schema/contract is published in
   `specs/`, changes are additive (new optional fields, new endpoints) —
   never breaking renames or removals without a new versioned contract.
3. **SQLite-dev / Supabase-prod via a repository interface.** No module
   talks to a database engine directly. All persistence goes through a
   repository abstraction so the same code runs against local SQLite in dev
   and Supabase Postgres in prod.
4. **GEE-live-with-NDVI-cache fallback.** Google Earth Engine is the live
   source for satellite/NDVI data; every GEE-dependent module must degrade
   to a local NDVI cache when GEE is unavailable, not fail outright.
5. **Module N+1 never starts before module N is tested and committed.**
   Strict dependency gating — no skipping ahead.

## Nothing is hand-faked

If a step needs human auth (browser OAuth, API key), STOP, print the exact
command and what it will ask for, wait for the human. Never simulate
success.

## Repo map

```
agro-mirai/
  CLAUDE.md              # this file — doctrine, hard rules, current phase
  PROGRESS.md            # session handoff log, regenerated state block
  docs/
    TOOLING.md             # verified CLI versions + auth status
    architecture.md        # system architecture (from Module 02)
  specs/
    core/                  # cross-cutting contracts (from Module 02):
                            #   schema.yaml, enums.md, openapi.yaml,
                            #   repository-interface.md
    domains/               # per-domain contracts + golden fixtures
  decisions/
    0001-index.md           # ADR index
    NNNN-<slug>.md           # individual ADRs
  modules/
    01-foundation/           # this module's notes + tests
    ...                      # one dir per module, each with a STATUS file
  tools/
    update_state.py          # regenerates PROGRESS.md's state block
  tests/
```

Each `modules/NN-<name>/` directory carries a `STATUS` file
(`not-started` / `in-progress` / `done`) that `tools/update_state.py` reads
to build the phase table in `PROGRESS.md`.

## Current phase

**Module 04 blocked on a human step — otherwise complete.** The storage
layer (`src/agro_mirai/persistence/`) implements
`specs/core/repository-interface.md` in full: domain dataclasses,
generated SQLite+Postgres DDL (`tools/gen_migrations.py`,
`migrations/`), `SQLiteDataStore` (tested, green), and
`SupabaseDataStore` (code complete against the same migrations, not yet
exercised against a live project). The parity suite
(`tests/persistence/contract/`) runs identical assertions against both
backends — SQLite always, Supabase skipping cleanly without credentials
— and `tools/seed_fixture.py` round-trips the golden fixture on SQLite.
Blocked on: no Supabase project exists yet for AGRO MIRAI (see
`modules/04-storage/STATUS` for the exact `supabase projects create` /
`link` / `db push` commands a human needs to run). Module 05 (Processing
& Feature Engineering) can start once that's unblocked. See
`PROGRESS.md` for the full 15-module plan and status.
