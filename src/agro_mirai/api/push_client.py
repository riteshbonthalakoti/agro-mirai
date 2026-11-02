"""Android push notifications via Expo's push service (Module 59).

Expo's push API (https://exp.host/--/api/v2/push/send) is the relay in
front of Google's FCM -- the app registers for an Expo push token
(mobile/src/push.ts), the backend stores it (persistence layer,
``push_tokens`` table) and posts to this one HTTP endpoint whenever it
wants to notify a farmer, with no Firebase SDK or service-account
credential needed on the *backend* side at all (that credential only
has to be uploaded once to the Expo/EAS project itself, a one-time
console step). Needs no API key for this scale of traffic.

Never raises: a push failure must never break the request that
triggered it (a scan result, a fresh advisory) -- same never-raise
contract as every other external-API client in this project. A
``DeviceNotRegistered`` receipt (uninstalled app, stale token) is used
to self-clean the ``push_tokens`` table rather than ever retrying a
dead token forever.
"""
import logging

import requests

from agro_mirai.persistence.models import PushToken

logger = logging.getLogger(__name__)

_EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
_TIMEOUT_S = 10.0
_BATCH_SIZE = 100  # Expo's own documented per-request cap


def send_push_to_farmer(store, farmer_id: str, title: str, body: str, data: dict | None = None) -> int:
    """Sends one notification to every device a farmer has registered.
    Returns how many tokens it actually attempted (0 if the farmer has
    none registered, or the store has no push-token methods yet)."""
    try:
        tokens = store.list_push_tokens(farmer_id)
    except Exception as exc:  # the store/table not being ready must never block the caller
        logger.warning("push_client: could not list tokens for farmer=%s: %s", farmer_id, exc)
        return 0
    if not tokens:
        return 0
    send_push([t.token for t in tokens], title, body, data)
    return len(tokens)


def send_push(tokens: list[str], title: str, body: str, data: dict | None = None) -> None:
    """Sends one notification to a raw list of Expo push tokens, batching
    at Expo's documented 100-per-request limit. Never raises."""
    for i in range(0, len(tokens), _BATCH_SIZE):
        batch = tokens[i : i + _BATCH_SIZE]
        messages = [
            {
                "to": token,
                "title": title,
                "body": body,
                "data": data or {},
                "sound": "default",
                "priority": "high",
                "channelId": "alerts",
            }
            for token in batch
        ]
        try:
            resp = requests.post(
                _EXPO_PUSH_URL,
                json=messages,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=_TIMEOUT_S,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("push_client: send failed for a batch of %d: %s", len(batch), exc)
