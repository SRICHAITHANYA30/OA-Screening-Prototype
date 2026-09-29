from __future__ import annotations

from typing import Any

from modules.patient_db import PatientDatabase


def compute_dashboard_stats(db: PatientDatabase) -> dict[str, Any]:
    stats = db.dashboard_stats()
    return {
        "totalPatients": stats["total_patients"],
        "totalScreenings": stats["total_screenings"],
        "todayScreenings": stats["today_screenings"],
        "lowRisk": stats["low_risk"],
        "moderateRisk": stats["moderate_risk"],
        "highRisk": stats["high_risk"],
        "pendingSync": stats["pending_sync"],
        "syncedRecords": stats["synced_records"],
    }
