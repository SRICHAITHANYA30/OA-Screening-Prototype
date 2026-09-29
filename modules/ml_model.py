from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import lightgbm as lgb
except Exception:
    lgb = None



MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_DIR.mkdir(exist_ok=True)
MODEL_PATH = MODEL_DIR / "oa_lightgbm_model.txt"
METADATA_PATH = MODEL_DIR / "model_metadata.json"


class LightGBMModelManager:
    def __init__(self, model_path: str | Path | None = None):
        self.model_path = Path(model_path) if model_path else MODEL_PATH
        self.metadata_path = MODEL_DIR / "model_metadata.json"
        self.model = None
        self.metadata = self._read_metadata()
        self._load_if_available()

    def _read_metadata(self) -> dict[str, Any]:
        if self.metadata_path.exists():
            try:
                return json.loads(self.metadata_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _load_if_available(self) -> None:
        if self.model_path.exists():
            try:
                self.model = lgb.Booster(model_file=str(self.model_path))
            except Exception:
                self.model = None

    def available(self) -> bool:
        return self.model is not None

    def status(self) -> dict[str, Any]:
        if self.model is not None:
            return {
                "status": "trained",
                "model_path": str(self.model_path),
                "metadata": self.metadata,
            }
        return {
            "status": "not_trained",
            "message": "AI model not trained / OAI dataset unavailable.",
            "model_path": str(self.model_path),
            "metadata": self.metadata,
        }

    def predict_from_features(self, features: dict[str, float]) -> dict[str, Any]:
        if self.model is None:
            return {
                "available": False,
                "status": "AI model not trained / OAI dataset unavailable.",
                "risk_level": "UNKNOWN",
                "risk_score": None,
            }
        ordered = []
        feature_order = self.metadata.get("feature_order", [])
        for field in feature_order:
            ordered.append(float(features.get(field, 0.0)))
        if not ordered:
            ordered = [float(v) for v in features.values()]
        prediction = self.model.predict([ordered])[0]
        risk_score = float(prediction)
        if risk_score < 0.33:
            risk_level = "LOW"
        elif risk_score < 0.66:
            risk_level = "MODERATE"
        else:
            risk_level = "HIGH"
        return {
            "available": True,
            "status": "AI-assisted preliminary screening",
            "risk_level": risk_level,
            "risk_score": risk_score,
            "raw_prediction": float(prediction),
        }

    def save_metadata(self, fields: list[str]) -> None:
        self.metadata = {"feature_order": fields}
        self.metadata_path.write_text(json.dumps(self.metadata), encoding="utf-8")
        self._read_metadata()
