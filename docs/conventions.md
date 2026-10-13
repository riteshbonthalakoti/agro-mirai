# Conventions

Platform-wide rules for AGRO MIRAI. Boring on purpose — these are the
things that get expensive to change once code depends on them, so they get
decided once, here, and everything else defers.

Additive-only: changing a rule below means writing a new ADR and, where
relevant, a new versioned contract. Never a silent rewrite.

## 1. Identifiers

- **All entity IDs are UUIDv4 strings.**
- Rendered lowercase, unhyphenated form is forbidden — always the standard
  8-4-4-4-12 hyphenated form (`f47ac10b-58cc-4372-a567-0e02b2c3d479`).
- Rationale: globally unique without a coordinator, cheap to generate on
  device, avoids exposing row counts, portable between SQLite and Postgres
  without sequence gymnastics. See `decisions/0002-id-format.md`.
- IDs are opaque to the client. Never parse meaning out of them.

## 2. Timestamps

- **All timestamps are UTC, ISO 8601, second precision, `Z` suffix.**
  Example: `2026-08-25T14:03:12Z`.
- Field naming: `created_at`, `updated_at`, `observed_at`, `deleted_at`.
  The `_at` suffix always denotes an instant in time. Date-only fields use
  the `_on` suffix (e.g. `sown_on`) and are ISO 8601 dates
  (`YYYY-MM-DD`).
- Storage: SQLite as TEXT ISO 8601, Postgres as `timestamptz`. The
  repository interface converts.
- Time zone display is a presentation concern; the API always emits UTC.

## 3. Error envelope

Every JSON API response that represents an error uses this exact shape:

```json
{
  "error": {
    "code": "SNAKE_CASE_CODE",
    "message": "Human-readable, single sentence, no trailing period.",
    "details": {}
  }
}
```

- `code` is a stable machine-readable slug. Codes are additive; a code
  never changes meaning.
- `message` is meant for a developer, not an end-user. Localised
  end-user copy is a frontend concern.
- `details` is an object; may be `{}` but must be present. Field-level
  validation errors go in `details.fields` as
  `{ "<field>": "<reason>" }`.
- HTTP status code categorises the class of failure (4xx client, 5xx
  server); the envelope carries the specific reason.

## 4. Ownership and tenancy

**Single-farmer-account-per-user.** This project is not multi-tenant SaaS.
Each authenticated user corresponds to exactly one `Farmer`. A `Farmer`
owns zero or more `Field`s; all other domain records (readings, samples,
advisories, feedback) belong to a `Field` and, transitively, to that
`Farmer`.

Authorization rule: a user may read and write records whose transitive
owner is their own `Farmer`. No cross-farmer sharing endpoints exist. If
that ever changes, it needs a new ADR and a new API version — not a
patch. See `decisions/0003-single-farmer-tenancy.md`.

## 5. Units

Metric throughout. No exceptions in stored data; presentation-layer
conversion (e.g. displaying acres for a user who prefers acres) is a
frontend concern and never touches the schema.

| Quantity | Unit | Field example |
|---|---|---|
| Length | metre (`m`) | `elevation_m` |
| Area | hectare (`ha`) | `area_ha` |
| Rainfall / irrigation depth | millimetre (`mm`) | `rainfall_mm` |
| Temperature | degrees Celsius (`c`) | `temp_c`, `temp_min_c` |
| Humidity | percent (`pct`, 0–100) | `humidity_pct` |
| Wind speed | metres per second (`mps`) | `wind_mps` |
| Soil moisture | volumetric percent (`pct`) | `soil_moisture_pct` |
| Soil pH | dimensionless | `ph` |
| NPK | milligrams per kilogram (`mg_per_kg`) | `nitrogen_mg_per_kg` |
| NDVI | dimensionless, -1..1 | `ndvi` |
| Confidence | 0..1 float | `confidence` |
| Geographic point | WGS84 decimal degrees | `latitude`, `longitude` |

Unit is encoded in the field name suffix wherever there is any risk of
ambiguity. Prefer `rainfall_mm` to a bare `rainfall`.

## 6. Naming

- API paths and JSON field names are `snake_case`.
- Python identifiers follow PEP 8 (`snake_case` functions, `PascalCase`
  classes).
- Enum values are `snake_case` strings, closed-vocabulary, defined in
  `specs/core/enums.md`.
- No abbreviations that a farmer would not recognise (`irrigation`, not
  `irrig`).

## 7. Language codes

ISO 639-1 two-letter codes (`en`, `hi`, `kn`, `ta`, `te`, …). Bundled
languages track what the AI4Bharat translation stack covers when Module
12 wires it up; the enum is additive.

## 8. Versioning

- API versions are URL-prefixed: `/v1/…`. There is only `v1` today.
- Adding an optional field or a new endpoint is a non-breaking change and
  stays in `v1`. Renaming, removing, or narrowing a field is breaking and
  requires `v2` plus a deprecation window on `v1`.
- Schema and OpenAPI files carry a top-level `version` field mirroring
  the API version prefix.
