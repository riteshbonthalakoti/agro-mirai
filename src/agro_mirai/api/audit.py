"""Shared audit-logging helper for every /v2/admin write route (Module
50). One place writes audit_log rows so no route can forget to; see
decisions/0017-multi-tenant-v2.md (superseded in part by this module's
own ADR) for why this dashboard is no longer read-only-only.
"""
from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import datetime, timezone


def write_audit_log(store, admin_farmer_id: str, action: str, target_type: str,
                     target_id: str, before=None, after=None) -> None:
    from agro_mirai.persistence.models import AuditLogEntry

    def _snapshot(record):
        if record is None:
            return None
        return json.dumps(dataclasses.asdict(record), default=str)

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
