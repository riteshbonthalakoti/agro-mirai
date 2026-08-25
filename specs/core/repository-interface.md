# Repository Interface

`DataStore` is the abstraction every module goes through to read or write
domain records. Module 04 implements it against SQLite for local dev and
against Supabase Postgres for production; no other module talks to a
database engine directly (CLAUDE.md hard rule #3).

This document is the contract. Method signatures below are Python-flavoured
pseudocode; Module 04 will land the real `Protocol` (or ABC) in
`agro_mirai/persistence/store.py`.

## Design rules

1. **Return domain dataclasses, not ORM rows.** Callers depend on the
   shapes in `specs/core/schema.yaml`, nothing engine-specific leaks out.
2. **Every mutating method returns the persisted record**, with any
   server-populated fields (`id` when omitted, `created_at`, `updated_at`)
   filled in.
3. **Ownership is enforced inside the store.** Every read/write method
   that touches farmer-owned data takes an explicit `farmer_id` and
   filters by it. There is no "admin escape hatch" for v1
   (docs/conventions.md §4).
4. **Not-found is `None`, not an exception.** `NotFoundError` is reserved
   for cases where a caller tried to write against a missing parent
   (e.g. `save_ndvi_reading` for a `field_id` the farmer does not own).
5. **List methods take explicit `limit` and `since` filters**, default
   `limit=50`, no unbounded fetches.
6. **Timestamps in / out are timezone-aware `datetime` in UTC.** The
   store handles the serialisation to SQLite TEXT or Postgres
   `timestamptz`.

## Errors

```python
class NotFoundError(Exception):
    """Raised when a mutation targets a parent that does not exist or is
    not owned by the given farmer."""

class ConflictError(Exception):
    """Raised on unique-constraint violations (e.g. duplicate id)."""
```

Both are engine-neutral; the implementation translates from
`sqlite3.IntegrityError`, `asyncpg.UniqueViolationError`, etc.

## Method signatures

Types (`Farmer`, `Field`, `WeatherReading`, …) map 1:1 to the entities in
`specs/core/schema.yaml`.

### Farmer

```python
def get_farmer(farmer_id: str) -> Farmer | None: ...

def save_farmer(farmer: Farmer) -> Farmer:
    """Insert if id is unknown, else update. Sets created_at/updated_at."""
```

### Field

```python
def get_field(farmer_id: str, field_id: str) -> Field | None: ...

def list_fields(farmer_id: str, limit: int = 50) -> list[Field]: ...

def save_field(farmer_id: str, field: Field) -> Field:
    """Insert or update. Raises NotFoundError if farmer_id is unknown."""

def delete_field(farmer_id: str, field_id: str) -> bool:
    """Returns True if a record was deleted, False if it was already
    absent. Cascades to child readings and advisories."""
```

### Readings and samples

```python
def save_weather_reading(farmer_id: str, reading: WeatherReading) -> WeatherReading: ...

def list_weather_readings(
    farmer_id: str,
    field_id: str,
    since: datetime | None = None,
    limit: int = 50,
) -> list[WeatherReading]: ...

def save_soil_sample(farmer_id: str, sample: SoilSample) -> SoilSample: ...

def list_soil_samples(
    farmer_id: str,
    field_id: str,
    limit: int = 50,
) -> list[SoilSample]: ...

def save_ndvi_reading(farmer_id: str, reading: NDVIReading) -> NDVIReading: ...

def list_ndvi_readings(
    farmer_id: str,
    field_id: str,
    since: datetime | None = None,
    limit: int = 50,
) -> list[NDVIReading]: ...
```

### Recommendations, advice, alerts

```python
def save_crop_recommendation(
    farmer_id: str, recommendation: CropRecommendation
) -> CropRecommendation: ...

def get_latest_crop_recommendation(
    farmer_id: str, field_id: str
) -> CropRecommendation | None: ...

def save_irrigation_advice(
    farmer_id: str, advice: IrrigationAdvice
) -> IrrigationAdvice: ...

def get_latest_irrigation_advice(
    farmer_id: str, field_id: str
) -> IrrigationAdvice | None: ...

def save_disease_risk_alert(
    farmer_id: str, alert: DiseaseRiskAlert
) -> DiseaseRiskAlert: ...

def list_disease_risk_alerts(
    farmer_id: str,
    field_id: str,
    since: datetime | None = None,
    limit: int = 50,
) -> list[DiseaseRiskAlert]: ...
```

### Advisories and feedback

```python
def save_advisory(farmer_id: str, advisory: Advisory) -> Advisory: ...

def list_advisories_for_field(
    farmer_id: str,
    field_id: str,
    limit: int = 50,
) -> list[Advisory]: ...

def get_advisory(farmer_id: str, advisory_id: str) -> Advisory | None: ...

def save_feedback_entry(farmer_id: str, entry: FeedbackEntry) -> FeedbackEntry:
    """Raises NotFoundError if advisory_id does not exist or is not owned
    by farmer_id."""

def list_feedback_for_advisory(
    farmer_id: str, advisory_id: str, limit: int = 50
) -> list[FeedbackEntry]: ...
```

### Health

```python
def ping() -> bool:
    """Return True if the underlying engine is reachable. Used by the
    health endpoint in Module 11."""
```

## Testing contract

Module 04 must ship a shared test suite (`tests/persistence/contract/`)
that both the SQLite and Supabase implementations pass. The golden
fixture at `specs/domains/fixtures/farm-001.json` is the canonical load
target for those tests.
