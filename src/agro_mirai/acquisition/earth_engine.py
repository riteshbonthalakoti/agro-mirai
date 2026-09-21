"""NDVI adapter — Google Earth Engine (Sentinel-2) with cache fallback.

Implements CLAUDE.md **hard rule #4**: GEE is the live source for NDVI;
every read attempts the live query first and falls back to a local NDVI
cache on timeout, quota exhaustion, or any GEE exception — never a hard
failure. Which path served the result is logged, and is recorded on the
returned ``NDVIReading.source`` (``gee_live`` vs ``cache``).

Live path
---------
Authenticate with the service account whose key path is in the
``EE_SERVICE_ACCOUNT_KEY`` environment variable (never hardcoded; the key
lives outside the repo — see ``docs/TOOLING.md``). Query
``COPERNICUS/S2_SR_HARMONIZED``, filtered to the field's point and the
last ``lookback_days`` days, keeping only scenes below
``max_cloud_cover_pct``; take the most-recent such scene, compute NDVI
= (B8 − B4) / (B8 + B4), and reduce it to the mean over a small buffer
around the point.

An explicit timeout wraps the blocking ``getInfo`` call (the GEE client
has no per-call timeout of its own) via a worker thread; exceeding it
triggers the fallback. Thresholds are an ADR
(``decisions/0004-gee-timeout-and-fallback.md``).

Cache path
----------
A local JSON cache (default ``specs/domains/fixtures/ndvi_cache.json``)
keyed by field id, with a lat/long fallback key. Seeded with a real,
precomputed value for the golden-fixture farm (``farm-001``) — see
``tools/seed_ndvi_cache.py``. A cache miss with no live result is the one
case that still raises :class:`SourceUnavailableError` (there is nothing
truthful to return, and fabricating a value is forbidden).
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import os
from pathlib import Path
from typing import Any

from .base import (
    Adapter,
    FieldInput,
    SourceUnavailableError,
    new_id,
    utc_now_iso,
)

logger = logging.getLogger("agro_mirai.acquisition.ndvi")

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_PATH = _ROOT / "specs" / "domains" / "fixtures" / "ndvi_cache.json"

# -- Fallback thresholds (ADR 0004) ---------------------------------------
DEFAULT_TIMEOUT_S = 20.0          # wall-clock budget for the live getInfo
DEFAULT_MAX_CLOUD_COVER_PCT = 20.0  # scene-level cloud ceiling
DEFAULT_LOOKBACK_DAYS = 30        # how far back to search for a clean scene
DEFAULT_BUFFER_M = 30.0           # reduceRegion radius around the point (m)

S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
CLOUD_PROP = "CLOUDY_PIXEL_PERCENTAGE"
SATELLITE = "sentinel-2"

SOURCE_LIVE = "gee_live"
SOURCE_CACHE = "cache"


class NDVIAdapter(Adapter):
    """Earth Engine (Sentinel-2) → ``NDVIReading`` with cache fallback."""

    source = SOURCE_LIVE  # nominal source; a fallback stamps SOURCE_CACHE

    def __init__(
        self,
        cache_path: Path | str = DEFAULT_CACHE_PATH,
        key_path: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_cloud_cover_pct: float = DEFAULT_MAX_CLOUD_COVER_PCT,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        buffer_m: float = DEFAULT_BUFFER_M,
    ) -> None:
        self.cache_path = Path(cache_path)
        self._key_path = key_path  # else read EE_SERVICE_ACCOUNT_KEY lazily
        self.timeout_s = timeout_s
        self.max_cloud_cover_pct = max_cloud_cover_pct
        self.lookback_days = lookback_days
        self.buffer_m = buffer_m
        self._ee_ready = False

    # -- public API --------------------------------------------------------
    def fetch(self, field: FieldInput) -> list[dict[str, Any]]:
        """Return a one-element list holding the field's latest NDVI.

        Live GEE first; on any failure, the local cache. Only a cache miss
        after a live failure raises.
        """
        try:
            reading = self._fetch_live(field)
            logger.info(
                "NDVI for field=%s served via %s (ndvi=%.3f)",
                field.field_id, SOURCE_LIVE, reading["ndvi"],
            )
            return [reading]
        except Exception as exc:  # noqa: BLE001 — fallback is the whole point
            logger.warning(
                "GEE live NDVI failed for field=%s (%s: %s); falling back to cache",
                field.field_id, type(exc).__name__, exc,
            )
            reading = self._fetch_cache(field)
            logger.info(
                "NDVI for field=%s served via %s (ndvi=%.3f)",
                field.field_id, SOURCE_CACHE, reading["ndvi"],
            )
            return [reading]

    # -- live path ---------------------------------------------------------
    def _ensure_initialized(self) -> None:
        if self._ee_ready:
            return
        import ee  # imported lazily so offline/cache use needs no GEE install

        # Hosted deployments (Render) have no key file on disk: the service
        # account JSON can be supplied as text in EE_SERVICE_ACCOUNT_JSON.
        key_json = (os.environ.get("EE_SERVICE_ACCOUNT_JSON") or "").strip()
        if key_json and not self._key_path:
            from google.oauth2 import service_account

            sa = json.loads(key_json)
            creds = service_account.Credentials.from_service_account_info(
                sa, scopes=ee.oauth.SCOPES
            )
        else:
            key_path = self._key_path or os.environ.get("EE_SERVICE_ACCOUNT_KEY")
            if not key_path:
                raise SourceUnavailableError(
                    "EE_SERVICE_ACCOUNT_KEY is not set; cannot authenticate GEE"
                )
            with open(key_path, encoding="utf-8") as fh:
                sa = json.load(fh)
            creds = ee.ServiceAccountCredentials(sa["client_email"], key_path)
        ee.Initialize(creds, project=sa.get("project_id"))
        self._ee_ready = True

    def _fetch_live(self, field: FieldInput) -> dict[str, Any]:
        import ee

        self._ensure_initialized()

        def _query() -> dict[str, Any]:
            import datetime as _dt

            point = ee.Geometry.Point([field.longitude, field.latitude])
            end = ee.Date(_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d"))
            start = end.advance(-self.lookback_days, "day")
            collection = (
                ee.ImageCollection(S2_COLLECTION)
                .filterBounds(point)
                .filterDate(start, end)
                .filter(ee.Filter.lt(CLOUD_PROP, self.max_cloud_cover_pct))
                .sort("system:time_start", False)
            )
            image = ee.Image(collection.first())
            ndvi = image.normalizedDifference(["B8", "B4"]).rename("ndvi")
            region = point.buffer(self.buffer_m)
            stats = ndvi.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e9
            )
            info = ee.Dictionary(
                {
                    "ndvi": stats.get("ndvi"),
                    "cloud": image.get(CLOUD_PROP),
                    "millis": image.get("system:time_start"),
                }
            ).getInfo()
            return info

        # Explicit wall-clock timeout around the blocking getInfo.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_query)
            try:
                info = future.result(timeout=self.timeout_s)
            except concurrent.futures.TimeoutError as exc:
                raise SourceUnavailableError(
                    f"GEE query exceeded {self.timeout_s}s timeout"
                ) from exc

        if info is None or info.get("ndvi") is None:
            raise SourceUnavailableError(
                "GEE returned no low-cloud Sentinel-2 scene for this field/window"
            )

        reading: dict[str, Any] = {
            "id": new_id(),
            "observed_at": _millis_to_iso(info.get("millis")),
            "source": SOURCE_LIVE,
            "ndvi": round(float(info["ndvi"]), 4),
            "satellite": SATELLITE,
        }
        if info.get("cloud") is not None:
            reading["cloud_cover_pct"] = round(float(info["cloud"]), 2)
        if field.field_id:
            reading["field_id"] = field.field_id
        return reading

    # -- cache path --------------------------------------------------------
    def _fetch_cache(self, field: FieldInput) -> dict[str, Any]:
        entry = self._lookup_cache(field)
        if entry is None:
            raise SourceUnavailableError(
                f"NDVI cache miss for field={field.field_id} "
                f"({field.latitude},{field.longitude}) and GEE was unavailable"
            )
        reading: dict[str, Any] = {
            "id": new_id(),
            "observed_at": entry.get("observed_at", utc_now_iso()),
            "source": SOURCE_CACHE,
            "ndvi": round(float(entry["ndvi"]), 4),
        }
        if entry.get("cloud_cover_pct") is not None:
            reading["cloud_cover_pct"] = round(float(entry["cloud_cover_pct"]), 2)
        reading["satellite"] = entry.get("satellite", SATELLITE)
        if field.field_id:
            reading["field_id"] = field.field_id
        return reading

    def _lookup_cache(self, field: FieldInput) -> dict[str, Any] | None:
        if not self.cache_path.exists():
            return None
        data = json.loads(self.cache_path.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        # Primary key: field id.
        if field.field_id:
            for e in entries:
                if e.get("field_id") == field.field_id:
                    return e
        # Fallback key: rounded lat/long (6 dp ≈ 0.1 m).
        key = _coord_key(field.latitude, field.longitude)
        for e in entries:
            if _coord_key(e.get("latitude"), e.get("longitude")) == key:
                return e
        return None


# -- helpers ---------------------------------------------------------------
def _coord_key(lat: Any, lon: Any) -> str | None:
    if lat is None or lon is None:
        return None
    return f"{float(lat):.6f},{float(lon):.6f}"


def _millis_to_iso(millis: Any) -> str:
    from datetime import datetime, timezone

    if millis is None:
        return utc_now_iso()
    dt = datetime.fromtimestamp(float(millis) / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
