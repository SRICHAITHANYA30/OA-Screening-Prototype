"""
Fusion Engine: Combine all three evidence streams into unified risk score
Weighted ensemble of clinical, gait, and X-ray evidence
Research-backed weighting from literature (KOA detection, TinyML 2026)
"""

import numpy as np
import pandas as pd
import json
from datetime import datetime
from pathlib import Path


class EvidenceFusionEngine:
    """
    Fuse three independent evidence streams into single KOA risk prediction.
    
    Weighting scheme based on published benchmarks:
    - Clinical/WOMAC: 35% (interpretability, universal applicability)
    - Gait/IMU: 35% (high accuracy ~97%, dual-IMU TinyML 2026)
    - X-ray KL grading: 30% (gold standard but requires imaging)
    
    Output: Unified KOA risk score 0-100 + risk category
    """
    
    # Evidence stream weights (must sum to 1.0)
    STREAM_WEIGHTS = {
        'clinical': 0.35,
        'gait': 0.35,
        'xray': 0.30
    }
    
    # Risk thresholds for categorization
    RISK_THRESHOLDS = {
        'normal': 20,           # 0-20: Normal/healthy
        'mild': 40,             # 21-40: Mild OA
        'moderate': 60,         # 41-60: Moderate OA
        'severe': 80,           # 61-80: Severe OA
        'critical': 100         # 81-100: Critical/advanced OA
    }
    
    # Cost model for deployment (₹ per screening)
    COST_MODEL = {
        'phc_kit_cost': 20000,      # ₹16-25k per Primary Health Centre kit
        'per_screening': 1.5,        # <₹2 per screen
        'samples_per_kit': 15000,    # Break-even ~15k screens
    }
    
    def __init__(self, use_weighted=True):
        self.use_weighted = use_weighted
        self.fusion_history = []
        self.individual_scores = {}
    
    def normalize_clinical_score(self, clinical_result):
        """
        Convert clinical/WOMAC risk to 0-100 score.
        Input: dict with 'risk_class' and 'risk_score'
        """
        risk_to_score = {
            'Normal': 10,
            'Mild': 35,
            'Moderate': 60,
            'Severe': 85
        }
        
        base_score = risk_to_score.get(clinical_result.get('risk_class', 'Normal'), 10)
        confidence = clinical_result.get('risk_score', 0.5)
        
        # Adjust by confidence (higher confidence = more extreme score)
        normalized = base_score * confidence
        
        return float(np.clip(normalized, 0, 100))
    
    def normalize_gait_score(self, gait_features):
        """
        Convert gait/IMU features to 0-100 risk score.
        Features indicating higher OA risk:
        - Reduced knee symmetry (should be close to 1.0)
        - Increased angular velocity (sign of compensation)
        - Reduced cadence (slower walking speed)
        - High knee angle variance (irregular gait)
        """
        score = 50  # Baseline
        
        # Knee symmetry: closer to 1.0 is better
        if 'knee_symmetry' in gait_features:
            symmetry = gait_features['knee_symmetry']
            asymmetry_penalty = (1.0 - symmetry) * 30  # 0-30 point penalty
            score -= asymmetry_penalty
        
        # Angular velocity: elevated values indicate compensation
        if 'angular_velocity_std' in gait_features:
            ang_vel = gait_features['angular_velocity_std']
            velocity_penalty = min(ang_vel * 15, 20)  # 0-20 point penalty
            score += velocity_penalty
        
        # Cadence: slower walking is concerning
        if 'cadence' in gait_features:
            cadence = gait_features['cadence']
            # Normal cadence: 110-120 steps/min
            if cadence < 90:
                cadence_penalty = (90 - cadence) * 0.3
                score += min(cadence_penalty, 15)
        
        # Knee angle variance: high variance = irregular gait
        if 'left_knee_angle_std' in gait_features:
            knee_var = gait_features['left_knee_angle_std']
            if knee_var > 10:
                var_penalty = (knee_var - 10) * 2
                score += min(var_penalty, 15)
        
        return float(np.clip(score, 0, 100))
    
    def normalize_xray_score(self, xray_result):
        """
        Convert X-ray KL grade to 0-100 risk score.
        KL grade directly maps to severity:
        0 (Normal) = 5, 1 (Doubtful) = 25, 2 (Minimal) = 45,
        3 (Moderate) = 70, 4 (Severe) = 95
        """
        kl_to_score = {
            0: 5,      # Normal
            1: 25,     # Doubtful OA
            2: 45,     # Minimal OA
            3: 70,     # Moderate OA
            4: 95      # Severe OA
        }
        
        kl_grade = xray_result.get('kl_grade', 0)
        base_score = kl_to_score.get(kl_grade, 50)
        confidence = xray_result.get('confidence', 0.7)
        
        # Adjust by model confidence
        normalized = base_score * confidence + (100 - base_score) * (1 - confidence)
        
        return float(np.clip(normalized, 0, 100))
    
    def fuse_evidence(self, clinical_result=None, gait_features=None, xray_result=None):
        """
        Fuse all three evidence streams into single risk assessment.
        
        Args:
            clinical_result: dict from WOMAC model
            gait_features: dict from gait analysis
            xray_result: dict from X-ray KL classification
        
        Returns:
            dict with unified risk score, category, and reasoning
        """
        # Normalize each stream to 0-100
        clinical_score = 50  # Default if missing
        gait_score = 50
        xray_score = 50
        available_streams = 0
        
        if clinical_result is not None:
            clinical_score = self.normalize_clinical_score(clinical_result)
            available_streams += 1
        
        if gait_features is not None:
            gait_score = self.normalize_gait_score(gait_features)
            available_streams += 1
        
        if xray_result is not None:
            xray_score = self.normalize_xray_score(xray_result)
            available_streams += 1
        
        # Store individual scores
        self.individual_scores = {
            'clinical': clinical_score if clinical_result else None,
            'gait': gait_score if gait_features else None,
            'xray': xray_score if xray_result else None,
        }
        
        # Weighted fusion
        if self.use_weighted:
            total_weight = sum(self.STREAM_WEIGHTS.values())
            fused_score = (
                clinical_score * self.STREAM_WEIGHTS['clinical'] +
                gait_score * self.STREAM_WEIGHTS['gait'] +
                xray_score * self.STREAM_WEIGHTS['xray']
            ) / total_weight
        else:
            # Simple average of available streams
            all_scores = [
                clinical_score if clinical_result else None,
                gait_score if gait_features else None,
                xray_score if xray_result else None
            ]
            valid_scores = [s for s in all_scores if s is not None]
            fused_score = np.mean(valid_scores) if valid_scores else 50.0
        
        # Categorize risk
        if fused_score <= self.RISK_THRESHOLDS['normal']:
            risk_category = 'NORMAL'
            recommendation = 'No evidence of OA. Regular follow-up recommended.'
        elif fused_score <= self.RISK_THRESHOLDS['mild']:
            risk_category = 'MILD'
            recommendation = 'Mild signs of OA. Annual screening recommended.'
        elif fused_score <= self.RISK_THRESHOLDS['moderate']:
            risk_category = 'MODERATE'
            recommendation = 'Moderate OA detected. Refer to orthopedics. Consider intervention.'
        elif fused_score <= self.RISK_THRESHOLDS['severe']:
            risk_category = 'SEVERE'
            recommendation = 'Severe OA. Immediate specialist consultation required.'
        else:
            risk_category = 'CRITICAL'
            recommendation = 'Advanced OA. Urgent orthopedic intervention needed.'
        
        # Confidence: based on agreement between streams
        scores = [s for s in self.individual_scores.values() if s is not None]
        if len(scores) > 1:
            variance = np.var(scores)
            # Lower variance = higher confidence
            confidence = 1.0 - min(variance / 1000, 1.0)
        else:
            confidence = 0.7  # Lower confidence with only one stream
        
        result = {
            'unified_risk_score': float(fused_score),
            'risk_category': risk_category,
            'confidence': float(confidence),
            'recommendation': recommendation,
            'individual_scores': self.individual_scores,
            'available_streams': available_streams,
            'timestamp': datetime.now().isoformat(),
            'thresholds': self.RISK_THRESHOLDS
        }
        
        self.fusion_history.append(result)
        
        return result
    
    def generate_patient_report(self, patient_id, fusion_result, clinical_data=None):
        """
        Generate comprehensive patient screening report.
        """
        report = {
            'report_id': f"SWASTHGATI_{patient_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'patient_id': patient_id,
            'timestamp': datetime.now().isoformat(),
            'screening_summary': {
                'unified_risk_score': fusion_result['unified_risk_score'],
                'risk_category': fusion_result['risk_category'],
                'confidence': fusion_result['confidence'],
                'recommendation': fusion_result['recommendation'],
            },
            'evidence_details': {
                'clinical_score': fusion_result['individual_scores'].get('clinical'),
                'gait_score': fusion_result['individual_scores'].get('gait'),
                'xray_score': fusion_result['individual_scores'].get('xray'),
            },
            'quality_metrics': {
                'data_completeness': f"{fusion_result['available_streams']}/3 streams",
                'prediction_confidence': f"{fusion_result['confidence']:.2%}",
            },
            'clinical_context': clinical_data or {},
            'next_steps': self._get_next_steps(fusion_result['risk_category']),
        }
        
        return report
    
    def _get_next_steps(self, risk_category):
        """Get recommended next steps based on risk category."""
        recommendations = {
            'NORMAL': [
                'Continue regular physical activity',
                'Annual screening recommended',
                'Maintain healthy BMI'
            ],
            'MILD': [
                'Annual screening advised',
                'Consider physical therapy exercises',
                'Monitor symptoms',
                'Weight management if BMI elevated'
            ],
            'MODERATE': [
                'Refer to orthopedic specialist within 3 months',
                'Baseline comprehensive X-ray imaging',
                'Consider pharmacological intervention',
                'Physical therapy program'
            ],
            'SEVERE': [
                'Specialist consultation within 1 month',
                'Advanced imaging (MRI/CT) consideration',
                'Possible surgical intervention discussion',
                'Pain management program'
            ],
            'CRITICAL': [
                'Urgent specialist consultation',
                'Pre-operative evaluation if surgery indicated',
                'Advanced imaging and assessment',
                'Multidisciplinary care team involvement'
            ]
        }
        
        return recommendations.get(risk_category, [])
    
    def get_cost_analysis(self, num_screenings=1000, num_phc_kits=1):
        """
        Calculate cost efficiency for deployment.
        """
        total_kit_cost = num_phc_kits * self.COST_MODEL['phc_kit_cost']
        total_screening_cost = num_screenings * self.COST_MODEL['per_screening']
        total_cost = total_kit_cost + total_screening_cost
        cost_per_screening = total_cost / max(num_screenings, 1)
        
        return {
            'num_phc_kits': num_phc_kits,
            'num_screenings': num_screenings,
            'kit_cost_total': total_kit_cost,
            'screening_cost_total': total_screening_cost,
            'total_cost': total_cost,
            'cost_per_screening': cost_per_screening,
            'breakeven_screenings': self.COST_MODEL['samples_per_kit'],
            'currency': '₹ (Indian Rupees)'
        }


def demo_fusion_engine():
    """Demonstrate the fusion engine."""
    print("\n" + "="*70)
    print("FUSION ENGINE: Multi-stream Evidence Integration")
    print("="*70)
    
    # Initialize engine
    print("\n[1] Initializing fusion engine...")
    engine = EvidenceFusionEngine(use_weighted=True)
    print(f"  - Weighting: Weighted ensemble (35% clinical, 35% gait, 30% X-ray)")
    print(f"  - Cost model: ₹{engine.COST_MODEL['phc_kit_cost']}/kit, <₹{engine.COST_MODEL['per_screening']}/screen")
    
    # Simulate patient screening
    print("\n[2] Simulating complete patient screening...")
    
    # Mock clinical result
    clinical_result = {
        'risk_class': 'Mild',
        'risk_score': 0.65,
        'probabilities': {'Normal': 0.2, 'Mild': 0.65, 'Moderate': 0.1, 'Severe': 0.05}
    }
    
    # Mock gait features
    gait_features = {
        'left_knee_angle_mean': 165.0,
        'left_knee_angle_std': 12.0,
        'right_knee_angle_mean': 168.0,
        'right_knee_angle_std': 10.0,
        'stride_length_mean': 0.68,
        'stride_length_std': 0.08,
        'knee_symmetry': 0.85,
        'cadence': 105.0,
        'angular_velocity_mean': 0.15,
        'angular_velocity_std': 0.08,
    }
    
    # Mock X-ray result
    xray_result = {
        'kl_grade': 1,
        'kl_description': 'Doubtful',
        'confidence': 0.72,
        'probabilities': {
            'Grade_0_(Normal)': 0.15,
            'Grade_1_(Doubtful)': 0.72,
            'Grade_2_(Minimal)': 0.10,
            'Grade_3_(Moderate)': 0.02,
            'Grade_4_(Severe)': 0.01
        }
    }
    
    # Fuse evidence
    print("  - Clinical/WOMAC: Mild (65% confidence)")
    print("  - Gait/IMU: Knee symmetry 0.85, cadence 105 steps/min")
    print("  - X-ray KL: Grade 1 - Doubtful (72% confidence)")
    
    fusion_result = engine.fuse_evidence(
        clinical_result=clinical_result,
        gait_features=gait_features,
        xray_result=xray_result
    )
    
    print("\n[3] Fusion results:")
    print(f"  - Unified Risk Score: {fusion_result['unified_risk_score']:.1f}/100")
    print(f"  - Risk Category: {fusion_result['risk_category']}")
    print(f"  - Prediction Confidence: {fusion_result['confidence']:.1%}")
    print(f"  - Available evidence streams: {fusion_result['available_streams']}/3")
    print(f"  - Recommendation: {fusion_result['recommendation']}")
    
    print("\n  Individual stream scores:")
    for stream, score in fusion_result['individual_scores'].items():
        if score is not None:
            print(f"    • {stream.upper()}: {score:.1f}/100")
    
    # Generate patient report
    print("\n[4] Generating comprehensive screening report...")
    report = engine.generate_patient_report(
        patient_id='P001',
        fusion_result=fusion_result,
        clinical_data={'age': 58, 'bmi': 29.5, 'gender': 'F'}
    )
    
    print(f"  Report ID: {report['report_id']}")
    print(f"  Risk Category: {report['screening_summary']['risk_category']}")
    print(f"  Next steps:")
    for i, step in enumerate(report['next_steps'], 1):
        print(f"    {i}. {step}")
    
    # Cost analysis
    print("\n[5] Cost model for deployment:")
    cost = engine.get_cost_analysis(num_screenings=5000, num_phc_kits=2)
    print(f"  - PHC kits needed: {cost['num_phc_kits']}")
    print(f"  - Screenings planned: {cost['num_screenings']}")
    print(f"  - Kit cost total: ₹{cost['kit_cost_total']:,}")
    print(f"  - Screening cost total: ₹{cost['screening_cost_total']:,}")
    print(f"  - Total cost: ₹{cost['total_cost']:,}")
    print(f"  - Cost per screening: ₹{cost['cost_per_screening']:.2f}")
    print(f"  - Break-even screenings: {cost['breakeven_screenings']}")
    
    print("\n✓ Fusion engine demonstration complete")
    
    return engine, report


if __name__ == '__main__':
    demo_fusion_engine()
