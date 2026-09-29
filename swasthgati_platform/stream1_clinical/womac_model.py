"""
Evidence Stream 1: Clinical/WOMAC Risk Assessment
LightGBM/XGBoost model for knee osteoarthritis risk stratification
WOMAC (Western Ontario and McMaster Universities Arthritis Index)
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import lightgbm as lgb
import xgboost as xgb
import pickle
import json
from pathlib import Path


class WOMACRiskModel:
    """
    WOMAC-based risk assessment for knee osteoarthritis.
    Features: Pain (24 points), Stiffness (8 points), Function (68 points) = 100 points total
    Risk stratification: Low (0-25), Mild (26-50), Moderate (51-75), Severe (76-100)
    """
    
    def __init__(self, model_type='lightgbm', random_state=42):
        self.model_type = model_type
        self.random_state = random_state
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = None
        self.performance_metrics = {}
        
    def create_synthetic_womac_data(self, n_samples=500):
        """
        Create synthetic WOMAC questionnaire data for training.
        In production, this would come from patient database.
        """
        np.random.seed(self.random_state)
        
        # WOMAC Pain subscale (5 items, 0-4 each)
        pain_items = np.random.randint(0, 5, size=(n_samples, 5))
        pain_score = pain_items.sum(axis=1) * 4.8  # Scale to 0-100
        
        # WOMAC Stiffness subscale (2 items, 0-4 each)
        stiffness_items = np.random.randint(0, 5, size=(n_samples, 2))
        stiffness_score = stiffness_items.sum(axis=1) * 12.5  # Scale to 0-100
        
        # WOMAC Function subscale (17 items, 0-4 each)
        function_items = np.random.randint(0, 5, size=(n_samples, 17))
        function_score = function_items.sum(axis=1) * 1.18  # Scale to 0-100
        
        # Additional clinical features
        age = np.random.normal(60, 10, n_samples)
        age = np.clip(age, 40, 85)
        
        bmi = np.random.normal(28, 4, n_samples)
        bmi = np.clip(bmi, 18, 40)
        
        # Kellgren-Lawrence grade (0-4)
        kl_grade = np.random.randint(0, 5, n_samples)
        
        # History of injury (0-1)
        injury_history = np.random.binomial(1, 0.3, n_samples)
        
        # Target: KOA severity (0=Normal, 1=Mild, 2=Moderate, 3=Severe)
        total_womac = pain_score + stiffness_score + function_score
        y = np.digitize(total_womac, [100, 200, 300]) - 1
        y = np.clip(y, 0, 3)
        
        # Features
        X = np.column_stack([
            pain_score, stiffness_score, function_score, age, bmi, 
            kl_grade, injury_history
        ])
        
        self.feature_names = [
            'pain_score', 'stiffness_score', 'function_score',
            'age', 'bmi', 'kl_grade', 'injury_history'
        ]
        
        return X, y
    
    def train(self, X=None, y=None, test_size=0.2):
        """
        Train the risk model using LightGBM or XGBoost.
        """
        # Generate synthetic data if not provided
        if X is None or y is None:
            X, y = self.create_synthetic_womac_data(n_samples=500)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.random_state, stratify=y
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        if self.model_type == 'lightgbm':
            self.model = lgb.LGBMClassifier(
                num_leaves=31,
                max_depth=5,
                learning_rate=0.05,
                n_estimators=100,
                random_state=self.random_state,
                verbose=-1
            )
        elif self.model_type == 'xgboost':
            self.model = xgb.XGBClassifier(
                max_depth=5,
                learning_rate=0.05,
                n_estimators=100,
                random_state=self.random_state,
                verbosity=0
            )
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
        
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        y_pred_proba = self.model.predict_proba(X_test_scaled)
        
        self.performance_metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, average='weighted', zero_division=0),
            'recall': recall_score(y_test, y_pred, average='weighted', zero_division=0),
            'f1': f1_score(y_test, y_pred, average='weighted', zero_division=0),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'classes': 4,
            'model_type': self.model_type
        }
        
        return self.performance_metrics
    
    def predict_risk(self, womac_features):
        """
        Predict KOA risk from WOMAC features.
        Returns risk score (0-1) and risk category.
        
        Args:
            womac_features: dict with keys {'pain_score', 'stiffness_score', 
                                            'function_score', 'age', 'bmi', 
                                            'kl_grade', 'injury_history'}
        """
        if self.model is None:
            raise ValueError("Model must be trained first")
        
        # Convert dict to array
        feature_order = [
            'pain_score', 'stiffness_score', 'function_score', 'age', 
            'bmi', 'kl_grade', 'injury_history'
        ]
        X = np.array([[womac_features.get(f, 0) for f in feature_order]])
        
        # Scale and predict
        X_scaled = self.scaler.transform(X)
        pred_class = self.model.predict(X_scaled)[0]
        pred_proba = self.model.predict_proba(X_scaled)[0]
        
        risk_score = pred_proba[pred_class]  # Confidence in prediction
        risk_categories = ['Normal', 'Mild', 'Moderate', 'Severe']
        
        return {
            'risk_class': risk_categories[pred_class],
            'risk_score': float(risk_score),
            'probabilities': {
                cat: float(prob) for cat, prob in 
                zip(risk_categories, pred_proba)
            },
            'raw_prediction': int(pred_class)
        }
    
    def save_model(self, model_path):
        """Save trained model and scaler."""
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)
        with open(model_path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names,
                'model_type': self.model_type
            }, f)
    
    def load_model(self, model_path):
        """Load trained model and scaler."""
        with open(model_path, 'rb') as f:
            data = pickle.load(f)
            self.model = data['model']
            self.scaler = data['scaler']
            self.feature_names = data['feature_names']
            self.model_type = data['model_type']
    
    def get_feature_importance(self):
        """Get feature importance from the trained model."""
        if self.model is None:
            raise ValueError("Model must be trained first")
        
        importances = self.model.feature_importances_
        return dict(zip(self.feature_names, importances))


def demo_stream1():
    """Demonstrate Evidence Stream 1."""
    print("\n" + "="*70)
    print("EVIDENCE STREAM 1: Clinical/WOMAC Risk Assessment")
    print("="*70)
    
    # Train LightGBM model
    print("\n[1] Training LightGBM model on synthetic WOMAC data...")
    model_lgb = WOMACRiskModel(model_type='lightgbm')
    metrics_lgb = model_lgb.train()
    
    print(f"  - Training samples: {metrics_lgb['train_samples']}")
    print(f"  - Test samples: {metrics_lgb['test_samples']}")
    print(f"  - Accuracy: {metrics_lgb['accuracy']:.4f}")
    print(f"  - Precision: {metrics_lgb['precision']:.4f}")
    print(f"  - Recall: {metrics_lgb['recall']:.4f}")
    print(f"  - F1-Score: {metrics_lgb['f1']:.4f}")
    
    # Train XGBoost model
    print("\n[2] Training XGBoost model on synthetic WOMAC data...")
    model_xgb = WOMACRiskModel(model_type='xgboost')
    metrics_xgb = model_xgb.train()
    
    print(f"  - Accuracy: {metrics_xgb['accuracy']:.4f}")
    print(f"  - Precision: {metrics_xgb['precision']:.4f}")
    print(f"  - Recall: {metrics_xgb['recall']:.4f}")
    print(f"  - F1-Score: {metrics_xgb['f1']:.4f}")
    
    # Test prediction
    print("\n[3] Sample prediction on patient WOMAC features...")
    test_patient = {
        'pain_score': 45.0,
        'stiffness_score': 30.0,
        'function_score': 65.0,
        'age': 62.0,
        'bmi': 29.5,
        'kl_grade': 2,
        'injury_history': 1
    }
    
    prediction = model_lgb.predict_risk(test_patient)
    print(f"  - Risk Class: {prediction['risk_class']}")
    print(f"  - Risk Score: {prediction['risk_score']:.4f}")
    print(f"  - Probabilities:")
    for cat, prob in prediction['probabilities'].items():
        print(f"      • {cat}: {prob:.4f}")
    
    # Feature importance
    print("\n[4] Feature Importance (LightGBM):")
    importance = model_lgb.get_feature_importance()
    for feat, imp in sorted(importance.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {feat}: {imp:.4f}")
    
    # Save model
    model_lgb.save_model('/tmp/womac_model_lgb.pkl')
    print("\n✓ Model saved to /tmp/womac_model_lgb.pkl")
    
    return model_lgb


if __name__ == '__main__':
    demo_stream1()
