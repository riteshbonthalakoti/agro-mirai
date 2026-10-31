"""Shared audit-logging helper for every /v2/admin write route (Module
50). One place writes audit_log rows so no route can forget to; see
decisions/0017-multi-tenant-v2.md (superseded in part by this module's
own ADR) for why this dashboard is no longer read-only-only.
"""
import dataclasses
import json
import uuid
from datetime import datetime, timezone


# Fields holding a full base64 data URI (no file-storage service exists
# yet, same reason across every model that has one) -- fine on the record
# itself, but an audit snapshot embedding the whole image on every edit is
# pure bloat nothing ever reads back out of an audit entry. Stripped to a
# boolean at write time; see strip_snapshot_photos() for the matching
# read-time cleanup of entries already stored before this existed.
_PHOTO_FIELDS = ("photo_url",)


def strip_snapshot_photos(d: dict) -> dict:
    for field in _PHOTO_FIELDS:
        if d.get(field):
            d[field] = f"<{field} omitted from audit snapshot, {len(d[field])} chars>"
    return d


def write_audit_log(store, admin_farmer_id: str, action: str, target_type: str,
                     target_id: str, before=None, after=None) -> None:
    from agro_mirai.persistence.models import AuditLogEntry

    def _snapshot(record):
        if record is None:
            return None
        return json.dumps(strip_snapshot_photos(dataclasses.asdict(record)), default=str)

    store.save_audit_log_entry(
        AuditLogEntry(
            id=str(uuid.uuid4()),
            admin_farmer_id=admin_farmer_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before_json=_snapshot(before),
            after_json=_snapshot(after),
            created_at=datetime.now(timezone.utc),
        )
    )
