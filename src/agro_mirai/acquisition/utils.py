"""Shared HTTP helpers for the acquisition layer."""
import time
from typing import Any

import requests

from .base import SourceResponseError, SourceUnavailableError


def fetch_with_retry(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    session: requests.Session | None = None,
    retries: int = 2,
    backoff: float = 0.5,
    timeout: float = 10.0,
    source_name: str = "remote",
    non_retriable_statuses: tuple[int, ...] = (),
) -> dict[str, Any]:
    """GET a JSON URL with retry+backoff. Raises typed SourceError on failure.

    Args:
        url: Full URL to GET.
        params: Query parameters dict.
        session: Existing ``requests.Session`` to reuse; a fresh one is created
            when omitted.
        retries: Total attempts (default 2 = initial try + one retry).
        backoff: Sleep seconds before the second attempt.
        timeout: Per-request timeout in seconds.
        source_name: Label used in error messages.
        non_retriable_statuses: Specific status codes that raise immediately
            without retry (e.g. ``(401,)`` for an auth failure). All other
            4xx codes are also non-retriable via the ``>= 400`` fallback.

    Returns:
        Parsed JSON response as a dict.

    Raises:
        SourceResponseError: On a non-retriable 4xx.
        SourceUnavailableError: On 5xx or exhausted retries.
    """
    _session = session or requests.Session()
    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            resp = _session.get(url, params=params, timeout=timeout)
            # Specific codes listed in non_retriable_statuses abort immediately.
            if resp.status_code in non_retriable_statuses:
                raise SourceResponseError(
                    f"{source_name} returned {resp.status_code}: {resp.text[:200]}"
                )
            if resp.status_code >= 500:
                raise SourceUnavailableError(
                    f"{source_name} returned {resp.status_code}"
                )
            if resp.status_code >= 400:
                # All other 4xx are client errors — non-transient, don't retry.
                raise SourceResponseError(
                    f"{source_name} returned {resp.status_code}: {resp.text[:200]}"
                )
            return resp.json()
        except SourceResponseError:
            raise
        except (requests.RequestException, SourceUnavailableError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(backoff)
                continue

    raise SourceUnavailableError(
        f"{source_name} unreachable after retry: {last_exc}"
    ) from last_exc
