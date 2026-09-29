"""
Evidence Stream 2: Movement Capture & Gait Analysis
MediaPipe BlazePose + Dual-IMU (ESP32/MPU6050) for gait feature extraction
Features: stride length, cadence, knee angles, angular velocity, stride symmetry
"""

import numpy as np
import pandas as pd
from collections import deque
import json
from datetime import datetime
from pathlib import Path
try:
    import mediapipe as mp
    import cv2
    MEDIAPIPE_AVAILABLE = hasattr(mp, 'solutions') and hasattr(mp.solutions, 'pose')
except ImportError:
    MEDIAPIPE_AVAILABLE = False

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class GaitFeatureExtractor:
    """
    Extract gait features from video (MediaPipe BlazePose) or IMU sensors.
    """
    
    # Mediapipe pose landmarks for lower body
    POSE_LANDMARKS = {
        'left_hip': 23,
        'right_hip': 24,
        'left_knee': 25,
        'right_knee': 26,
        'left_ankle': 27,
        'right_ankle': 28,
    }
    
    def __init__(self, use_mediapipe=True, use_imu=False):
        self.use_mediapipe = use_mediapipe and MEDIAPIPE_AVAILABLE
        self.use_imu = use_imu and SERIAL_AVAILABLE
        
        self.pose_history = deque(maxlen=30)  # 30-frame window at 30fps = 1 second
        self.imu_history = deque(maxlen=100)
        self.gait_events = []
        
        if self.use_mediapipe:
            try:
                self.mp_pose = mp.solutions.pose
                self.pose = self.mp_pose.Pose(
                    static_image_mode=False,
                    model_complexity=1,
                    smooth_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
            except Exception:
                self.use_mediapipe = False
    
    def extract_mediapipe_features(self, frame):
        """
        Extract pose keypoints from video frame using MediaPipe.
        Returns normalized 3D landmarks.
        """
        if not self.use_mediapipe:
            return None
        
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(frame_rgb)
        
        if results.pose_landmarks:
            landmarks = {}
            for name, idx in self.POSE_LANDMARKS.items():
                lm = results.pose_landmarks.landmark[idx]
                landmarks[name] = [lm.x, lm.y, lm.z]
            return landmarks
        
        return None
    
    def calculate_angle(self, p1, p2, p3):
        """
        Calculate angle at p2 formed by p1-p2-p3.
        Returns angle in degrees.
        """
        v1 = np.array(p1) - np.array(p2)
        v2 = np.array(p3) - np.array(p2)
        
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.arccos(cos_angle) * 180 / np.pi
        
        return angle
    
    def calculate_distance(self, p1, p2):
        """Calculate Euclidean distance between two points."""
        return np.linalg.norm(np.array(p1) - np.array(p2))
    
    def compute_gait_metrics(self):
        """
        Compute gait metrics from pose history.
        Returns dict with stride length, cadence, knee angles, etc.
        """
        if len(self.pose_history) < 10:
            return None
        
        landmarks_list = list(self.pose_history)
        
        # Knee angles over time
        left_knee_angles = []
        right_knee_angles = []
        
        for landmarks in landmarks_list:
            if all(k in landmarks for k in ['left_hip', 'left_knee', 'left_ankle']):
                lka = self.calculate_angle(
                    landmarks['left_hip'],
                    landmarks['left_knee'],
                    landmarks['left_ankle']
                )
                left_knee_angles.append(lka)
            
            if all(k in landmarks for k in ['right_hip', 'right_knee', 'right_ankle']):
                rka = self.calculate_angle(
                    landmarks['right_hip'],
                    landmarks['right_knee'],
                    landmarks['right_ankle']
                )
                right_knee_angles.append(rka)
        
        # Stride length estimation (distance between ankles over time)
        stride_lengths = []
        for landmarks in landmarks_list:
            if 'left_ankle' in landmarks and 'right_ankle' in landmarks:
                stride = self.calculate_distance(
                    landmarks['left_ankle'],
                    landmarks['right_ankle']
                )
                stride_lengths.append(stride)
        
        # Calculate metrics
        metrics = {
            'left_knee_angle_mean': np.mean(left_knee_angles) if left_knee_angles else 0,
            'left_knee_angle_std': np.std(left_knee_angles) if left_knee_angles else 0,
            'right_knee_angle_mean': np.mean(right_knee_angles) if right_knee_angles else 0,
            'right_knee_angle_std': np.std(right_knee_angles) if right_knee_angles else 0,
            'stride_length_mean': np.mean(stride_lengths) if stride_lengths else 0,
            'stride_length_std': np.std(stride_lengths) if stride_lengths else 0,
            'knee_symmetry': self.calculate_knee_symmetry(left_knee_angles, right_knee_angles),
            'cadence': self.estimate_cadence(landmarks_list),
        }
        
        return metrics
    
    def calculate_knee_symmetry(self, left_angles, right_angles):
        """
        Calculate knee angle symmetry ratio.
        1.0 = perfect symmetry, <1.0 indicates asymmetry.
        """
        if not left_angles or not right_angles:
            return 0.0
        
        left_mean = np.mean(left_angles)
        right_mean = np.mean(right_angles)
        
        if left_mean == 0 or right_mean == 0:
            return 0.0
        
        ratio = min(left_mean, right_mean) / max(left_mean, right_mean)
        return float(ratio)
    
    def estimate_cadence(self, landmarks_list):
        """
        Estimate walking cadence (steps per minute).
        Based on knee angle oscillations.
        """
        if len(landmarks_list) < 5:
            return 0.0
        
        # Count knee angle oscillations as proxy for cadence
        # At 30fps, one complete gait cycle ~ 60-80 frames
        # Simplified: count local minima in knee angles
        knee_angles = []
        for landmarks in landmarks_list:
            if 'left_knee' in landmarks:
                angle = self.calculate_angle(
                    landmarks['left_hip'],
                    landmarks['left_knee'],
                    landmarks['left_ankle']
                )
                knee_angles.append(angle)
        
        if len(knee_angles) < 3:
            return 0.0
        
        # Simple cadence estimation: ~60-120 steps/min for normal walking
        oscillations = sum(1 for i in range(1, len(knee_angles)-1) 
                         if knee_angles[i] < knee_angles[i-1] and 
                            knee_angles[i] < knee_angles[i+1])
        
        # Approximate cadence
        fps = 30
        duration_sec = len(knee_angles) / fps
        cadence_hz = oscillations / max(duration_sec, 0.1)
        cadence_per_min = cadence_hz * 60 * 2  # 2 knees, count as full gait cycle
        
        return float(np.clip(cadence_per_min, 0, 150))
    
    def process_video_frame(self, frame):
        """Process single video frame and update history."""
        landmarks = self.extract_mediapipe_features(frame)
        if landmarks:
            self.pose_history.append(landmarks)
            return True
        return False
    
    def process_imu_data(self, accel, gyro):
        """
        Process IMU data from dual sensors (e.g., ESP32 + MPU6050).
        accel: [ax, ay, az] acceleration
        gyro: [gx, gy, gz] angular velocity
        """
        imu_frame = {
            'timestamp': datetime.now().isoformat(),
            'accel': accel,
            'gyro': gyro,
            'magnitude_accel': np.linalg.norm(accel),
            'magnitude_gyro': np.linalg.norm(gyro),
        }
        self.imu_history.append(imu_frame)
    
    def compute_imu_gait_features(self):
        """
        Compute gait features from IMU data.
        Returns angular velocity metrics and acceleration patterns.
        """
        if len(self.imu_history) < 30:
            return None
        
        data_list = list(self.imu_history)
        
        gyro_mags = [d['magnitude_gyro'] for d in data_list]
        accel_mags = [d['magnitude_accel'] for d in data_list]
        
        gyro_values = np.array([d['gyro'] for d in data_list])
        accel_values = np.array([d['accel'] for d in data_list])
        
        metrics = {
            'angular_velocity_mean': float(np.mean(gyro_mags)),
            'angular_velocity_std': float(np.std(gyro_mags)),
            'acceleration_mean': float(np.mean(accel_mags)),
            'acceleration_std': float(np.std(accel_mags)),
            'gyro_x_range': float(np.max(gyro_values[:, 0]) - np.min(gyro_values[:, 0])),
            'gyro_y_range': float(np.max(gyro_values[:, 1]) - np.min(gyro_values[:, 1])),
            'gyro_z_range': float(np.max(gyro_values[:, 2]) - np.min(gyro_values[:, 2])),
        }
        
        return metrics
    
    def get_all_features(self):
        """Get combined features from vision and IMU."""
        vision_features = self.compute_gait_metrics() or {}
        imu_features = self.compute_imu_gait_features() or {}
        
        return {**vision_features, **imu_features}


class IMUSimulator:
    """
    Simulate dual-IMU sensor data for testing without hardware.
    In production, this would connect via pyserial to ESP32/MPU6050.
    """
    
    def __init__(self, sample_rate=100):
        self.sample_rate = sample_rate
        self.sample_count = 0
    
    def generate_gait_imu_data(self):
        """
        Generate realistic gait-pattern IMU data.
        Simulates one complete gait cycle (~1 second at 100Hz = 100 samples).
        """
        t = (self.sample_count % self.sample_rate) / self.sample_rate
        phase = 2 * np.pi * t
        
        # Simulated gyroscope data (angular velocity)
        gyro = np.array([
            0.5 * np.sin(phase),           # X-axis rotation
            0.3 * np.sin(phase + np.pi/3), # Y-axis rotation  
            0.2 * np.sin(phase + 2*np.pi/3), # Z-axis rotation
        ])
        
        # Simulated accelerometer data
        accel = np.array([
            9.8 + 0.5 * np.sin(phase),     # X-axis acceleration
            0.2 * np.cos(phase),            # Y-axis acceleration
            0.3 * np.sin(2*phase),          # Z-axis acceleration
        ])
        
        self.sample_count += 1
        return accel, gyro


def demo_stream2():
    """Demonstrate Evidence Stream 2."""
    print("\n" + "="*70)
    print("EVIDENCE STREAM 2: Movement Capture & Gait Analysis")
    print("="*70)
    
    # Initialize gait extractor (MediaPipe disabled if not available)
    print("\n[1] Initializing Gait Feature Extractor...")
    gait_extractor = GaitFeatureExtractor(use_mediapipe=MEDIAPIPE_AVAILABLE, use_imu=True)
    print(f"  - MediaPipe support: {'✓' if MEDIAPIPE_AVAILABLE else '✗'}")
    print(f"  - IMU support: Enabled (simulated)")
    
    # Simulate IMU data collection
    print("\n[2] Simulating dual-IMU data collection (ESP32 + MPU6050)...")
    imu_sim = IMUSimulator(sample_rate=100)
    
    for i in range(150):  # 1.5 seconds of data at 100Hz
        accel, gyro = imu_sim.generate_gait_imu_data()
        gait_extractor.process_imu_data(accel, gyro)
    
    print(f"  - Collected 150 IMU samples (1.5 seconds @ 100Hz)")
    
    # Compute gait features
    print("\n[3] Computing gait metrics from IMU data...")
    imu_features = gait_extractor.compute_imu_gait_features()
    
    if imu_features:
        print("  IMU Gait Features:")
        for key, value in imu_features.items():
            print(f"    - {key}: {value:.4f}")
    
    # Simulate video-based pose estimation
    print("\n[4] Simulating MediaPipe pose extraction...")
    if MEDIAPIPE_AVAILABLE:
        # Create synthetic pose landmarks
        for i in range(30):
            synthetic_landmarks = {
                'left_hip': [0.4, 0.5, 0.1],
                'right_hip': [0.6, 0.5, 0.1],
                'left_knee': [0.4, 0.65, 0.15],
                'right_knee': [0.6, 0.65, 0.15],
                'left_ankle': [0.4 + 0.05*np.sin(i*0.3), 0.8, 0.2],
                'right_ankle': [0.6 + 0.05*np.sin(i*0.3 + np.pi), 0.8, 0.2],
            }
            gait_extractor.pose_history.append(synthetic_landmarks)
        
        vision_features = gait_extractor.compute_gait_metrics()
        print("  Vision-Based Gait Features:")
        for key, value in vision_features.items():
            print(f"    - {key}: {value:.4f}")
    else:
        print("  ⚠ MediaPipe not available - skipping vision-based features")
    
    # Combined features
    print("\n[5] Combined gait feature vector...")
    all_features = gait_extractor.get_all_features()
    print(f"  - Total features extracted: {len(all_features)}")
    print(f"  - Feature vector dimension: {len(all_features)}")
    
    print("\n✓ Evidence Stream 2 demonstration complete")
    
    return gait_extractor


if __name__ == '__main__':
    demo_stream2()
