from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from modules.analytics import compute_dashboard_stats
from modules.cognitive_db import CognitiveDatabase
from modules.cognitive_games import CognitiveGameEngine, default_assessment
from modules.ml_model import LightGBMModelManager
from modules.ner_translations import ner_translations
from modules.patient_db import PatientDatabase
from modules.reminders import CaregiverAnalytics, ReminderService
from modules.security import privacy_notice, sanitize_text, validate_patient_payload, validate_upload
from modules.sync_manager import SyncManager
from modules.translations import TranslationService
from screening_core import PROCESSED_DIR, KneeRiskAnalyzer


PROJECT_ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = PROJECT_ROOT / "uploads"
REPORTS_DIR = PROJECT_ROOT / "reports"
UPLOAD_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "avi", "mov", "mkv", "wmv", "webm"}

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

analyzer = KneeRiskAnalyzer()
db = PatientDatabase()
sync_manager = SyncManager(db)
translator = TranslationService()
ml_model = LightGBMModelManager()
cognitive_db = CognitiveDatabase()
cognitive_games = CognitiveGameEngine()
reminder_service = ReminderService(cognitive_db)
caregiver_analytics = CaregiverAnalytics(cognitive_db)

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except Exception:  # pragma: no cover
    canvas = None
    letter = None


def _generate_text_report(patient: dict | None, screening: dict | None) -> str:
    if not patient or not screening:
        return "Screening report not available."
    risk_label = screening.get("risk_level") or "UNKNOWN"
    return (
        f"SwasthGati Preliminary OA Screening Report\n"
        f"Patient ID: {patient.get('patient_id', '-')}\n"
        f"Name: {patient.get('name', '-')}\n"
        f"Age/Sex: {patient.get('age', '-')} / {patient.get('sex', '-')}\n"
        f"Location: {patient.get('district', '-')}, {patient.get('state', '-')}\n\n"
        f"Clinical results\n"
        f"Pain score: {screening.get('pain_score', '-')}, Mobility score: {screening.get('mobility_score', '-')}\n"
        f"Left knee angle: {screening.get('left_knee_angle', '-')}, Right knee angle: {screening.get('right_knee_angle', '-')}\n"
        f"Symmetry: {screening.get('symmetry_pct', '-')}%\n"
        f"Risk level: {risk_label}\n"
        f"AI status: {screening.get('ai_status', 'AI model not trained / OAI dataset unavailable.')}\n\n"
        f"""Medical disclaimer: AI-assisted screening only — not a medical diagnosis.
This preliminary assessment is intended to support field screening and clinical review.
"""
    )


def _write_pdf_report(report_path: Path, patient: dict | None, screening: dict | None) -> None:
    if canvas is None:
        return
    c = canvas.Canvas(str(report_path), pagesize=letter)
    c.setTitle('SwasthGati Preliminary Screening Report')
    c.setFont('Helvetica-Bold', 16)
    c.drawString(72, 760, 'SwasthGati Preliminary OA Screening Report')
    c.setFont('Helvetica', 11)
    c.drawString(72, 740, f"Patient ID: {patient.get('patient_id') if patient else '-'}")
    c.drawString(72, 725, f"Name: {patient.get('name') if patient else '-'}")
    c.drawString(72, 710, f"Age/Sex: {patient.get('age') if patient else '-'} / {patient.get('sex') if patient else '-'}")
    c.drawString(72, 695, f"Location: {patient.get('district') if patient else '-'} / {patient.get('state') if patient else '-'}")
    c.drawString(72, 680, f"Risk level: {screening.get('risk_level') if screening else '-'}")
    c.drawString(72, 665, f"AI status: {screening.get('ai_status') if screening else '-'}")
    c.drawString(72, 650, 'Medical disclaimer: AI-assisted screening only — not a medical diagnosis.')
    c.save()


def _write_cognitive_pdf_report(report_path: Path, patient: dict | None, stats: dict | None, sessions: list | None, assessment: dict | None) -> None:
    if canvas is None:
        return
    c = canvas.Canvas(str(report_path), pagesize=letter)
    c.setTitle('Smirthi Cognitive Health Report')
    y = 760
    c.setFont('Helvetica-Bold', 18)
    c.drawString(72, y, 'Smirthi Cognitive Health Report')
    y -= 30
    c.setFont('Helvetica', 11)
    if patient:
        c.drawString(72, y, f"Patient: {patient.get('name', '-')} ({patient.get('patient_id', '-')})")
        y -= 18
        c.drawString(72, y, f"Age: {patient.get('age', '-')}  |  District: {patient.get('district', '-')}  |  State: {patient.get('state', '-')}")
        y -= 18
        c.drawString(72, y, f"Caregiver: {patient.get('caregiver_name', '-')}  |  Phone: {patient.get('caregiver_phone', '-')}")
        y -= 28
    if stats:
        c.setFont('Helvetica-Bold', 13)
        c.drawString(72, y, 'Overall Statistics')
        y -= 18
        c.setFont('Helvetica', 11)
        c.drawString(72, y, f"Total Sessions: {stats.get('total_sessions', 0)}")
        y -= 16
        c.drawString(72, y, f"Average Score: {stats.get('avg_score', 0)}")
        y -= 16
        c.drawString(72, y, f"Average Accuracy: {stats.get('avg_accuracy', 0)}%")
        y -= 16
        c.drawString(72, y, f"Total Time: {stats.get('total_time_minutes', 0)} minutes")
        y -= 16
        c.drawString(72, y, f"Cognitive Trend: {stats.get('cognitive_trend', 'N/A')}")
        y -= 28
    if sessions:
        c.setFont('Helvetica-Bold', 13)
        c.drawString(72, y, 'Recent Sessions')
        y -= 18
        c.setFont('Helvetica', 10)
        for s in sessions[:15]:
            if y < 60:
                c.showPage()
                y = 760
            line = f"  {s.get('game_type', '-')}  |  Score: {s.get('score', 0)}  |  Accuracy: {s.get('accuracy_pct', 0)}%  |  Lv {s.get('difficulty_level', 1)}"
            c.drawString(72, y, line)
            y -= 14
        y -= 14
    if assessment:
        c.setFont('Helvetica-Bold', 13)
        c.drawString(72, y, 'Latest Assessment')
        y -= 18
        c.setFont('Helvetica', 11)
        c.drawString(72, y, f"Overall: {assessment.get('overall_score', 0)}  |  Memory: {assessment.get('memory_score', 0)}  |  Attention: {assessment.get('attention_score', 0)}")
        y -= 16
        c.drawString(72, y, f"Recognition: {assessment.get('recognition_score', 0)}  |  Recall: {assessment.get('recall_score', 0)}")
        y -= 24
    c.setFont('Helvetica-Oblique', 9)
    c.drawString(72, max(y, 40), 'Generated by Smirthi Cognitive Companion. This is not a medical diagnosis.')
    c.save()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/dashboard")
def dashboard_api():
    return jsonify(compute_dashboard_stats(db))


@app.route("/api/patients", methods=["GET", "POST"])
def patients_api():
    if request.method == "GET":
        return jsonify({"patients": db.list_patients()})

    payload = request.get_json(silent=True) or {}
    ok, error = validate_patient_payload(payload)
    if not ok:
        return jsonify({"success": False, "message": error}), 400

    patient = db.register_patient({
        "patient_id": sanitize_text(payload.get("patient_id")),
        "name": sanitize_text(payload.get("name")),
        "age": payload.get("age"),
        "sex": sanitize_text(payload.get("sex")),
        "location": sanitize_text(payload.get("location")),
        "district": sanitize_text(payload.get("district")),
        "state": sanitize_text(payload.get("state")),
        "occupation": sanitize_text(payload.get("occupation")),
        "height": payload.get("height"),
        "weight": payload.get("weight"),
        "bmi": payload.get("bmi"),
        "oa_history": sanitize_text(payload.get("oa_history")),
    })
    sync_manager.add_pending_record("patient", patient["patient_id"], patient)
    return jsonify({"success": True, "patient": patient})


@app.route("/api/patient/<patient_id>")
def patient_detail_api(patient_id: str):
    patient = db.get_patient(patient_id)
    screenings = db.get_screenings_for_patient(patient_id)
    return jsonify({"patient": patient, "screenings": screenings})


@app.route("/api/screenings")
def screenings_api():
    return jsonify({"screenings": db.list_screenings()})


@app.route("/api/screening", methods=["POST"])
def save_screening_api():
    payload = request.get_json(silent=True) or {}
    patient_id = payload.get("patient_id")
    if not patient_id:
        return jsonify({"success": False, "message": "Patient ID is required."}), 400

    patient = db.get_patient(patient_id)
    if not patient:
        return jsonify({"success": False, "message": "Patient not found. Register the patient first."}), 404

    ai_status = "AI model not trained / OAI dataset unavailable."
    ai_payload = {"available": False, "status": ai_status, "risk_level": "UNKNOWN"}
    feature_payload = {
        "age": float(patient.get("age") or 0),
        "pain_score": float(payload.get("pain_score") or 0),
        "mobility_score": float(payload.get("mobility_score") or 0),
        "stiffness_score": float(payload.get("stiffness_score") or 0),
        "bmi": float(patient.get("bmi") or payload.get("bmi") or 0),
    }
    if ml_model.available():
        ai_payload = ml_model.predict_from_features(feature_payload)
        ai_status = ai_payload.get("status")
    result_payload = {
        "patient_id": patient_id,
        "screening_id": payload.get("screening_id") or db._new_screening_id(),
        "screening_date": datetime.utcnow().isoformat(timespec="seconds"),
        "pain_score": payload.get("pain_score"),
        "mobility_score": payload.get("mobility_score"),
        "left_knee_angle": payload.get("left_knee_angle"),
        "right_knee_angle": payload.get("right_knee_angle"),
        "symmetry_pct": payload.get("symmetry_pct"),
        "risk_score": payload.get("risk_score") or ai_payload.get("risk_score"),
        "risk_level": payload.get("risk_level") or ai_payload.get("risk_level"),
        "ai_status": ai_status,
        "notes": sanitize_text(payload.get("notes")),
        "file_path": payload.get("file_path"),
        "sync_status": "PENDING",
    }

    screening = db.save_screening(result_payload)
    if payload.get("movement_features"):
        db.save_movement_features(screening["screening_id"], payload["movement_features"])
    if payload.get("sensor_features"):
        db.save_sensor_features(screening["screening_id"], payload["sensor_features"])
    db.save_ml_prediction(screening["screening_id"], "lightgbm", ai_status, ai_payload)
    sync_manager.add_pending_record("screening", screening["screening_id"], screening)

    report_text = _generate_text_report(patient, screening)
    report_path = REPORTS_DIR / f"{screening['screening_id']}.txt"
    report_path.write_text(report_text, encoding="utf-8")
    db.save_report(screening["screening_id"], str(report_path), report_text)

    return jsonify({"success": True, "screening": screening, "ai_prediction": ai_payload, "privacy_notice": privacy_notice()})


@app.route("/api/analytics")
def analytics_api():
    return jsonify({"analytics": compute_dashboard_stats(db), "privacy_notice": privacy_notice()})


@app.route("/api/sync-status")
def sync_status_api():
    return jsonify(sync_manager.status())


@app.route("/api/report/<screening_id>")
def report_api(screening_id: str):
    screening = db.get_screening(screening_id)
    patient = db.get_patient(screening["patient_id"]) if screening else None
    report_text = _generate_text_report(patient, screening)
    report_path = REPORTS_DIR / f"{screening_id}.txt"
    report_path.write_text(report_text, encoding="utf-8")
    return jsonify({"screening_id": screening_id, "report": report_text, "path": str(report_path)})


@app.route("/api/report/<screening_id>/pdf")
def report_pdf_api(screening_id: str):
    screening = db.get_screening(screening_id)
    patient = db.get_patient(screening["patient_id"]) if screening else None
    report_text = _generate_text_report(patient, screening)
    pdf_path = REPORTS_DIR / f"{screening_id}.pdf"
    _write_pdf_report(pdf_path, patient, screening)
    if not pdf_path.exists():
        pdf_path.write_bytes(b'')
    return jsonify({"screening_id": screening_id, "pdf_path": str(pdf_path), "status": "generated" if pdf_path.exists() else "not_available"})


@app.route("/api/analyze-frame", methods=["POST"])
def analyze_frame_api():
    if "frame" not in request.files:
        return jsonify({"success": False, "message": "No frame was received."}), 400

    frame_file = request.files["frame"]
    image_bytes = frame_file.read()
    result = analyzer.analyze_image_bytes(image_bytes)
    return jsonify({"success": True, "result": result.to_dict()})


@app.route("/api/analyze-image", methods=["POST"])
def analyze_image_api():
    image_file = request.files.get("image")
    if image_file is None or image_file.filename == "":
        return jsonify({"success": False, "message": "Please choose a photo."}), 400

    is_valid, error = validate_upload(image_file, ALLOWED_IMAGE_EXTENSIONS)
    if not is_valid:
        return jsonify({"success": False, "message": error}), 400

    safe_name = secure_filename(image_file.filename)
    saved_path = UPLOAD_DIR / safe_name
    image_file.save(saved_path)
    result = analyzer.analyze_image_bytes(saved_path.read_bytes())
    payload = result.to_dict()
    payload["uploaded_name"] = safe_name
    return jsonify({"success": True, "result": payload})


@app.route("/api/analyze-video", methods=["POST"])
def analyze_video_api():
    video_file = request.files.get("video")
    if video_file is None or video_file.filename == "":
        return jsonify({"success": False, "message": "Please choose a video."}), 400

    is_valid, error = validate_upload(video_file, ALLOWED_VIDEO_EXTENSIONS)
    if not is_valid:
        return jsonify({"success": False, "message": error}), 400

    safe_name = secure_filename(video_file.filename)
    saved_path = UPLOAD_DIR / safe_name
    video_file.save(saved_path)

    result = analyzer.analyze_video_path(str(saved_path))
    payload = result.to_dict()
    payload["uploaded_name"] = safe_name
    return jsonify({"success": True, "result": payload})


@app.route("/processed/<path:filename>")
def processed_file(filename: str):
    return send_from_directory(PROCESSED_DIR, filename, as_attachment=False)


@app.route("/cognitive")
def cognitive_home():
    return render_template("cognitive.html")


@app.route("/api/cognitive/languages")
def cognitive_languages_api():
    return jsonify({"languages": ner_translations.LANGUAGES})


@app.route("/api/cognitive/content")
def cognitive_content_api():
    language = request.args.get("lang", "en")
    return jsonify({
        "bundle": ner_translations.bundle_for(language),
        "ui": {k: ner_translations.ui(k, language) for k in (
            "memory", "attention", "recognition", "recall", "medicine",
            "hydration", "activity", "appointment",
        )},
        "games": cognitive_games.list_games(),
    })


@app.route("/api/cognitive/patient", methods=["GET", "POST"])
def cognitive_patient_api():
    if request.method == "GET":
        patient_id = request.args.get("patient_id")
        if not patient_id:
            return jsonify({"success": False, "message": "patient_id is required."}), 400
        patient = cognitive_db.get_cognitive_patient(patient_id)
        if not patient:
            return jsonify({"success": False, "message": "Patient not found."}), 404
        reminder_service.seed_defaults(patient_id)
        return jsonify({"success": True, "patient": patient})

    payload = request.get_json(silent=True) or {}
    if not payload.get("patient_id"):
        return jsonify({"success": False, "message": "patient_id is required."}), 400
    patient = cognitive_db.register_cognitive_patient({
        "patient_id": sanitize_text(payload.get("patient_id")),
        "name": sanitize_text(payload.get("name")),
        "age": payload.get("age"),
        "sex": sanitize_text(payload.get("sex")),
        "district": sanitize_text(payload.get("district")),
        "state": sanitize_text(payload.get("state")),
        "language": sanitize_text(payload.get("language") or "en"),
        "cognitive_level": sanitize_text(payload.get("cognitive_level") or "moderate"),
        "caregiver_name": sanitize_text(payload.get("caregiver_name")),
        "caregiver_phone": sanitize_text(payload.get("caregiver_phone")),
    })
    reminder_service.seed_defaults(patient["patient_id"])
    return jsonify({"success": True, "patient": patient})


@app.route("/api/cognitive/game/new")
def cognitive_new_game_api():
    game_type = request.args.get("game_type")
    language = request.args.get("lang", "en")
    level = float(request.args.get("level", 1.0))
    valid_games = set(cognitive_games.games.keys())
    if game_type not in valid_games:
        return jsonify({"success": False, "message": "Unknown game type."}), 400
    puzzle = cognitive_games.new_game(game_type, language=language, level=level)
    return jsonify({"success": True, "puzzle": puzzle})


@app.route("/api/cognitive/session", methods=["POST"])
def cognitive_session_api():
    payload = request.get_json(silent=True) or {}
    patient_id = payload.get("patient_id")
    if not patient_id:
        return jsonify({"success": False, "message": "patient_id is required."}), 400
    patient = cognitive_db.get_cognitive_patient(patient_id)
    if not patient:
        return jsonify({"success": False, "message": "Patient not registered in cognitive platform."}), 404

    session_id = payload.get("session_id")
    if cognitive_db.session_exists(session_id):
        existing = cognitive_db.get_game_session(session_id)
        return jsonify({
            "success": True,
            "session": existing,
            "coins": cognitive_db.get_patient_coins(patient_id),
            "stats": cognitive_db.get_patient_overall_stats(patient_id),
            "activity": "already-logged",
        }), 200

    accuracy = float(payload.get("accuracy_pct", 0))
    current_level = float(payload.get("level", 1.0))
    next_level = cognitive_games.next_level(payload.get("game_type"), current_level, accuracy)

    total_questions = int(payload.get("total_questions") or 0)
    correct_answers = int(payload.get("correct_answers") or 0)
    if total_questions and not correct_answers:
        correct_answers = int(round(total_questions * (accuracy / 100.0)))
    coins_earned = 5 * correct_answers

    session = cognitive_db.save_game_session({
        "session_id": session_id,
        "patient_id": patient_id,
        "game_type": payload.get("game_type"),
        "difficulty_level": payload.get("difficulty_level", int(current_level)),
        "score": payload.get("score", 0),
        "max_score": payload.get("max_score", 100),
        "completion_time_seconds": payload.get("completion_time_seconds", 0),
        "hints_used": payload.get("hints_used", 0),
        "accuracy_pct": accuracy,
        "adaptive_level": next_level,
        "session_data": payload.get("session_data"),
        "completed": payload.get("completed", True),
        "coins_earned": coins_earned,
        "total_questions": total_questions,
        "correct_answers": correct_answers,
        "language": payload.get("language", patient.get("language") or "en"),
    })
    cognitive_db.save_daily_activity({
        "patient_id": patient_id,
        "games_played": 1,
        "total_score": payload.get("score", 0),
        "engagement_minutes": float(payload.get("completion_time_seconds", 0)) / 60.0,
        "mood": payload.get("mood"),
        "notes": payload.get("notes"),
    })
    coin_balance = cognitive_db.add_coins(patient_id, coins_earned)
    game_label = payload.get("game_type", "game")
    pct = float(payload.get("accuracy_pct", 0))
    cognitive_db.add_activity_feed(
        patient_id,
        "game",
        f"Played {game_label} - score {payload.get('score', 0)}, accuracy {pct}%, +{coins_earned} coins",
        float(payload.get("score", 0)),
    )
    # Detailed caregiver notification for game completion
    if patient.get("caregiver_phone"):
        detail = (
            f"{patient.get('name') or 'Patient'} completed {game_label}: "
            f"Score {payload.get('score', 0)}, Accuracy {pct}%, "
            f"Coins +{coins_earned}, Duration {payload.get('completion_time_seconds', 0)}s, "
            f"Level {payload.get('difficulty_level', 1)}"
        )
        cognitive_db.add_caregiver_notification(
            patient.get("caregiver_phone"),
            patient_id,
            "game_completed",
            detail,
        )
    # Low performance notification
    if pct < 55 and patient.get("caregiver_phone"):
        cognitive_db.add_caregiver_notification(
            patient.get("caregiver_phone"),
            patient_id,
            "low_performance",
            f"{patient.get('name') or 'Patient'} had low accuracy ({pct}%) in {game_label}. Consider reviewing the activity.",
        )
    # Level up notification handled by frontend but also notify caregiver
    # (frontend will handle level up toast)
    return jsonify({
        "success": True,
        "session": session,
        "next_level": next_level,
        "coins_earned": coins_earned,
        "coins": coin_balance,
        "stats": cognitive_db.get_patient_overall_stats(patient_id),
        "activity": "logged",
    })


@app.route("/api/cognitive/dashboard")
def cognitive_dashboard_api():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"success": False, "message": "patient_id is required."}), 400
    stats = cognitive_db.get_patient_overall_stats(patient_id)
    assessments = cognitive_db.get_assessments_for_patient(patient_id)
    daily = cognitive_db.get_daily_activities(patient_id)
    reminders = reminder_service.list_reminders(patient_id)
    return jsonify({
        "success": True,
        "stats": stats,
        "assessments": assessments,
        "daily": daily,
        "reminders": reminders,
    })


@app.route("/api/cognitive/assessment", methods=["POST"])
def cognitive_assessment_api():
    payload = request.get_json(silent=True) or {}
    patient_id = payload.get("patient_id")
    if not patient_id:
        return jsonify({"success": False, "message": "patient_id is required."}), 400
    assessment = cognitive_db.save_assessment(payload)
    cognitive_db.add_activity_feed(
        patient_id,
        "milestone",
        f"Cognitive assessment recorded - overall score {payload.get('overall_score', 0)}",
        float(payload.get("overall_score", 0)),
    )
    return jsonify({"success": True, "assessment": assessment})


@app.route("/api/cognitive/reminders")
def cognitive_reminders_api():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"success": False, "message": "patient_id is required."}), 400
    return jsonify({"success": True, "reminders": reminder_service.list_reminders(patient_id)})


@app.route("/api/cognitive/reminders", methods=["POST"])
def cognitive_add_reminder_api():
    payload = request.get_json(silent=True) or {}
    patient_id = payload.get("patient_id")
    if not patient_id:
        return jsonify({"success": False, "message": "patient_id is required."}), 400
    reminder_type = payload.get("reminder_type")
    if reminder_type not in ("medicine", "hydration", "activity", "appointment"):
        reminder_type = "activity"
    reminder = reminder_service.add_reminder(patient_id, {
        "reminder_type": reminder_type,
        "title": sanitize_text(payload.get("title")),
        "message": sanitize_text(payload.get("message")),
        "scheduled_time": payload.get("scheduled_time") or payload.get("time"),
        "recurrence": payload.get("recurrence", "daily"),
        "is_active": payload.get("is_active", True),
    })
    cognitive_db.add_activity_feed(
        patient_id,
        "reminder",
        f"Reminder added: {reminder.get('title') or reminder_type} at {reminder.get('scheduled_time') or '--:--'}",
        0,
    )
    patient = cognitive_db.get_cognitive_patient(patient_id)
    if patient:
        cognitive_db.add_caregiver_notification(
            patient.get("caregiver_phone"),
            patient_id,
            "reminder",
            f"Reminder added for {patient.get('name') or 'patient'}: {reminder.get('title') or reminder_type} at {reminder.get('scheduled_time') or '--:--'}",
        )
    return jsonify({"success": True, "reminder": reminder})


@app.route("/api/cognitive/reminders/<reminder_id>", methods=["DELETE"])
def cognitive_delete_reminder_api(reminder_id: str):
    result = reminder_service.delete_reminder(reminder_id)
    return jsonify({"success": True, **result})


@app.route("/api/cognitive/reminders/<reminder_id>/toggle", methods=["POST"])
def cognitive_toggle_reminder_api(reminder_id: str):
    payload = request.get_json(silent=True) or {}
    reminder = reminder_service.toggle_reminder(reminder_id, bool(payload.get("active", True)))
    return jsonify({"success": True, "reminder": reminder})


@app.route("/api/cognitive/reminders/<reminder_id>/ack", methods=["POST"])
def cognitive_ack_reminder_api(reminder_id: str):
    reminder = reminder_service.get_reminder(reminder_id)
    result = reminder_service.acknowledge(reminder_id)
    if reminder:
        cognitive_db.add_activity_feed(
            reminder.get("patient_id"),
            "reminder",
            f"Reminder acknowledged: {reminder.get('title') or reminder.get('reminder_type') or 'item'}",
            0,
        )
    return jsonify({"success": True, **result})


@app.route("/api/cognitive/caregiver")
def cognitive_caregiver_api():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"success": False, "message": "patient_id is required."}), 400
    dashboard = cognitive_db.get_caregiver_dashboard(patient_id)
    dashboard["health_score"] = caregiver_analytics.health_score(patient_id)
    return jsonify({"success": True, "dashboard": dashboard})


@app.route("/api/cognitive/overview")
def cognitive_caregiver_overview_api():
    return jsonify({
        "success": True,
        "overview": cognitive_db.caregiver_dashboard_stats(),
        "patients": caregiver_analytics.list_patients(),
    })


@app.route("/api/cognitive/patients")
def cognitive_caregiver_patients_api():
    caregiver_phone = request.args.get("phone", "").strip()
    if not caregiver_phone:
        return jsonify({"success": False, "message": "caregiver phone is required."}), 400
    patients = cognitive_db.get_patients_for_caregiver(caregiver_phone)
    enriched = []
    for p in patients:
        enriched.append({
            "patient_id": p.get("patient_id"),
            "name": p.get("name"),
            "age": p.get("age"),
            "sex": p.get("sex"),
            "district": p.get("district"),
            "state": p.get("state"),
            "language": p.get("language"),
            "cognitive_level": p.get("cognitive_level"),
            "coins_balance": p.get("coins_balance"),
            "stats": cognitive_db.get_patient_overall_stats(p.get("patient_id")),
            "today": cognitive_db.get_today_stats(p.get("patient_id")),
            "active_reminders": len([r for r in reminder_service.list_reminders(p.get("patient_id")) if r.get("is_active")]),
        })
    return jsonify({"success": True, "patients": enriched})


@app.route("/api/cognitive/coins")
def cognitive_coins_api():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"success": False, "message": "patient_id is required."}), 400
    return jsonify({
        "success": True,
        "patient_id": patient_id,
        "coins_balance": cognitive_db.get_patient_coins(patient_id),
        "today": cognitive_db.get_today_stats(patient_id),
    })


@app.route("/api/cognitive/notifications")
def cognitive_notifications_api():
    caregiver_phone = request.args.get("phone", "").strip()
    if not caregiver_phone:
        return jsonify({"success": False, "message": "caregiver phone is required."}), 400
    limit = int(request.args.get("limit", 50))
    return jsonify({
        "success": True,
        "notifications": cognitive_db.list_caregiver_notifications(caregiver_phone, limit=limit),
        "unread": cognitive_db.count_unread_notifications(caregiver_phone),
    })


@app.route("/api/cognitive/notifications/read", methods=["POST"])
def cognitive_notifications_read_api():
    payload = request.get_json(silent=True) or {}
    caregiver_phone = payload.get("phone", "").strip()
    if not caregiver_phone:
        return jsonify({"success": False, "message": "caregiver phone is required."}), 400
    cognitive_db.mark_notifications_read(caregiver_phone)
    return jsonify({"success": True, "unread": 0})


@app.route("/api/cognitive/login", methods=["POST"])
def cognitive_login_api():
    payload = request.get_json(silent=True) or {}
    phone = payload.get("phone", "").strip()
    if not phone:
        return jsonify({"success": False, "message": "Phone number is required."}), 400
    pin = str(payload.get("pin", "") or "").strip()
    name = payload.get("name", "").strip()
    role = payload.get("role", "patient")
    language = payload.get("language", "en")

    existing = cognitive_db.login_user(phone)
    if existing:
        stored_pin = (existing.get("pin") or "").strip()
        if not stored_pin and pin:
            cognitive_db.set_user_pin(phone, pin)
            existing["pin"] = pin
        user = existing
        if (user.get("pin") or "").strip() != (pin or "").strip():
            return jsonify({"success": False, "status": "wrong_pin",
                            "message": "Incorrect PIN. Please try again."}), 403
        patient = None
        if role == "patient" and user.get("patient_id"):
            patient = cognitive_db.get_cognitive_patient(user["patient_id"])
        return jsonify({"success": True, "user": user, "patient": patient})

    if not name:
        return jsonify({"success": False, "message": "Name is required for new registration."}), 400
    if not pin or not pin.isdigit() or len(pin) < 4:
        return jsonify({"success": False, "message": "Please set a 4-digit safety PIN."}), 400

    patient = None
    if role == "patient":
        patient = cognitive_db.register_cognitive_patient({
            "patient_id": f"P-{phone[-6:]}",
            "name": sanitize_text(name),
            "language": language,
            "caregiver_phone": payload.get("caregiver_phone") or phone,
        })
        reminder_service.seed_defaults(patient["patient_id"])
    user = cognitive_db.register_user({
        "phone": phone,
        "name": name,
        "role": role,
        "language": language,
        "patient_id": patient["patient_id"] if patient else payload.get("patient_id"),
        "pin": pin,
    })
    return jsonify({"success": True, "user": user, "patient": patient})


@app.route("/api/cognitive/activity-feed")
def cognitive_activity_feed_api():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"success": False, "message": "patient_id is required."}), 400
    since = request.args.get("since", "")
    limit = int(request.args.get("limit", 20))
    feed = cognitive_db.get_activity_feed(patient_id, limit=limit)
    return jsonify({"success": True, "feed": feed})


@app.route("/api/cognitive/report/pdf")
def cognitive_report_pdf_api():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"success": False, "message": "patient_id is required."}), 400
    patient = cognitive_db.get_cognitive_patient(patient_id)
    stats = cognitive_db.get_patient_overall_stats(patient_id)
    sessions = cognitive_db.get_sessions_for_patient(patient_id, limit=30)
    assessments = cognitive_db.get_assessments_for_patient(patient_id)
    assessment = assessments[0] if assessments else None
    pdf_path = REPORTS_DIR / f"Smirthi-{patient_id}-{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    _write_cognitive_pdf_report(pdf_path, patient, stats, sessions, assessment)
    if not pdf_path.exists():
        pdf_path.write_bytes(b'')
    return jsonify({
        "success": True,
        "patient_id": patient_id,
        "pdf_path": str(pdf_path),
        "status": "generated",
        "download_url": f"/api/cognitive/report/{patient_id}/download",
    })


@app.route("/api/cognitive/report/<patient_id>/download")
def cognitive_report_download_api(patient_id: str):
    pdf_path = REPORTS_DIR / f"Smirthi-{patient_id}-{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    if not pdf_path.exists():
        patient = cognitive_db.get_cognitive_patient(patient_id)
        stats = cognitive_db.get_patient_overall_stats(patient_id)
        sessions = cognitive_db.get_sessions_for_patient(patient_id, limit=30)
        assessments = cognitive_db.get_assessments_for_patient(patient_id)
        assessment = assessments[0] if assessments else None
        _write_cognitive_pdf_report(pdf_path, patient, stats, sessions, assessment)
    if pdf_path.exists():
        return send_from_directory(str(pdf_path.parent), pdf_path.name, as_attachment=True)
    return jsonify({"success": False, "message": "Report not available."}), 404


@app.route("/health")
def health_api():
    return jsonify({"ok": True, "status": "SwasthGati offline-capable screening app running"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
