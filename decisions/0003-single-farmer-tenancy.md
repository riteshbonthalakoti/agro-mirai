# ADR 0003 — Ownership model: single farmer per user account

**Status:** accepted
**Date:** 2026-08-25
**Module:** 02 — Data Contracts & Conventions

## Context

AGRO MIRAI is a VTU Sem 7 capstone; the original PPT
(`AGRO_MIRAI2.1.pdf`) describes advisories delivered to individual
farmers, not to co-operatives or extension agents managing many farms.
The 15-module plan does not include roles, permissions, or org
management.

Nevertheless a codebase without an explicit ownership rule invites later
modules to invent an ad-hoc multi-tenancy story (an "admin" flag here, a
`shared_with` list there) and then rip it out.

## Decision

**Single-farmer-account-per-user.** Each authenticated user maps to
exactly one `Farmer`. A `Farmer` owns zero or more `Field`s; every other
domain record ties back through a `Field` (or directly through the
`Farmer`, for `FeedbackEntry`).

Authorization rule (enforced at the repository layer, see
`specs/core/repository-interface.md`): a caller may only read or write
records whose transitive owner is their own `Farmer`. Every repository
method takes an explicit `farmer_id`; there is no admin escape hatch.

## Consequences

- Simpler schema: no `organizations`, `memberships`, `roles`, `shares`.
- Simpler tests: the golden fixture in
  `specs/domains/fixtures/farm-001.json` never needs to model
  cross-farmer visibility.
- If the project ever needs multi-farmer sharing (an extension officer
  viewing several farmers, a co-operative dashboard), it needs a new ADR
  and a new API version (`/v2`), not a patch to `v1`.
- No later module may reintroduce a multi-tenant abstraction without a
  superseding ADR.
