"""Soil adapter — SoilGrids REST API (ISRIC, no API key required).

Maps a SoilGrids point query to a single ``SoilSample`` record
(``specs/core/schema.yaml``).

Representative depth interval
-----------------------------
SoilGrids returns predictions for several standard depth intervals
(0-5cm, 5-15cm, 15-30cm, …). We use the **topsoil 0-5cm** interval as the
single representative sample. Rationale: it is the layer a farmer's own
lab test samples — the plough/surface layer where fertiliser is applied
and where pH and available nutrients most directly drive crop advice.
Deeper intervals describe the subsoil and are out of scope for v1's
single-sample model. The interval used is recorded on the returned
record's provenance via ``source`` (``soilgrids``) and documented in
``docs/architecture.md``.

Unit mapping (SoilGrids "mapped" integer → conventions §5 units)
----------------------------------------------------------------
SoilGrids encodes each property as an integer that must be divided by a
per-property ``d_factor`` to reach its target unit:

* ``phh2o``    mapped = pH×10        → ``ph``                 = mapped / 10
* ``nitrogen`` mapped = cg/kg (N)    → ``nitrogen_mg_per_kg`` = mapped × 10
                                       (cg/kg → mg/kg: ×10)
* ``soc``      mapped = dg/kg (SOC)  → ``organic_carbon_pct`` = mapped / 100
                                       (dg/kg → g/kg /10, g/kg → % ×0.1)

SoilGrids v2 does **not** provide phosphorus or potassium, so
``phosphorus_mg_per_kg`` / ``potassium_mg_per_kg`` are left unset
(optional in the schema); likewise ``moisture_pct`` (a dynamic quantity,
not a SoilGrids static property). A downstream module may fill these from
a lab report or synthesis.

**Known limitation — total vs. plant-available nitrogen.** SoilGrids'
``nitrogen`` property is *total* soil nitrogen (a global geophysical
prediction), not the *plant-available* nitrogen an Indian soil-testing
lab report measures. Both are legitimately expressed in
``nitrogen_mg_per_kg`` per the schema (same unit, same field), but they
answer different agronomic questions and are **not directly comparable**
across ``source: lab_report`` vs ``source: soilgrids`` records for the
same field — expect SoilGrids' value to read roughly 10-100x higher.
Module 06 (crop recommendation) and any nitrogen-threshold logic must
branch on ``source`` rather than assuming a single scale. Flagged here
rather than silently reinterpreted, because narrowing the schema's
meaning is a contract change per CLAUDE.md rule #2, not a Module 03
decision.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from .base import (
    Adapter,
    FieldInput,
    SourceResponseError,
    SourceUnavailableError,
    new_id,
    utc_now_iso,
)

QUERY_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

#: The representative depth interval (see module docstring).
REPRESENTATIVE_DEPTH = "0-5cm"

#: SoilGrids properties we request → (SoilSample field, converter).
_PROPERTY_MAP: dict[str, tuple[str, Any]] = {
    "phh2o": ("ph", lambda v: v / 10.0),
    "nitrogen": ("nitrogen_mg_per_kg", lambda v: v * 10.0),
    "soc": ("organic_carbon_pct", lambda v: v / 100.0),
}

DEFAULT_TIMEOUT_S = 30.0  # SoilGrids is frequently slow; give it room.


class SoilAdapter(Adapter):
    """SoilGrids → ``SoilSample`` (topsoil 0-5cm)."""

    source = "soilgrids"

    def __init__(
        self,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout_s = timeout_s
        self._session = session or requests.Session()

    def fetch(self, field: FieldInput) -> list[dict[str, Any]]:
        """Return a one-element list holding the field's topsoil sample.

        A list (not a bare dict) keeps the return type uniform with the
        other adapters. Raises if SoilGrids is unreachable; returns a
        sample with only the fields SoilGrids could populate otherwise
        (a no-data pixel yields a sample with no chemistry values).
        """
        params = [
            ("lon", field.longitude),
            ("lat", field.latitude),
            ("depth", REPRESENTATIVE_DEPTH),
            ("value", "mean"),
        ]
        for prop in _PROPERTY_MAP:
            params.append(("property", prop))
        payload = self._get_with_retry(QUERY_URL, params)
        return [self._map_sample(payload, field)]

    # -- mapping (pure) ----------------------------------------------------
    def _map_sample(
        self, payload: dict[str, Any], field: FieldInput
    ) -> dict[str, Any]:
        sample: dict[str, Any] = {
            "id": new_id(),
            "observed_at": utc_now_iso(),
            "source": self.source,
        }
        if field.field_id:
            sample["field_id"] = field.field_id

        layers = (payload.get("properties") or {}).get("layers") or []
        for layer in layers:
            name = layer.get("name")
            if name not in _PROPERTY_MAP:
                continue
            mean = self._mean_at_depth(layer, REPRESENTATIVE_DEPTH)
            if mean is None:
                continue  # no-data pixel for this property; leave field unset
            field_name, convert = _PROPERTY_MAP[name]
            sample[field_name] = round(float(convert(mean)), 4)
        return sample

    @staticmethod
    def _mean_at_depth(layer: dict[str, Any], depth_label: str) -> float | None:
        for depth in layer.get("depths") or []:
            if depth.get("label") == depth_label:
                value = (depth.get("values") or {}).get("mean")
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    return None
                return float(value)
        return None

    # -- transport ---------------------------------------------------------
    def _get_with_retry(
        self, url: str, params: list[tuple[str, Any]]
    ) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                resp = self._session.get(url, params=params, timeout=self.timeout_s)
                if resp.status_code >= 500:
                    raise SourceUnavailableError(
                        f"SoilGrids returned {resp.status_code}"
                    )
                if resp.status_code >= 400:
                    raise SourceResponseError(
                        f"SoilGrids returned {resp.status_code}: {resp.text[:200]}"
                    )
                return resp.json()
            except SourceResponseError:
                raise
            except (requests.RequestException, SourceUnavailableError) as exc:
                last_exc = exc
                if attempt == 0:
                    time.sleep(1.0)
                    continue
        raise SourceUnavailableError(
            f"SoilGrids unreachable after retry: {last_exc}"
        ) from last_exc
