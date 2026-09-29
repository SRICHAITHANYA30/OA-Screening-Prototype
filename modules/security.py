from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def sanitize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()[:200]


def validate_patient_payload(payload: dict[str, Any]) -> tuple[bool, str | None]:
    if not payload.get("name"):
        return False, "Patient name is required."
    if not payload.get("patient_id"):
        return False, "Patient ID is required."
    age = payload.get("age")
    if age is not None:
        try:
            age_value = int(age)
            if age_value < 0 or age_value > 120:
                return False, "Age must be between 0 and 120."
        except (TypeError, ValueError):
            return False, "Age must be numeric."
    return True, None


def validate_upload(file_obj, allowed_extensions: set[str], max_bytes: int = 50 * 1024 * 1024) -> tuple[bool, str | None]:
    if file_obj is None:
        return False, "No file uploaded."
    filename = getattr(file_obj, "filename", "")
    ext = Path(filename).suffix.lower().lstrip(".")
    if not ext or ext not in allowed_extensions:
        return False, f"Unsupported file type. Allowed: {', '.join(sorted(allowed_extensions))}."
    try:
        file_obj.seek(0, os.SEEK_END)
        size = file_obj.tell()
        file_obj.seek(0)
        if size > max_bytes:
            return False, f"File exceeds {max_bytes // (1024 * 1024)} MB limit."
    except Exception:
        return False, "File could not be validated."
    return True, None


def privacy_notice() -> str:
    return (
        "Privacy notice: Only essential screening information is stored locally. "
        "This system is for AI-assisted preliminary screening and is not a medical diagnosis."
    )
