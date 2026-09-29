from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

try:
    from ultralytics import YOLO
except Exception as exc:  # pragma: no cover
    YOLO = None
    YOLO_IMPORT_ERROR = str(exc)
else:
    YOLO_IMPORT_ERROR = None


PROJECT_ROOT = Path(__file__).resolve().parent
PROCESSED_DIR = PROJECT_ROOT / "processed_outputs"
PROCESSED_DIR.mkdir(exist_ok=True)


@dataclass
class PoseAnalysisResult:
    valid: bool
    status: str
    left_knee_angle: float | None = None
    right_knee_angle: float | None = None
    symmetry_pct: float | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    movement_status: str | None = None
    alignment_status: str | None = None
    possible_region: str | None = None
    possible_markers: list[str] | None = None
    annotated_image_base64: str | None = None
    processed_video_url: str | None = None
    multiple_people_detected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "status": self.status,
            "left_knee_angle": self.left_knee_angle,
            "right_knee_angle": self.right_knee_angle,
            "symmetry_pct": self.symmetry_pct,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "movement_status": self.movement_status,
            "alignment_status": self.alignment_status,
            "possible_region": self.possible_region,
            "possible_markers": self.possible_markers or [],
            "annotated_image_base64": self.annotated_image_base64,
            "processed_video_url": self.processed_video_url,
            "multiple_people_detected": self.multiple_people_detected,
        }


class KneeRiskAnalyzer:
    """Real YOLO pose-based knee screening analyzer for webcam, images, and video."""

    def __init__(self):
        self.model = None
        if YOLO is not None:
            self.model = YOLO("yolov8n-pose.pt")

        self.landmark_names = {
            "left_hip": 11,
            "right_hip": 12,
            "left_knee": 13,
            "right_knee": 14,
            "left_ankle": 15,
            "right_ankle": 16,
        }
        self.skeleton_pairs = [
            (11, 13),
            (13, 15),
            (12, 14),
            (14, 16),
            (11, 12),
            (11, 23),
            (12, 24),
        ]

    @staticmethod
    def angle_between(p1, p2, p3) -> float:
        p1 = np.asarray(p1, dtype=float)
        p2 = np.asarray(p2, dtype=float)
        p3 = np.asarray(p3, dtype=float)
        v1 = p1 - p2
        v2 = p3 - p2
        denom = np.linalg.norm(v1) * np.linalg.norm(v2)
        if denom < 1e-6:
            return 0.0
        cosine = float(np.dot(v1, v2) / denom)
        cosine = max(-1.0, min(1.0, cosine))
        return float(np.degrees(np.arccos(cosine)))

    @staticmethod
    def frame_to_base64(frame: np.ndarray) -> str:
        ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            return ""
        return base64.b64encode(buffer.tobytes()).decode("utf-8")

    def _extract_landmarks(self, frame: np.ndarray):
        if self.model is None:
            return None, False, 0

        results = self.model(frame, verbose=False, conf=0.25)[0]
        if results is None or results.keypoints is None or len(results.keypoints.xy) == 0:
            return None, False, 0

        keypoints = results.keypoints.xy.cpu().numpy()
        person_count = len(keypoints)
        selected = keypoints[0]

        landmarks = {}
        for name, idx in self.landmark_names.items():
            if idx < len(selected):
                x, y = selected[idx]
                if np.isnan(x) or np.isnan(y):
                    landmarks[name] = None
                else:
                    landmarks[name] = (int(x), int(y))
            else:
                landmarks[name] = None

        return landmarks, person_count > 1, person_count

    def _draw_pose(self, frame: np.ndarray, keypoints_xy: np.ndarray, text_lines: list[str] | None = None):
        annotated = frame.copy()

        for start_idx, end_idx in self.skeleton_pairs:
            if start_idx >= len(keypoints_xy) or end_idx >= len(keypoints_xy):
                continue
            p1 = keypoints_xy[start_idx]
            p2 = keypoints_xy[end_idx]
            if np.any(np.isnan(p1)) or np.any(np.isnan(p2)):
                continue
            cv2.line(annotated, tuple(map(int, p1)), tuple(map(int, p2)), (34, 197, 94), 3)

        for idx in [11, 12, 13, 14, 15, 16]:
            if idx < len(keypoints_xy):
                x, y = keypoints_xy[idx]
                if not (np.isnan(x) or np.isnan(y)):
                    cv2.circle(annotated, (int(x), int(y)), 7, (59, 130, 246), -1)
                    cv2.circle(annotated, (int(x), int(y)), 10, (255, 255, 255), 2)

        if text_lines:
            overlay = annotated.copy()
            cv2.rectangle(overlay, (14, 14), (360, 120), (15, 23, 42), -1)
            annotated = cv2.addWeighted(overlay, 0.5, annotated, 0.5, 0)
            for i, text in enumerate(text_lines):
                cv2.putText(
                    annotated,
                    text,
                    (26, 44 + i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )

        return annotated

    def analyze_frame(self, frame: np.ndarray) -> PoseAnalysisResult:
        if self.model is None:
            return PoseAnalysisResult(False, f"YOLO model unavailable: {YOLO_IMPORT_ERROR or 'unknown error'}")

        results = self.model(frame, verbose=False, conf=0.25)[0]
        if results is None or results.keypoints is None or len(results.keypoints.xy) == 0:
            return PoseAnalysisResult(False, "No person detected. Please stand where your full body/legs are visible.")

        keypoints = results.keypoints.xy.cpu().numpy()
        multiple_people = len(keypoints) > 1
        selected = keypoints[0]

        landmarks = {}
        for name, idx in self.landmark_names.items():
            if idx < len(selected):
                x, y = selected[idx]
                if np.isnan(x) or np.isnan(y):
                    landmarks[name] = None
                else:
                    landmarks[name] = (int(x), int(y))
            else:
                landmarks[name] = None

        if not all(landmarks.get(name) is not None for name in self.landmark_names):
            annotated = self._draw_pose(
                frame,
                selected,
                ["Unable to obtain reliable knee landmarks.", "Please adjust your position."]
            )
            return PoseAnalysisResult(
                False,
                "Unable to obtain reliable knee landmarks. Please adjust your position.",
                annotated_image_base64=self.frame_to_base64(annotated),
                multiple_people_detected=multiple_people,
            )

        left_knee_angle = self.angle_between(
            landmarks["left_hip"], landmarks["left_knee"], landmarks["left_ankle"]
        )
        right_knee_angle = self.angle_between(
            landmarks["right_hip"], landmarks["right_knee"], landmarks["right_ankle"]
        )
        diff = abs(left_knee_angle - right_knee_angle)
        symmetry_pct = max(0.0, min(100.0, 100.0 - (diff / 90.0) * 100.0))

        alignment_status = "Normal" if diff < 15 else "Possible variation"
        movement_status = "Normal" if symmetry_pct >= 80 else "Possible abnormality"
        score = 0.0
        score += max(0.0, (100.0 - symmetry_pct)) * 0.55
        score += max(0.0, diff - 10.0) * 1.4
        score += max(0.0, 65.0 - min(left_knee_angle, right_knee_angle)) * 0.6
        score = float(max(0.0, min(100.0, score)))

        if score < 35:
            risk_level = "LOW"
        elif score < 65:
            risk_level = "MODERATE"
        else:
            risk_level = "HIGH"

        if symmetry_pct < 75:
            possible_markers = ["Movement asymmetry"]
        else:
            possible_markers = []
        if min(left_knee_angle, right_knee_angle) < 60:
            possible_markers.append("Reduced range of motion")
        if diff >= 15:
            possible_markers.append("Alignment variation")
        if multiple_people:
            possible_markers.append("Multiple people detected")

        if not possible_markers:
            possible_markers = ["No major risk markers detected"]

        possible_region = "Bilateral knee movement" if diff >= 15 else "Insufficient data" if symmetry_pct < 60 else "Possible affected knee movement region"
        status = (
            "AI-assisted screening result — not a medical diagnosis. "
            "Possible abnormal movement/alignment region detected."
        )

        annotated = self._draw_pose(
            frame,
            selected,
            [
                f"Left: {left_knee_angle:.1f}°  Right: {right_knee_angle:.1f}°",
                f"Symmetry: {symmetry_pct:.1f}%  Risk: {risk_level}",
                "Real pose landmarks detected",
            ],
        )

        return PoseAnalysisResult(
            True,
            status,
            left_knee_angle=left_knee_angle,
            right_knee_angle=right_knee_angle,
            symmetry_pct=symmetry_pct,
            risk_score=score,
            risk_level=risk_level,
            movement_status=movement_status,
            alignment_status=alignment_status,
            possible_region=possible_region,
            possible_markers=possible_markers,
            annotated_image_base64=self.frame_to_base64(annotated),
            multiple_people_detected=multiple_people,
        )

    def analyze_image_bytes(self, image_bytes: bytes) -> PoseAnalysisResult:
        np_buffer = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
        if frame is None:
            return PoseAnalysisResult(False, "Unsupported image or could not decode file.")
        return self.analyze_frame(frame)

    def analyze_video_path(self, video_path: str) -> PoseAnalysisResult:
        if self.model is None:
            return PoseAnalysisResult(False, f"YOLO model unavailable: {YOLO_IMPORT_ERROR or 'unknown error'}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return PoseAnalysisResult(False, "Unable to open video file.")

        fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width == 0 or height == 0:
            cap.release()
            return PoseAnalysisResult(False, "Could not read video dimensions.")

        processed_path = PROCESSED_DIR / f"processed_{Path(video_path).stem}.avi"
        writer = cv2.VideoWriter(str(processed_path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height))
        if not writer.isOpened():
            cap.release()
            return PoseAnalysisResult(False, "Could not initialize processed video writer.")

        left_angles = []
        right_angles = []
        symmetry_values = []
        valid_frames = 0
        preview_frame = None
        preview_result = None

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            preview_result = self.analyze_frame(frame)
            if preview_result.valid:
                valid_frames += 1
                left_angles.append(preview_result.left_knee_angle or 0)
                right_angles.append(preview_result.right_knee_angle or 0)
                symmetry_values.append(preview_result.symmetry_pct or 0)
                annotated = cv2.imdecode(np.frombuffer(base64.b64decode(preview_result.annotated_image_base64), np.uint8), cv2.IMREAD_COLOR) if preview_result.annotated_image_base64 else frame
                preview_frame = annotated
                writer.write(annotated)
            else:
                writer.write(frame)

        cap.release()
        writer.release()

        if valid_frames == 0:
            return PoseAnalysisResult(False, "No usable pose landmarks found in this video. Check visibility and camera framing.")

        left_mean = float(np.mean(left_angles))
        right_mean = float(np.mean(right_angles))
        symmetry_mean = float(np.mean(symmetry_values))
        diff = abs(left_mean - right_mean)

        risk_score = float(max(0.0, min(100.0, (100.0 - symmetry_mean) * 0.9 + max(0.0, diff - 10.0) * 1.1)))
        risk_level = "LOW" if risk_score < 35 else "MODERATE" if risk_score < 65 else "HIGH"
        possible_markers = []
        if symmetry_mean < 75:
            possible_markers.append("Movement asymmetry")
        if min(left_mean, right_mean) < 60:
            possible_markers.append("Reduced range of motion")
        if diff >= 15:
            possible_markers.append("Alignment variation")
        if not possible_markers:
            possible_markers = ["No major risk markers detected"]

        if diff >= 15:
            possible_region = "Bilateral knee movement" if symmetry_mean < 70 else "Possible affected knee movement region"
        else:
            possible_region = "Insufficient data" if valid_frames < 10 else "Possible affected knee movement region"

        status = (
            "AI-assisted screening result — not a medical diagnosis. "
            "Possible abnormal movement/alignment region detected."
        )

        preview_image_b64 = None
        if preview_frame is not None:
            preview_image_b64 = self.frame_to_base64(preview_frame)

        return PoseAnalysisResult(
            True,
            status,
            left_knee_angle=left_mean,
            right_knee_angle=right_mean,
            symmetry_pct=symmetry_mean,
            risk_score=risk_score,
            risk_level=risk_level,
            movement_status="Normal" if symmetry_mean >= 80 else "Possible abnormality",
            alignment_status="Normal" if diff < 15 else "Possible variation",
            possible_region=possible_region,
            possible_markers=possible_markers,
            annotated_image_base64=preview_image_b64,
            processed_video_url=f"/processed/{processed_path.name}",
        )
