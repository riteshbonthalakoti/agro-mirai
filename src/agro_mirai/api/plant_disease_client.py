"""HTTP client for Kindwise's Crop.Health plant-disease identification API
(AI cascade restructure, scratch/restructure-plan.md).

Uses the shared ``KeyPool`` (``api/key_pool.py``) for key rotation, same as
the vision-LLM tier. Important operational note, not a bug: Kindwise's
signup grants a one-time batch of free identification credits per account
rather than a renewing monthly quota, so this pool is expected to run dry
over time as credits are consumed -- once every configured key is
exhausted, ``identify_disease`` returns ``None`` on every call and the
cascade falls through to the vision-LLM tier (and from there, CNN) exactly
as it would if this tier were simply unconfigured. That is the intended,
permanent long-run behavior for this tier, not a failure to fix.

Never raises -- matches every other tier's never-raise contract in
``models/image_or_environmental_disease.py``.
"""
import logging
import os

import requests

from agro_mirai.api.key_pool import KeyPool

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 8
_IDENTIFY_URL = "https://crop.kindwise.com/api/v1/identification"

_pool = KeyPool(provider_name="kindwise", env_prefix="PLANT_DISEASE_API_KEY")


def plant_disease_timeout() -> float:
    raw = os.environ.get("PLANT_DISEASE_API_TIMEOUT_S", "")
    try:
        return float(raw) if raw else DEFAULT_TIMEOUT_S
    except ValueError:
        return DEFAULT_TIMEOUT_S


_NOT_A_PLANT = "__not_a_plant__"


def identify_disease(image_bytes: bytes, field_id: str) -> dict | None | str:
    """POSTs the image to Kindwise Crop.Health. Returns the parsed JSON
    body's top disease suggestion as a dict (``{"disease": str,
    "confidence": float}``) on success, ``None`` on anything else --
    no usable key (unconfigured, or every key exhausted/cooling down),
    network error, timeout, non-200 status, or a response shape without
    a disease suggestion -- or the sentinel string ``_NOT_A_PLANT`` when
    Kindwise's own ``is_plant`` classifier is confident the photo isn't a
    plant at all (the caller maps this to its own ``NOT_A_PLANT``
    sentinel). Never raises.

    On a 429, the exhausted key is put on cooldown and the call is
    retried once with the next key in the pool (matches the retry-once
    convention in ``cnn_client.call_cnn_service``)."""
    for _ in range(2):
        key = _pool.get_key()
        if key is None:
            return None
        try:
            resp = requests.post(
                _IDENTIFY_URL,
                files={"images": ("image.jpg", image_bytes)},
                headers={"Api-Key": key},
                timeout=plant_disease_timeout(),
            )
        except requests.RequestException as exc:
            logger.warning("Kindwise Crop.Health field=%s: network error: %s", field_id, exc)
            return None

        if resp.status_code == 429:
            _pool.mark_rate_limited(key)
            continue  # one retry with the next key in the pool

        if resp.status_code != 200:
            logger.warning(
                "Kindwise Crop.Health field=%s: status %s", field_id, resp.status_code
            )
            return None

        _pool.mark_success(key)
        try:
            data = resp.json()
            is_plant = data.get("result", {}).get("is_plant", {})
            if is_plant.get("binary") is False and float(is_plant.get("probability", 1.0)) < 0.5:
                return _NOT_A_PLANT
            suggestions = data["result"]["disease"]["suggestions"]
            top = suggestions[0]
            return {"disease": top["name"], "confidence": float(top["probability"])}
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning("Kindwise Crop.Health field=%s: malformed response: %s", field_id, exc)
            return None
    return None  # both attempts hit 429 — every key exhausted/cooling down
