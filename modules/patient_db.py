from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


import tempfile

try:
    DB_PATH = Path(__file__).resolve().parent.parent / "data" / "patients.db"
    DB_PATH.parent.mkdir(exist_ok=True)
except OSError:
    DB_PATH = Path(tempfile.gettempdir()) / "patients.db"


class PatientDatabase:
    def __init__(self, database_path: str | Path | None = None):
        self.database_path = Path(database_path) if database_path else DB_PATH
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.database_path = Path(tempfile.gettempdir()) / self.database_path.name
        self._initialize_db()


    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT UNIQUE NOT NULL,
                    name TEXT,
                    age INTEGER,
                    sex TEXT,
                    location TEXT,
                    district TEXT,
                    state TEXT,
                    occupation TEXT,
                    height REAL,
                    weight REAL,
                    bmi REAL,
                    oa_history TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS screenings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screening_id TEXT UNIQUE NOT NULL,
                    patient_id TEXT NOT NULL,
                    screening_date TEXT NOT NULL,
                    pain_score REAL,
                    mobility_score REAL,
                    left_knee_angle REAL,
                    right_knee_angle REAL,
                    symmetry_pct REAL,
                    risk_score REAL,
                    risk_level TEXT,
                    ai_status TEXT,
                    notes TEXT,
                    file_path TEXT,
                    sync_status TEXT DEFAULT 'PENDING',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pain_mobility (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screening_id TEXT NOT NULL,
                    pain_score REAL,
                    stiffness_score REAL,
                    mobility_score REAL,
                    previous_injury TEXT,
                    family_history TEXT,
                    activity_level TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS movement_features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screening_id TEXT NOT NULL,
                    left_knee_angle REAL,
                    right_knee_angle REAL,
                    knee_angle_range REAL,
                    symmetry_pct REAL,
                    pose_confidence REAL,
                    valid_frames INTEGER,
                    movement_consistency REAL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sensor_features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screening_id TEXT NOT NULL,
                    sensor_connected INTEGER DEFAULT 0,
                    sensor_type TEXT,
                    accelerometer TEXT,
                    gyroscope TEXT,
                    step_count INTEGER,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ml_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screening_id TEXT NOT NULL,
                    model_name TEXT,
                    model_status TEXT,
                    prediction_json TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screening_id TEXT NOT NULL,
                    report_path TEXT,
                    report_text TEXT,
                    generated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    attempts INTEGER DEFAULT 0
                )
                """
            )
            conn.commit()

    def register_patient(self, payload: dict[str, Any]) -> dict[str, Any]:
        patient_id = payload.get("patient_id") or self._new_patient_id()
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        bmi = payload.get("bmi")
        if bmi is None:
            weight = payload.get("weight")
            height = payload.get("height")
            if weight and height:
                bmi = float(weight) / ((float(height) / 100.0) ** 2)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO patients (
                    patient_id, name, age, sex, location, district, state, occupation,
                    height, weight, bmi, oa_history, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    patient_id,
                    payload.get("name"),
                    payload.get("age"),
                    payload.get("sex"),
                    payload.get("location"),
                    payload.get("district"),
                    payload.get("state"),
                    payload.get("occupation"),
                    payload.get("height"),
                    payload.get("weight"),
                    bmi,
                    payload.get("oa_history"),
                    created_at,
                ),
            )
            conn.commit()
        return self.get_patient(patient_id)

    def get_patient(self, patient_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
            if row is None:
                return None
            return dict(row)

    def list_patients(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM patients ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def save_screening(self, payload: dict[str, Any]) -> dict[str, Any]:
        screening_id = payload.get("screening_id") or self._new_screening_id()
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO screenings (
                    screening_id, patient_id, screening_date, pain_score, mobility_score,
                    left_knee_angle, right_knee_angle, symmetry_pct, risk_score, risk_level,
                    ai_status, notes, file_path, sync_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    screening_id,
                    payload.get("patient_id"),
                    payload.get("screening_date") or created_at,
                    payload.get("pain_score"),
                    payload.get("mobility_score"),
                    payload.get("left_knee_angle"),
                    payload.get("right_knee_angle"),
                    payload.get("symmetry_pct"),
                    payload.get("risk_score"),
                    payload.get("risk_level"),
                    payload.get("ai_status"),
                    payload.get("notes"),
                    payload.get("file_path"),
                    payload.get("sync_status") or "PENDING",
                    created_at,
                ),
            )
            conn.commit()
        return self.get_screening(screening_id)

    def get_screening(self, screening_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM screenings WHERE screening_id = ?", (screening_id,)).fetchone()
            if row is None:
                return None
            return dict(row)

    def get_screenings_for_patient(self, patient_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM screenings WHERE patient_id = ? ORDER BY created_at DESC", (patient_id,)).fetchall()
            return [dict(row) for row in rows]

    def list_screenings(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM screenings ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def save_movement_features(self, screening_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO movement_features (
                    screening_id, left_knee_angle, right_knee_angle, knee_angle_range,
                    symmetry_pct, pose_confidence, valid_frames, movement_consistency, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    screening_id,
                    payload.get("left_knee_angle"),
                    payload.get("right_knee_angle"),
                    payload.get("knee_angle_range"),
                    payload.get("symmetry_pct"),
                    payload.get("pose_confidence"),
                    payload.get("valid_frames"),
                    payload.get("movement_consistency"),
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
            conn.commit()

    def save_sensor_features(self, screening_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sensor_features (
                    screening_id, sensor_connected, sensor_type,
                    accelerometer, gyroscope, step_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    screening_id,
                    1 if payload.get("sensor_connected") else 0,
                    payload.get("sensor_type"),
                    json.dumps(payload.get("accelerometer")) if payload.get("accelerometer") else None,
                    json.dumps(payload.get("gyroscope")) if payload.get("gyroscope") else None,
                    payload.get("step_count"),
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
            conn.commit()

    def save_ml_prediction(self, screening_id: str, model_name: str, status: str, prediction: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO ml_predictions (screening_id, model_name, model_status, prediction_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (screening_id, model_name, status, json.dumps(prediction), datetime.utcnow().isoformat(timespec="seconds")),
            )
            conn.commit()

    def save_report(self, screening_id: str, report_path: str, report_text: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO reports (screening_id, report_path, report_text, generated_at) VALUES (?, ?, ?, ?)",
                (screening_id, report_path, report_text, datetime.utcnow().isoformat(timespec="seconds")),
            )
            conn.commit()

    def enqueue_sync(self, entity_type: str, entity_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sync_queue (entity_type, entity_id, payload, created_at, status) VALUES (?, ?, ?, ?, 'PENDING')",
                (entity_type, entity_id, json.dumps(payload), datetime.utcnow().isoformat(timespec="seconds")),
            )
            conn.commit()

    def get_pending_sync(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM sync_queue WHERE status = 'PENDING' ORDER BY created_at ASC").fetchall()
            return [dict(row) for row in rows]

    def mark_sync_done(self, sync_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE sync_queue SET status = 'SYNCED' WHERE id = ?", (sync_id,))
            conn.commit()

    def dashboard_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            total_patients = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
            total_screenings = conn.execute("SELECT COUNT(*) FROM screenings").fetchone()[0]
            today_screenings = conn.execute(
                "SELECT COUNT(*) FROM screenings WHERE date(screening_date) = date('now')",
            ).fetchone()[0]
            low_risk = conn.execute("SELECT COUNT(*) FROM screenings WHERE risk_level = 'LOW' OR risk_level IS NULL").fetchone()[0]
            moderate_risk = conn.execute("SELECT COUNT(*) FROM screenings WHERE risk_level = 'MODERATE'").fetchone()[0]
            high_risk = conn.execute("SELECT COUNT(*) FROM screenings WHERE risk_level = 'HIGH'").fetchone()[0]
            pending_sync = conn.execute("SELECT COUNT(*) FROM sync_queue WHERE status = 'PENDING'").fetchone()[0]
            synced = conn.execute("SELECT COUNT(*) FROM sync_queue WHERE status = 'SYNCED'").fetchone()[0]
        return {
            "total_patients": total_patients,
            "total_screenings": total_screenings,
            "today_screenings": today_screenings,
            "low_risk": low_risk,
            "moderate_risk": moderate_risk,
            "high_risk": high_risk,
            "pending_sync": pending_sync,
            "synced_records": synced,
        }

    @staticmethod
    def _new_patient_id() -> str:
        return f"PT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    @staticmethod
    def _new_screening_id() -> str:
        return f"SCR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
