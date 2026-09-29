from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any


class ReminderTypes:
    MEDICINE = "medicine"
    HYDRATION = "hydration"
    ACTIVITY = "activity"
    APPOINTMENT = "appointment"


REMINDER_COLORS = {
    ReminderTypes.MEDICINE: "medicine",
    ReminderTypes.HYDRATION: "hydration",
    ReminderTypes.ACTIVITY: "activity",
    ReminderTypes.APPOINTMENT: "appointment",
}

DEFAULT_REMINDERS = [
    {"type": ReminderTypes.MEDICINE, "title": "Morning Medicine", "time": "08:00", "recurrence": "daily"},
    {"type": ReminderTypes.HYDRATION, "title": "Drink Water", "time": "10:00", "recurrence": "daily"},
    {"type": ReminderTypes.ACTIVITY, "title": "Morning Walk", "time": "09:00", "recurrence": "daily"},
    {"type": ReminderTypes.MEDICINE, "title": "Evening Medicine", "time": "20:00", "recurrence": "daily"},
    {"type": ReminderTypes.HYDRATION, "title": "Afternoon Hydration", "time": "15:00", "recurrence": "daily"},
]


class ReminderService:
    def __init__(self, database):
        self.database = database

    def add_reminder(self, patient_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        reminder_id = payload.get("reminder_id") or f"RM-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        with self.database._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO reminders (
                    reminder_id, patient_id, reminder_type, title, message,
                    scheduled_time, recurrence, date, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reminder_id,
                    patient_id,
                    payload.get("reminder_type"),
                    payload.get("title"),
                    payload.get("message"),
                    payload.get("scheduled_time") or payload.get("time"),
                    payload.get("recurrence", "daily"),
                    payload.get("date"),
                    1 if payload.get("is_active", True) else 0,
                    created_at,
                ),
            )
            conn.commit()
        return self.get_reminder(reminder_id)

    def get_reminder(self, reminder_id: str) -> dict[str, Any] | None:
        with self.database._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reminders WHERE reminder_id = ?", (reminder_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_reminders(self, patient_id: str) -> list[dict[str, Any]]:
        with self.database._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE patient_id = ? ORDER BY scheduled_time, is_active DESC",
                (patient_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def toggle_reminder(self, reminder_id: str, active: bool) -> dict[str, Any]:
        with self.database._connect() as conn:
            conn.execute(
                "UPDATE reminders SET is_active = ? WHERE reminder_id = ?",
                (1 if active else 0, reminder_id),
            )
            conn.commit()
        return self.get_reminder(reminder_id)

    def delete_reminder(self, reminder_id: str) -> dict[str, Any]:
        with self.database._connect() as conn:
            conn.execute("DELETE FROM reminders WHERE reminder_id = ?", (reminder_id,))
            conn.commit()
        return {"deleted": True, "reminder_id": reminder_id}

    def seed_defaults(self, patient_id: str) -> int:
        existing = len(self.list_reminders(patient_id))
        if existing > 0:
            return existing
        for item in DEFAULT_REMINDERS:
            self.add_reminder(patient_id, {
                "reminder_type": item["type"],
                "title": item["title"],
                "scheduled_time": item["time"],
                "recurrence": item["recurrence"],
            })
        return len(self.list_reminders(patient_id))

    def due_reminders(self, patient_id: str, current_time: str | None = None) -> list[dict[str, Any]]:
        now = datetime.now()
        current = current_time or now.strftime("%H:%M")
        reminders = self.list_reminders(patient_id)
        due = []
        for r in reminders:
            if not r.get("is_active"):
                continue
            scheduled = r.get("scheduled_time") or ""
            if scheduled and scheduled[:5] == current[:5]:
                due.append(r)
        return due

    def log_triggered(self, reminder: dict[str, Any]) -> dict[str, Any]:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.database._connect() as conn:
            conn.execute(
                """
                INSERT INTO reminder_logs (reminder_id, patient_id, triggered_at, acknowledged, acknowledged_at)
                VALUES (?, ?, ?, 0, NULL)
                """,
                (
                    reminder["reminder_id"],
                    reminder.get("patient_id"),
                    now,
                ),
            )
            conn.execute(
                "UPDATE reminders SET last_triggered = ? WHERE reminder_id = ?",
                (now, reminder["reminder_id"]),
            )
            conn.commit()

        with self.database._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as total, SUM(CASE WHEN acknowledged = 1 THEN 1 ELSE 0 END) as ack
                FROM reminder_logs WHERE reminder_id = ?
                """,
                (reminder["reminder_id"],),
            ).fetchone()
        return {
            "reminder_id": reminder["reminder_id"],
            "total_triggers": row["total"],
            "acknowledged": row["ack"] or 0,
            "triggered_at": now,
        }

    def acknowledge(self, reminder_id: str) -> dict[str, Any]:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.database._connect() as conn:
            conn.execute(
                """
                UPDATE reminder_logs SET acknowledged = 1, acknowledged_at = ?
                WHERE reminder_id = ? AND acknowledged = 0
                """,
                (now, reminder_id),
            )
            conn.commit()
        return {"reminder_id": reminder_id, "acknowledged": True, "acknowledged_at": now}


class CaregiverAnalytics:
    def __init__(self, database):
        self.database = database

    def patient_summary(self, patient_id: str) -> dict[str, Any]:
        patient = self.database.get_cognitive_patient(patient_id)
        if not patient:
            return {"patient": None}
        dashboard = self.database.get_caregiver_dashboard(patient_id)
        return dashboard

    def list_patients(self) -> list[dict[str, Any]]:
        patients = self.database.list_cognitive_patients()
        result = []
        for p in patients:
            stats = self.database.get_patient_overall_stats(p["patient_id"])
            result.append({
                **p,
                "stats": stats,
            })
        return result

    def health_score(self, patient_id: str) -> float:
        stats = self.database.get_patient_overall_stats(patient_id)
        accuracy = stats.get("avg_accuracy", 0)
        trend_bonus = 0
        if stats.get("cognitive_trend") == "improving":
            trend_bonus = 5
        elif stats.get("cognitive_trend") == "declining":
            trend_bonus = -5
        return round(min(100, max(0, accuracy * 0.8 + trend_bonus)), 1)