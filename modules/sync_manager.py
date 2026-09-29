from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from modules.patient_db import PatientDatabase


class SyncManager:
    def __init__(self, database: PatientDatabase):
        self.database = database

    def add_pending_record(self, entity_type: str, entity_id: str, payload: dict[str, Any]) -> None:
        self.database.enqueue_sync(entity_type, entity_id, payload)

    def sync_pending(self) -> list[dict[str, Any]]:
        pending = self.database.get_pending_sync()
        for item in pending:
            self.database.mark_sync_done(item["id"])
        return pending

    def status(self) -> dict[str, Any]:
        stats = self.database.dashboard_stats()
        return {
            "pending_sync": stats["pending_sync"],
            "synced_records": stats["synced_records"],
            "offline_mode": True,
            "last_sync_check": datetime.utcnow().isoformat(timespec="seconds"),
        }
