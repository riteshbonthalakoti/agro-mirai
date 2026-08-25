#!/usr/bin/env python3
"""Seed the local NDVI cache with a real, live GEE value.

Per CLAUDE.md hard rule #4 the NDVI cache backs the live→cache fallback,
and per the Module 03 task the golden-fixture farm (``farm-001``) entry
must be a *real* precomputed value pulled once from Earth Engine — never
fabricated. This script does exactly that and writes it into
``specs/domains/fixtures/ndvi_cache.json``.

Prerequisites: ``EE_SERVICE_ACCOUNT_KEY`` set to the service-account key
path (see docs/TOOLING.md), and the service account granted
``roles/serviceusage.serviceUsageConsumer`` on its GCP project.

    EE_SERVICE_ACCOUNT_KEY=~/.config/agro-mirai/ee-service-account.json \
        python tools/seed_ndvi_cache.py

Re-running updates the farm-001 entry in place (keyed by field id).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from agro_mirai.acquisition import FieldInput, NDVIAdapter  # noqa: E402
from agro_mirai.acquisition.earth_engine import DEFAULT_CACHE_PATH  # noqa: E402

FIXTURE = ROOT / "specs" / "domains" / "fixtures" / "farm-001.json"


def _load_farm_field() -> FieldInput:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    field = data["fields"][0]
    return FieldInput.from_field(field)


def _upsert(cache_path: Path, entry: dict) -> None:
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        cache = {"description": "Local NDVI cache (CLAUDE.md hard rule #4).",
                 "entries": []}
    entries = cache.setdefault("entries", [])
    entries = [e for e in entries if e.get("field_id") != entry["field_id"]]
    entries.append(entry)
    cache["entries"] = entries
    cache_path.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    field = _load_farm_field()
    # Widen the lookback window for this one-time seed pull only. The
    # adapter's production defaults (decisions/0004-gee-timeout-and-
    # fallback.md: 30 days, <20% cloud) are tuned for a live serving path
    # and correctly find nothing during a monsoon-cloud stretch over
    # Bellary — that's what the fallback is for. The seed just needs one
    # real, recent low-cloud scene to exist; 90 days reliably has one.
    adapter = NDVIAdapter(lookback_days=90)
    # Force the live path so we never seed a cache value from the cache.
    reading = adapter._fetch_live(field)  # noqa: SLF001 — deliberate, seeder only
    entry = {
        "field_id": field.field_id,
        "latitude": field.latitude,
        "longitude": field.longitude,
        "observed_at": reading["observed_at"],
        "ndvi": reading["ndvi"],
        "cloud_cover_pct": reading.get("cloud_cover_pct"),
        "satellite": reading.get("satellite", "sentinel-2"),
    }
    _upsert(DEFAULT_CACHE_PATH, entry)
    print(f"Seeded NDVI cache for {field.field_id}: ndvi={entry['ndvi']} "
          f"observed_at={entry['observed_at']} -> {DEFAULT_CACHE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
