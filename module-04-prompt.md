# MODULE 04 — Storage Layer

Continuing the AGRO MIRAI build in the existing `agro-mirai` repo. Modules
01–03 are done and committed. Read `CLAUDE.md` and `PROGRESS.md` first —
that's your complete required context.

This module implements the `DataStore` repository interface specified in
`specs/core/repository-interface.md` (written in Module 02, not yet
implemented) against **two** backends: SQLite for local dev, Supabase
Postgres for the deployed demo. Locked decision #3 — no module talks to a
database engine directly — gets proven here, not just declared: the same
test suite must pass against both backends through the same interface.

## Before any code: git identity + commit discipline

1. Confirm `git config user.name` / `user.email` in this repo resolve to
   the actual GitHub account (riteshbonthalakoti), not a default/generic
   identity. Set them explicitly at repo level if they don't already match
   — `git config user.name "<real name>"` / `user.email "<real email>"`.
   Print what you set so it's visible in the handoff.
2. Commit at each real checkpoint below, not once at the end. Each
   numbered task in this prompt is roughly one commit — some tasks may
   split into two if there's a genuine sub-step (e.g. "SQLite implementation"
   then "SQLite tests passing" are two commits, not one). Don't pad beyond
   what's real, and don't collapse real steps into one giant commit either.
   If you hit a genuine debugging detour (like Module 03's IAM roles or
   monsoon cloud cover), that's its own commit too — it's real work and
   worth showing as such.

## Tasks

### 1. Migrations from the schema, not a hand-duplicated field list
Write a migration generator (or hand-written migrations that you verify
against `specs/core/schema.yaml` field-by-field — pick whichever is more
reliable, but state which and why) producing DDL for both SQLite and
Postgres for all 10 entities. If a field list drifts from `schema.yaml`
later, that's exactly the kind of bug `check_specs.py` should eventually
catch — note this as a possible Module 02 enhancement in your handoff if
you don't have time to wire it in now, don't silently skip it.

### 2. `SQLiteDataStore`
Implements every method in `repository-interface.md` against a local
`.db` file (already gitignored). This is the default for all local dev
and for every other module's test suite going forward.

### 3. `SupabaseDataStore`
Same interface, implemented against the Supabase project already set up
and authenticated in Module 01 (`supabase` CLI). Use the `supabase` CLI to
apply migrations to the actual project — don't hand-run SQL through a
dashboard. Read connection details from env vars (`SUPABASE_URL`,
`SUPABASE_KEY` or equivalent) — add these to `.env.example`, never commit
real values.
- Note in your handoff: Supabase's free-tier project auto-pauses after 7
  days with no activity (per the stack research). Add a one-line note to
  `docs/TOOLING.md` on how to resume it (`supabase` CLI command or
  dashboard fallback), so this doesn't surprise a future session.

### 4. Parity test suite
The important part of this module. Write ONE test suite that runs against
**both** backends via parametrization (e.g. pytest fixture that yields
each `DataStore` implementation) — same assertions, same data, both
backends. This is the actual proof that the repository pattern works,
not just an architecture diagram claiming it does. SQLite tests always
run; Supabase tests skip cleanly if credentials aren't present in the
shell, same pattern as Module 03's live-gated tests.

### 5. Seed script using the golden fixture
`tools/seed_fixture.py` (or similar): loads `specs/domains/fixtures/farm-001.json`
into a given backend via the `DataStore` interface, and a corresponding
verification that reads it back and matches field-for-field. Run it against
both backends as part of your own manual validation, not just unit tests.

### 6. Update doctrine
- `modules/04-storage/STATUS`
- `CLAUDE.md` current phase → Module 04 complete, Module 05 next
- `decisions/`: an ADR if you make any non-obvious call (e.g. connection
  pooling approach, how you're generating migrations)
- `python tools/update_state.py`, review, commit
- Run `python tools/check_specs.py` — confirm nothing drifted

## Definition of done
- [ ] `git config` shows your real identity for this repo
- [ ] Both `SQLiteDataStore` and `SupabaseDataStore` implement the full
      interface from `repository-interface.md`
- [ ] The same parity test suite passes against both (Supabase skips
      gracefully without creds, doesn't fail the suite)
- [ ] Seed script round-trips the golden fixture correctly on both backends
- [ ] No secrets in the diff
- [ ] Commit history shows real, distinct checkpoints — check your own log
      before pushing and squash anything that isn't a genuine step
- [ ] Doctrine updated, pushed to `origin/main`

## Handoff format
```
Module: 04 — Storage Layer
Status: complete | blocked (say on what)
Implemented:
Files changed:
Commits made: <list with one-line summary each — this is new, include it>
Tests created: <+pass/fail, note SQLite vs Supabase coverage>
Known limitations:
Remaining risks:
Next recommended module: 05 — Processing & Feature Engineering
```
