from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


import tempfile

try:
    DB_PATH = Path(__file__).resolve().parent.parent / "data" / "cognitive.db"
    DB_PATH.parent.mkdir(exist_ok=True)
except OSError:
    DB_PATH = Path(tempfile.gettempdir()) / "cognitive.db"


class CognitiveDatabase:
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
                CREATE TABLE IF NOT EXISTS cognitive_patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT UNIQUE NOT NULL,
                    name TEXT,
                    age INTEGER,
                    sex TEXT,
                    district TEXT,
                    state TEXT,
                    language TEXT DEFAULT 'en',
                    cognitive_level TEXT DEFAULT 'moderate',
                    caregiver_name TEXT,
                    caregiver_phone TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS game_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    patient_id TEXT NOT NULL,
                    game_type TEXT NOT NULL,
                    difficulty_level INTEGER DEFAULT 1,
                    score REAL DEFAULT 0,
                    max_score REAL DEFAULT 100,
                    completion_time_seconds REAL DEFAULT 0,
                    hints_used INTEGER DEFAULT 0,
                    accuracy_pct REAL DEFAULT 0,
                    adaptive_level REAL DEFAULT 1.0,
                    session_data TEXT,
                    completed INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cognitive_assessments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_id TEXT UNIQUE NOT NULL,
                    patient_id TEXT NOT NULL,
                    overall_score REAL DEFAULT 0,
                    memory_score REAL DEFAULT 0,
                    attention_score REAL DEFAULT 0,
                    recognition_score REAL DEFAULT 0,
                    recall_score REAL DEFAULT 0,
                    engagement_minutes REAL DEFAULT 0,
                    sessions_played INTEGER DEFAULT 0,
                    trend TEXT DEFAULT 'stable',
                    assessment_data TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reminder_id TEXT UNIQUE NOT NULL,
                    patient_id TEXT NOT NULL,
                    reminder_type TEXT NOT NULL,
                    title TEXT,
                    message TEXT,
                    scheduled_time TEXT,
                    recurrence TEXT DEFAULT 'daily',
                    is_active INTEGER DEFAULT 1,
                    last_triggered TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminder_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reminder_id TEXT NOT NULL,
                    patient_id TEXT NOT NULL,
                    triggered_at TEXT,
                    acknowledged INTEGER DEFAULT 0,
                    acknowledged_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    activity_date TEXT NOT NULL,
                    games_played INTEGER DEFAULT 0,
                    total_score REAL DEFAULT 0,
                    engagement_minutes REAL DEFAULT 0,
                    mood TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cognitive_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'patient',
                    language TEXT DEFAULT 'en',
                    patient_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_feed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    activity_detail TEXT,
                    score REAL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS caregiver_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    caregiver_phone TEXT NOT NULL,
                    patient_id TEXT,
                    notification_type TEXT,
                    detail TEXT,
                    is_read INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Add new columns to already-created tables (idempotent, SQLite 3.35+)."""
        checks = [
            ("cognitive_users", "pin", "TEXT"),
            ("cognitive_patients", "coins_balance", "REAL DEFAULT 0"),
            ("game_sessions", "coins_earned", "REAL DEFAULT 0"),
            ("game_sessions", "total_questions", "INTEGER DEFAULT 0"),
            ("game_sessions", "correct_answers", "INTEGER DEFAULT 0"),
            ("game_sessions", "language", "TEXT DEFAULT 'en'"),
            ("reminders", "date", "TEXT"),
        ]
        for table, column, decl in checks:
            exists = conn.execute(
                "SELECT COUNT(*) FROM pragma_table_info(?) WHERE name = ?",
                (table, column),
            ).fetchone()[0]
            if not exists:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        conn.commit()

    def register_cognitive_patient(self, payload: dict[str, Any]) -> dict[str, Any]:
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cognitive_patients (
                    patient_id, name, age, sex, district, state,
                    language, cognitive_level, caregiver_name, caregiver_phone, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("patient_id"),
                    payload.get("name"),
                    payload.get("age"),
                    payload.get("sex"),
                    payload.get("district"),
                    payload.get("state"),
                    payload.get("language", "en"),
                    payload.get("cognitive_level", "moderate"),
                    payload.get("caregiver_name"),
                    payload.get("caregiver_phone"),
                    created_at,
                ),
            )
            conn.commit()
        return self.get_cognitive_patient(payload.get("patient_id"))

    def get_cognitive_patient(self, patient_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM cognitive_patients WHERE patient_id = ?", (patient_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_cognitive_patients(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM cognitive_patients ORDER BY created_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    def save_game_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = payload.get("session_id") or f"GS-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:20]}"
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO game_sessions (
                    session_id, patient_id, game_type, difficulty_level,
                    score, max_score, completion_time_seconds, hints_used,
                    accuracy_pct, adaptive_level, session_data, completed, created_at,
                    coins_earned, total_questions, correct_answers, language
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    payload.get("patient_id"),
                    payload.get("game_type"),
                    payload.get("difficulty_level", 1),
                    payload.get("score", 0),
                    payload.get("max_score", 100),
                    payload.get("completion_time_seconds", 0),
                    payload.get("hints_used", 0),
                    payload.get("accuracy_pct", 0),
                    payload.get("adaptive_level", 1.0),
                    json.dumps(payload.get("session_data")),
                    1 if payload.get("completed") else 0,
                    created_at,
                    payload.get("coins_earned", 0),
                    payload.get("total_questions", 0),
                    payload.get("correct_answers", 0),
                    payload.get("language", "en"),
                ),
            )
            conn.commit()
        return self.get_game_session(session_id)

    def session_exists(self, session_id: str) -> bool:
        if not session_id:
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM game_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return row is not None

    def get_game_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM game_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_sessions_for_patient(self, patient_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM game_sessions WHERE patient_id = ? ORDER BY created_at DESC LIMIT ?",
                (patient_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_game_type_stats(self, patient_id: str, game_type: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) as total_sessions,
                    AVG(score) as avg_score,
                    AVG(accuracy_pct) as avg_accuracy,
                    AVG(completion_time_seconds) as avg_time,
                    AVG(difficulty_level) as avg_difficulty,
                    AVG(adaptive_level) as current_adaptive_level,
                    MAX(score) as best_score
                FROM game_sessions
                WHERE patient_id = ? AND game_type = ? AND completed = 1
                """,
                (patient_id, game_type),
            ).fetchone()
            return dict(row) if row else {}

    def get_patient_overall_stats(self, patient_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            sessions = conn.execute(
                "SELECT * FROM game_sessions WHERE patient_id = ? ORDER BY created_at DESC",
                (patient_id,),
            ).fetchall()
            sessions = [dict(row) for row in sessions]

            total = len(sessions)
            completed = sum(1 for s in sessions if s.get("completed"))
            avg_score = sum(s.get("score", 0) for s in sessions) / max(total, 1)
            avg_accuracy = sum(s.get("accuracy_pct", 0) for s in sessions) / max(total, 1)
            total_time = sum(s.get("completion_time_seconds", 0) for s in sessions)

            game_breakdown = {}
            for s in sessions:
                gtype = s.get("game_type", "unknown")
                if gtype not in game_breakdown:
                    game_breakdown[gtype] = {"count": 0, "total_score": 0}
                game_breakdown[gtype]["count"] += 1
                game_breakdown[gtype]["total_score"] += s.get("score", 0)

            recent_scores = []
            for s in sessions[:20]:
                recent_scores.append({
                    "game_type": s.get("game_type"),
                    "score": s.get("score"),
                    "date": s.get("created_at"),
                    "difficulty": s.get("difficulty_level"),
                })

            if total >= 3:
                recent_avg = sum(s.get("score", 0) for s in sessions[:5]) / min(5, total)
                older_avg = sum(s.get("score", 0) for s in sessions[5:15]) / max(min(10, total - 5), 1)
                if recent_avg > older_avg * 1.1:
                    trend = "improving"
                elif recent_avg < older_avg * 0.9:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"

            return {
                "patient_id": patient_id,
                "total_sessions": total,
                "completed_sessions": completed,
                "avg_score": round(avg_score, 1),
                "avg_accuracy": round(avg_accuracy, 1),
                "total_time_minutes": round(total_time / 60, 1),
                "game_breakdown": game_breakdown,
                "recent_scores": recent_scores,
                "cognitive_trend": trend,
            }

    def save_assessment(self, payload: dict[str, Any]) -> dict[str, Any]:
        assessment_id = payload.get("assessment_id") or f"CA-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cognitive_assessments (
                    assessment_id, patient_id, overall_score, memory_score,
                    attention_score, recognition_score, recall_score,
                    engagement_minutes, sessions_played, trend, assessment_data, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    payload.get("patient_id"),
                    payload.get("overall_score", 0),
                    payload.get("memory_score", 0),
                    payload.get("attention_score", 0),
                    payload.get("recognition_score", 0),
                    payload.get("recall_score", 0),
                    payload.get("engagement_minutes", 0),
                    payload.get("sessions_played", 0),
                    payload.get("trend", "stable"),
                    json.dumps(payload.get("assessment_data")),
                    created_at,
                ),
            )
            conn.commit()
        return {"assessment_id": assessment_id, "created_at": created_at}

    def get_assessments_for_patient(self, patient_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM cognitive_assessments WHERE patient_id = ? ORDER BY created_at DESC LIMIT 30",
                (patient_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def save_daily_activity(self, payload: dict[str, Any]) -> dict[str, Any]:
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM daily_activities WHERE patient_id = ? AND activity_date = ?",
                (payload.get("patient_id"), datetime.utcnow().strftime("%Y-%m-%d")),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE daily_activities SET
                        games_played = games_played + ?,
                        total_score = total_score + ?,
                        engagement_minutes = engagement_minutes + ?,
                        mood = COALESCE(?, mood)
                    WHERE id = ?
                    """,
                    (
                        payload.get("games_played", 1),
                        payload.get("total_score", 0),
                        payload.get("engagement_minutes", 0),
                        payload.get("mood"),
                        existing["id"],
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO daily_activities (
                        patient_id, activity_date, games_played, total_score,
                        engagement_minutes, mood, notes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload.get("patient_id"),
                        datetime.utcnow().strftime("%Y-%m-%d"),
                        payload.get("games_played", 1),
                        payload.get("total_score", 0),
                        payload.get("engagement_minutes", 0),
                        payload.get("mood"),
                        payload.get("notes"),
                        created_at,
                    ),
                )
            conn.commit()
        return {"status": "saved", "date": datetime.utcnow().strftime("%Y-%m-%d")}

    def get_daily_activities(self, patient_id: str, days: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM daily_activities
                WHERE patient_id = ?
                ORDER BY activity_date DESC
                LIMIT ?
                """,
                (patient_id, days),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_caregiver_dashboard(self, patient_id: str) -> dict[str, Any]:
        patient = self.get_cognitive_patient(patient_id)
        overall = self.get_patient_overall_stats(patient_id)
        assessments = self.get_assessments_for_patient(patient_id)
        recent_sessions = self.get_sessions_for_patient(patient_id, limit=10)
        daily = self.get_daily_activities(patient_id, days=7)

        with self._connect() as conn:
            active_reminders = conn.execute(
                "SELECT COUNT(*) as cnt FROM reminders WHERE patient_id = ? AND is_active = 1",
                (patient_id,),
            ).fetchone()

        today = self.get_today_stats(patient_id)
        return {
            "patient": patient,
            "overall_stats": overall,
            "latest_assessment": assessments[0] if assessments else None,
            "recent_sessions": recent_sessions,
            "weekly_activity": daily,
            "active_reminders": active_reminders["cnt"] if active_reminders else 0,
            "coins_balance": self.get_patient_coins(patient_id),
            "coins_today": today["coins_today"],
            "games_today": today["games_today"],
            "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        }

    def caregiver_dashboard_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            total_patients = conn.execute("SELECT COUNT(*) FROM cognitive_patients").fetchone()[0]
            total_sessions = conn.execute("SELECT COUNT(*) FROM game_sessions").fetchone()[0]
            today_sessions = conn.execute(
                "SELECT COUNT(*) FROM game_sessions WHERE date(created_at) = date('now')"
            ).fetchone()[0]
            avg_score = conn.execute(
                "SELECT AVG(score) FROM game_sessions WHERE completed = 1"
            ).fetchone()[0] or 0
            active_reminders = conn.execute(
                "SELECT COUNT(*) FROM reminders WHERE is_active = 1"
            ).fetchone()[0]
            improving = conn.execute(
                """
                SELECT COUNT(DISTINCT patient_id) FROM cognitive_assessments
                WHERE trend = 'improving'
                """
            ).fetchone()[0]

        return {
            "total_patients": total_patients,
            "total_sessions": total_sessions,
            "today_sessions": today_sessions,
            "avg_score": round(avg_score, 1),
            "active_reminders": active_reminders,
            "improving_patients": improving,
        }

    def login_user(self, phone: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM cognitive_users WHERE phone = ?", (phone,)
            ).fetchone()
            return dict(row) if row else None

    def verify_login(self, phone: str, pin: str) -> tuple[str, dict[str, Any] | None]:
        """Verify phone + PIN credentials.
        Returns (status, user): status is 'ok', 'not_found', 'wrong_pin'."""
        user = self.login_user(phone)
        if not user:
            return "not_found", None
        stored = (user.get("pin") or "").strip()
        if not stored:
            return "wrong_pin", user
        if stored != (pin or "").strip():
            return "wrong_pin", user
        return "ok", user

    def register_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cognitive_users (
                    phone, name, role, language, patient_id, pin, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("phone"),
                    payload.get("name"),
                    payload.get("role", "patient"),
                    payload.get("language", "en"),
                    payload.get("patient_id"),
                    payload.get("pin"),
                    created_at,
                ),
            )
            conn.commit()
        return self.get_user_by_phone(payload.get("phone"))

    def get_user_by_phone(self, phone: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM cognitive_users WHERE phone = ?", (phone,)
            ).fetchone()
            return dict(row) if row else None

    def add_activity_feed(self, patient_id: str, activity_type: str, detail: str = "", score: float = 0) -> dict[str, Any]:
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO activity_feed (patient_id, activity_type, activity_detail, score, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (patient_id, activity_type, detail, score, created_at),
            )
            conn.commit()
        return {"status": "ok", "created_at": created_at}

    def get_activity_feed(self, patient_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM activity_feed WHERE patient_id = ? ORDER BY created_at DESC LIMIT ?",
                (patient_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Coins
    # ------------------------------------------------------------------
    def get_patient_coins(self, patient_id: str) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT coins_balance FROM cognitive_patients WHERE patient_id = ?",
                (patient_id,),
            ).fetchone()
            return float(row["coins_balance"]) if row and row["coins_balance"] else 0.0

    def add_coins(self, patient_id: str, amount: float) -> float:
        with self._connect() as conn:
            conn.execute(
                "UPDATE cognitive_patients SET coins_balance = COALESCE(coins_balance, 0) + ? WHERE patient_id = ?",
                (amount, patient_id),
            )
            conn.commit()
        return self.get_patient_coins(patient_id)

    def get_today_stats(self, patient_id: str) -> dict[str, Any]:
        """Games played today and coins earned today."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as games_today, COALESCE(SUM(coins_earned), 0) as coins_today
                FROM game_sessions
                WHERE patient_id = ? AND completed = 1 AND date(created_at) = ?
                """,
                (patient_id, today),
            ).fetchone()
            return {
                "games_today": row["games_today"] if row else 0,
                "coins_today": round(row["coins_today"], 0) if row else 0,
            }

    def get_activity_feed_for_caregiver(self, caregiver_phone: str, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            patient_ids = [
                r["patient_id"]
                for r in conn.execute(
                    "SELECT patient_id FROM cognitive_patients WHERE caregiver_phone = ?",
                    (caregiver_phone,),
                ).fetchall()
            ] or [""]
            marks = ",".join("?" for _ in patient_ids)
            rows = conn.execute(
                f"SELECT * FROM activity_feed WHERE patient_id IN ({marks}) ORDER BY created_at DESC LIMIT ?",
                (*patient_ids, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Caregiver notifications
    # ------------------------------------------------------------------
    def add_caregiver_notification(self, caregiver_phone: str, patient_id: str | None,
                                   notification_type: str, detail: str) -> dict[str, Any]:
        if not caregiver_phone:
            return {"status": "skipped"}
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO caregiver_notifications (caregiver_phone, patient_id, notification_type, detail, is_read, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (caregiver_phone, patient_id, notification_type, detail, created_at),
            )
            conn.commit()
        return {"status": "ok", "created_at": created_at}

    def list_caregiver_notifications(self, caregiver_phone: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM caregiver_notifications
                WHERE caregiver_phone = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (caregiver_phone, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def count_unread_notifications(self, caregiver_phone: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM caregiver_notifications WHERE caregiver_phone = ? AND is_read = 0",
                (caregiver_phone,),
            ).fetchone()
            return row["cnt"] if row else 0

    def mark_notifications_read(self, caregiver_phone: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE caregiver_notifications SET is_read = 1 WHERE caregiver_phone = ? AND is_read = 0",
                (caregiver_phone,),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Caregiver scope
    # ------------------------------------------------------------------
    def get_patients_for_caregiver(self, caregiver_phone: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM cognitive_patients
                WHERE caregiver_phone = ?
                ORDER BY created_at DESC
                """,
                (caregiver_phone,),
            ).fetchall()
            return [dict(row) for row in rows]
