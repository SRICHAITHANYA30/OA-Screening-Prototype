import os
import math
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageTk, ImageOps

try:
    from ultralytics import YOLO
except Exception as exc:  # pragma: no cover
    YOLO = None
    YOLO_IMPORT_ERROR = str(exc)
else:
    YOLO_IMPORT_ERROR = None


USE_APP_PATH = Path(__file__).resolve().parent


class PoseAnalyzer:
    """Real YOLO pose detection engine for knee posture screening."""

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

    @staticmethod
    def angle_between(p1, p2, p3):
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

    def _extract_landmarks(self, frame):
        if self.model is None:
            return None
        results = self.model(frame, verbose=False, conf=0.25)[0]
        if results is None or len(results.keypoints.xy) == 0:
            return None

        keypoints = results.keypoints.xy[0].cpu().numpy()
        h, w, _ = frame.shape
        landmarks = {}
        for name, idx in self.landmark_names.items():
            if idx < len(keypoints):
                x, y = keypoints[idx]
                if not np.isnan(x) and not np.isnan(y):
                    landmarks[name] = (int(x), int(y))
                else:
                    landmarks[name] = None
            else:
                landmarks[name] = None
        return landmarks

    def _annotate_frame(self, frame, landmarks, text_lines=None):
        if landmarks is None:
            return frame
        annotated = frame.copy()
        connection_pairs = [
            ("left_hip", "left_knee"),
            ("left_knee", "left_ankle"),
            ("right_hip", "right_knee"),
            ("right_knee", "right_ankle"),
        ]
        for a_name, b_name in connection_pairs:
            a = landmarks.get(a_name)
            b = landmarks.get(b_name)
            if a and b:
                cv2.line(annotated, a, b, (0, 255, 0), 2)

        for name in ["left_hip", "left_knee", "left_ankle", "right_hip", "right_knee", "right_ankle"]:
            pt = landmarks.get(name)
            if pt:
                cv2.circle(annotated, pt, 6, (0, 0, 255), -1)

        if text_lines:
            for idx, line in enumerate(text_lines):
                cv2.putText(
                    annotated,
                    line,
                    (20, 30 + idx * 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
        return annotated

    def analyze_frame(self, frame):
        landmarks = self._extract_landmarks(frame)
        if not landmarks:
            return {
                "valid": False,
                "status": "No person detected. Please move into the camera frame.",
                "annotated": frame,
            }

        required = ["left_hip", "left_knee", "left_ankle", "right_hip", "right_knee", "right_ankle"]
        if not all(landmarks.get(name) is not None for name in required):
            return {
                "valid": False,
                "status": "Insufficient landmarks detected. Improve visibility and ensure the full leg is visible.",
                "annotated": self._annotate_frame(frame, landmarks),
            }

        left_knee_angle = self.angle_between(
            landmarks["left_hip"], landmarks["left_knee"], landmarks["left_ankle"]
        )
        right_knee_angle = self.angle_between(
            landmarks["right_hip"], landmarks["right_knee"], landmarks["right_ankle"]
        )

        diff = abs(left_knee_angle - right_knee_angle)
        symmetry_pct = max(0.0, 100.0 - (diff / 90.0) * 100.0)
        symmetry_pct = min(100.0, symmetry_pct)

        score = 0.0
        score += max(0.0, (60.0 - min(left_knee_angle, right_knee_angle)) / 60.0) * 25.0
        score += max(0.0, (60.0 - abs(left_knee_angle - right_knee_angle)) / 60.0) * 30.0
        score += max(0.0, (100.0 - symmetry_pct) / 100.0) * 45.0
        score = min(100.0, max(0.0, score))

        if score < 35:
            level = "LOW"
            detail = "AI-assisted screening result — not a medical diagnosis. Possible low-risk posture pattern observed."
        elif score < 65:
            level = "MODERATE"
            detail = "AI-assisted screening result — not a medical diagnosis. Possible abnormal movement/alignment region detected."
        else:
            level = "HIGH"
            detail = "AI-assisted screening result — not a medical diagnosis. Possible abnormal posture/alignment marker detected."

        text_lines = [
            f"Left knee: {left_knee_angle:.1f}°",
            f"Right knee: {right_knee_angle:.1f}°",
            f"Symmetry: {symmetry_pct:.1f}%",
            f"Risk: {level} ({score:.1f}/100)",
        ]
        annotated = self._annotate_frame(frame, landmarks, text_lines)
        return {
            "valid": True,
            "status": detail,
            "annotated": annotated,
            "left_knee_angle": left_knee_angle,
            "right_knee_angle": right_knee_angle,
            "symmetry_pct": symmetry_pct,
            "risk_score": score,
            "risk_level": level,
        }

    def analyze_image(self, image_path):
        image = cv2.imread(image_path)
        if image is None:
            return {"valid": False, "status": "Unsupported image or file could not be read."}
        result = self.analyze_frame(image)
        if not result["valid"]:
            return result
        result["processed_path"] = image_path
        return result

    def analyze_video(self, video_path):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"valid": False, "status": "Unable to open video file."}

        left_angles = []
        right_angles = []
        valid_frames = 0
        processed_dir = USE_APP_PATH / "processed_outputs"
        processed_dir.mkdir(exist_ok=True)
        out_path = processed_dir / "processed_video.avi"
        fps = 20.0
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if frame_width == 0 or frame_height == 0:
            return {"valid": False, "status": "Could not read video dimensions."}

        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        writer = cv2.VideoWriter(str(out_path), fourcc, fps, (frame_width, frame_height))
        if not writer.isOpened():
            return {"valid": False, "status": "Could not initialize video writer for processed output."}

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            result = self.analyze_frame(frame)
            if result["valid"]:
                left_angles.append(result["left_knee_angle"])
                right_angles.append(result["right_knee_angle"])
                valid_frames += 1
            writer.write(result["annotated"])

        cap.release()
        writer.release()

        if valid_frames == 0:
            return {"valid": False, "status": "No usable pose landmarks found in this video. Check visibility and camera framing."}

        left_mean = float(np.mean(left_angles))
        right_mean = float(np.mean(right_angles))
        diff = abs(left_mean - right_mean)
        symmetry = max(0.0, 100.0 - (diff / 90.0) * 100.0)
        symmetry = min(100.0, symmetry)
        score = min(100.0, max(0.0, (100.0 - symmetry) * 0.8 + (50.0 - min(left_mean, right_mean)) * 0.2))
        if score < 35:
            level = "LOW"
            detail = "AI-assisted screening result — not a medical diagnosis. The movement pattern appears relatively symmetric."
        elif score < 65:
            level = "MODERATE"
            detail = "AI-assisted screening result — not a medical diagnosis. Possible abnormal movement/alignment region detected."
        else:
            level = "HIGH"
            detail = "AI-assisted screening result — not a medical diagnosis. Possible abnormal posture/alignment marker detected."

        return {
            "valid": True,
            "status": detail,
            "left_knee_angle": left_mean,
            "right_knee_angle": right_mean,
            "symmetry_pct": symmetry,
            "risk_score": float(score),
            "risk_level": level,
            "processed_video": str(out_path),
        }


class SwasthGatiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SWASTHGATI - Knee Risk Screening")
        self.root.geometry("1200x750")
        self.root.minsize(1100, 700)
        self.root.configure(bg="#eaf3fb")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("Primary.TButton", background="#1d4ed8", foreground="#ffffff", font=("Segoe UI", 11, "bold"))
        style.map("Primary.TButton", background=[("active", "#163ea8")])
        style.configure("Secondary.TButton", background="#eff6ff", foreground="#0f172a", font=("Segoe UI", 10, "bold"))
        style.configure("Muted.TButton", background="#dfeafc", foreground="#0f172a", font=("Segoe UI", 10, "bold"))

        self.pose_analyzer = PoseAnalyzer()
        self.cap = None
        self.camera_running = False
        self.screening_active = False
        self.current_mode = "live"
        self.preview_photo = None
        self.last_summary = {
            "left_knee_angle": None,
            "right_knee_angle": None,
            "symmetry_pct": None,
            "risk_level": "LOW",
            "status": "Ready for screening.",
        }

        self.header_frame = tk.Frame(self.root, bg="#f5fbff", padx=28, pady=20)
        self.header_frame.pack(fill=tk.X)

        self.title_label = tk.Label(
            self.header_frame,
            text="SWASTHGATI",
            bg="#f5fbff",
            fg="#0f172a",
            font=("Segoe UI", 28, "bold"),
            anchor="w",
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = tk.Label(
            self.header_frame,
            text="AI-Assisted Knee Risk Screening",
            bg="#f5fbff",
            fg="#3b82f6",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        )
        self.subtitle_label.pack(anchor="w", pady=2)

        self.subsubtitle_label = tk.Label(
            self.header_frame,
            text="Preliminary screening using posture and movement analysis",
            bg="#f5fbff",
            fg="#475569",
            font=("Segoe UI", 10),
            anchor="w",
        )
        self.subsubtitle_label.pack(anchor="w", pady=6)

        self.mode_frame = tk.Frame(self.root, bg="#edf6ff", padx=18, pady=18)
        self.mode_frame.pack(fill=tk.X, padx=20, pady=10)

        self.mode_buttons = {}
        for mode, label, sub in [
            ("live", "📷 LIVE CAMERA", "Real-time screening"),
            ("photo", "📸 UPLOAD PHOTO", "Analyze knee image"),
            ("video", "🎥 UPLOAD VIDEO", "Analyze walking"),
        ]:
            btn = tk.Button(
                self.mode_frame,
                text=f"{label}\n{sub}",
                compound="center",
                bg="#ffffff",
                fg="#0f172a",
                activebackground="#dbeafe",
                activeforeground="#0f172a",
                font=("Segoe UI", 11, "bold"),
                padx=18,
                pady=12,
                relief="flat",
                bd=2,
                cursor="hand2",
                command=lambda m=mode: self.set_mode(m),
                width=20,
                height=3,
            )
            btn.pack(side=tk.LEFT, padx=12)
            self.mode_buttons[mode] = btn

        self.content_frame = tk.Frame(self.root, bg="#edf6ff", padx=18, pady=18)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        self.preview_card = tk.Frame(self.content_frame, bg="#ffffff", bd=0, highlightthickness=0)
        self.preview_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12)

        self.preview_label = tk.Label(
            self.preview_card,
            bg="#0f172a",
            relief="flat",
            width=78,
            height=28,
            compound="center",
        )
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.analysis_panel = tk.Frame(self.content_frame, width=360, bg="#ffffff", padx=16, pady=16)
        self.analysis_panel.pack(side=tk.RIGHT, fill=tk.Y)

        self.analysis_title = tk.Label(
            self.analysis_panel,
            text="LIVE ANALYSIS",
            bg="#ffffff",
            fg="#0f172a",
            font=("Segoe UI", 15, "bold"),
            anchor="w",
        )
        self.analysis_title.pack(anchor="w", pady=12)

        self.metric_left = self.make_metric_block("Left Knee", "0.0°", "Knee Angle")
        self.metric_right = self.make_metric_block("Right Knee", "0.0°", "Knee Angle")
        self.metric_sym = self.make_metric_block("Symmetry", "0.0%", "Left / Right")
        self.metric_status = self.make_metric_block("Movement Status", "Normal", "Current pattern")

        self.result_card = tk.Frame(self.analysis_panel, bg="#dfeafc", padx=14, pady=14, bd=0)
        self.result_card.pack(fill=tk.X, pady=8)

        self.result_title = tk.Label(
            self.result_card,
            text="PRELIMINARY SCREENING RESULT",
            bg="#dfeafc",
            fg="#0f172a",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        self.result_title.pack(anchor="w")

        self.result_value = tk.Label(
            self.result_card,
            text="LOW RISK",
            bg="#dfeafc",
            fg="#0f172a",
            font=("Segoe UI", 22, "bold"),
            anchor="w",
        )
        self.result_value.pack(anchor="w", pady=8)

        self.result_note = tk.Label(
            self.result_card,
            text="Possible markers: none detected",
            bg="#dfeafc",
            fg="#1f2937",
            justify=tk.LEFT,
            font=("Segoe UI", 10),
            wraplength=320,
            anchor="w",
        )
        self.result_note.pack(anchor="w")

        self.disclaimer = tk.Label(
            self.analysis_panel,
            text="AI-assisted screening only — not a medical diagnosis.",
            bg="#ffffff",
            fg="#475569",
            font=("Segoe UI", 10, "italic"),
            justify=tk.LEFT,
            wraplength=330,
            anchor="w",
        )
        self.disclaimer.pack(anchor="w", pady=12)

        self.status_row = tk.Frame(self.root, bg="#edf6ff", padx=20, pady=12)
        self.status_row.pack(fill=tk.X)

        self.status_indicator = tk.Label(self.status_row, text="●", fg="#22c55e", bg="#edf6ff", font=("Segoe UI", 16, "bold"))
        self.status_indicator.pack(side=tk.LEFT)

        self.status_label = tk.Label(self.status_row, text="Camera Connected", bg="#edf6ff", fg="#0f172a", font=("Segoe UI", 10, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=10)

        self.pose_status_label = tk.Label(self.status_row, text="Pose Detection Active", bg="#edf6ff", fg="#475569", font=("Segoe UI", 10))
        self.pose_status_label.pack(side=tk.LEFT)

        self.control_frame = tk.Frame(self.root, bg="#edf6ff", padx=20, pady=20)
        self.control_frame.pack(fill=tk.X)

        self.camera_btn = ttk.Button(self.control_frame, text="Start Camera", command=self.start_camera_flow)
        self.camera_btn.pack(side=tk.LEFT, padx=12)

        self.start_btn = ttk.Button(self.control_frame, text="Start Screening", command=self.start_screening)
        self.start_btn.pack(side=tk.LEFT, padx=12)

        self.stop_btn = ttk.Button(self.control_frame, text="Stop Screening", command=self.stop_screening)
        self.stop_btn.pack(side=tk.LEFT)

        self.set_mode("live")
        self.ensure_previews()

    def make_metric_block(self, title, value, subtitle):
        frame = tk.Frame(self.analysis_panel, bg="#f8fbff", padx=12, pady=10)
        frame.pack(fill=tk.X, pady=6)
        title_label = tk.Label(frame, text=title, bg="#f8fbff", fg="#475569", font=("Segoe UI", 10, "bold"), anchor="w")
        title_label.pack(anchor="w")
        value_label = tk.Label(frame, text=value, bg="#f8fbff", fg="#0f172a", font=("Segoe UI", 21, "bold"), anchor="w")
        value_label.pack(anchor="w", pady=4)
        sub_label = tk.Label(frame, text=subtitle, bg="#f8fbff", fg="#64748b", font=("Segoe UI", 9), anchor="w")
        sub_label.pack(anchor="w")
        return {"frame": frame, "value": value_label, "title": title_label, "sub": sub_label}

    def set_mode(self, mode):
        self.current_mode = mode
        for key, btn in self.mode_buttons.items():
            if key == mode:
                btn.config(bg="#dbeafe", relief="solid", bd=2, highlightbackground="#2563eb")
            else:
                btn.config(bg="#ffffff", relief="flat", bd=1, highlightbackground="#e2e8f0")

        if mode == "live":
            self.analysis_title.config(text="LIVE ANALYSIS")
            self.status_label.config(text="Camera Connected")
            self.pose_status_label.config(text="Pose Detection Active")
            self.status_indicator.config(fg="#22c55e")
        elif mode == "photo":
            self.analysis_title.config(text="PHOTO ANALYSIS")
            self.status_label.config(text="Image Ready")
            self.pose_status_label.config(text="Static Pose Analysis")
            self.status_indicator.config(fg="#3b82f6")
        elif mode == "video":
            self.analysis_title.config(text="VIDEO ANALYSIS")
            self.status_label.config(text="Video Ready")
            self.pose_status_label.config(text="Movement Tracking")
            self.status_indicator.config(fg="#8b5cf6")

    def ensure_previews(self):
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            placeholder,
            "SWASTHGATI\nKnee Risk Screening",
            (120, 220),
            cv2.FONT_HERSHEY_COMPLEX,
            1.0,
            (255, 255, 255),
            2,
        )
        self.update_preview_image(placeholder)

    def update_preview_image(self, frame):
        if frame is None:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image = ImageOps.contain(image, (640, 480))
        photo = ImageTk.PhotoImage(image)
        self.preview_photo = photo
        self.preview_label.configure(image=photo)

    def start_camera_flow(self):
        if YOLO is None:
            messagebox.showerror("Missing dependency", "YOLOv8 is not installed. Please run: pip install ultralytics")
            return
        self.set_mode("live")
        self.stop_screening(release_only=True)
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Camera error", "Could not open the laptop webcam. Check camera permission or another app is using it.")
            return
        self.camera_running = True
        self.status_label.config(text="Camera Connected")
        self.status_indicator.config(fg="#22c55e")
        self.pose_status_label.config(text="Pose Detection Active")
        self.root.after(30, self.update_camera_loop)

    def stop_screening(self, release_only=False):
        self.screening_active = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.camera_running = False
        if not release_only:
            self.status_label.config(text="Camera Stopped")
            self.pose_status_label.config(text="Ready to begin")
            self.status_indicator.config(fg="#f59e0b")
            self.ensure_previews()

    def start_screening(self):
        if not self.camera_running:
            messagebox.showwarning("Camera not ready", "Please click '📷 LIVE CAMERA' before starting screening.")
            return
        self.screening_active = True
        self.status_label.config(text="Screening Active")
        self.pose_status_label.config(text="Collecting movement data")
        self.status_indicator.config(fg="#22c55e")

    def update_camera_loop(self):
        if not self.camera_running or self.cap is None:
            return
        ok, frame = self.cap.read()
        if not ok:
            self.status_label.config(text="Camera Failed")
            self.pose_status_label.config(text="Unable to read frames")
            self.status_indicator.config(fg="#ef4444")
            self.camera_running = False
            return

        result = self.pose_analyzer.analyze_frame(frame)
        if result["valid"]:
            self.update_analysis_panel(result)
            if self.screening_active:
                self.result_value.config(text=f"{result['risk_level']} RISK")
                self.result_note.config(text=f"Possible markers: {self.risk_markers_text(result)}")
        else:
            self.update_analysis_panel_default(result["status"])

        self.update_preview_image(result["annotated"])
        self.root.after(30, self.update_camera_loop)

    def risk_markers_text(self, result):
        markers = []
        if result.get("symmetry_pct", 100) < 85:
            markers.append("movement asymmetry")
        if result.get("left_knee_angle", 0) < 60 or result.get("right_knee_angle", 0) < 60:
            markers.append("reduced range of motion")
        if not markers:
            markers.append("no major posture/marker trend detected")
        return "; ".join(markers)

    def update_analysis_panel(self, result):
        left_angle = result.get("left_knee_angle", 0.0)
        right_angle = result.get("right_knee_angle", 0.0)
        symmetry = result.get("symmetry_pct", 0.0)
        status = "Normal" if symmetry >= 85 else "Possible abnormality"
        alignment = "Normal" if abs(left_angle - right_angle) < 15 else "Possible variation"
        movement = "Normal" if symmetry >= 80 else "Possible abnormality"

        self.metric_left["value"].config(text=f"{left_angle:.1f}°")
        self.metric_right["value"].config(text=f"{right_angle:.1f}°")
        self.metric_sym["value"].config(text=f"{symmetry:.1f}%")
        self.metric_status["value"].config(text=status)

        self.metric_left["sub"].config(text=f"Movement: {movement}\nAlignment: {alignment}")
        self.metric_right["sub"].config(text=f"Movement: {movement}\nAlignment: {alignment}")
        self.metric_sym["sub"].config(text="Left / Right symmetry")
        self.metric_status["sub"].config(text="Current pattern")

        risk = result.get("risk_level", "LOW")
        self.result_value.config(text=f"{risk} RISK")
        self.result_note.config(text=f"Possible markers: {self.risk_markers_text(result)}")

    def update_analysis_panel_default(self, message):
        self.metric_left["value"].config(text="--")
        self.metric_right["value"].config(text="--")
        self.metric_sym["value"].config(text="--")
        self.metric_status["value"].config(text="Unknown")
        self.metric_left["sub"].config(text="Movement: Unavailable")
        self.metric_right["sub"].config(text="Alignment: Unavailable")
        self.metric_sym["sub"].config(text="Left / Right")
        self.metric_status["sub"].config(text="Current pattern")
        self.result_value.config(text="LOW RISK")
        self.result_note.config(text=message)

    def upload_photo(self):
        if YOLO is None:
            messagebox.showerror("Missing dependency", "YOLOv8 is required for photo analysis. Install ultralytics.")
            return
        self.set_mode("photo")
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])
        if not file_path:
            return

        result = self.pose_analyzer.analyze_image(file_path)
        if not result["valid"]:
            messagebox.showwarning("Analysis failed", result["status"])
            self.result_note.config(text=result["status"])
            return

        image = cv2.imread(file_path)
        if image is not None:
            self.update_preview_image(result["annotated"])
        self.update_analysis_panel(result)
        self.result_value.config(text=f"{result['risk_level']} RISK")
        self.result_note.config(text=f"Possible markers: {self.risk_markers_text(result)}")
        self.status_label.config(text="Image Processed")
        self.pose_status_label.config(text="Static pose analysis complete")

    def upload_video(self):
        if YOLO is None:
            messagebox.showerror("Missing dependency", "YOLOv8 is required for video analysis. Install ultralytics.")
            return
        self.set_mode("video")
        file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv")])
        if not file_path:
            return

        self.status_label.config(text="Analyzing video")
        self.pose_status_label.config(text="Tracking knee movement")
        self.root.update_idletasks()

        result = self.pose_analyzer.analyze_video(file_path)
        if not result["valid"]:
            messagebox.showwarning("Video analysis failed", result["status"])
            self.result_note.config(text=result["status"])
            return

        self.update_analysis_panel(result)
        self.result_value.config(text=f"{result['risk_level']} RISK")
        self.result_note.config(text=f"Possible markers: {self.risk_markers_text(result)}")
        self.status_label.config(text="Video Processed")
        self.pose_status_label.config(text="Movement analysis complete")

        processed_video_path = result.get("processed_video")
        if processed_video_path:
            self.result_note.config(text=f"Processed output: {processed_video_path}\n{self.risk_markers_text(result)}")


def main():
    if YOLO is None:
        print("YOLOv8 import failed:", YOLO_IMPORT_ERROR)
        print("Install the dependencies with: pip install ultralytics opencv-python pillow")

    root = tk.Tk()
    app = SwasthGatiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
