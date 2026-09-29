"""
Evidence Stream 3: X-ray Analysis
U-Net ROI segmentation + EfficientNet/DenseNet for Kellgren-Lawrence (KL) grading
KL grades: 0=Normal, 1=Doubtful, 2=Minimal, 3=Moderate, 4=Severe
"""

import numpy as np
import torch
import torch.nn as nn
from torch.optim import Adam
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
import json
from pathlib import Path


class SimpleUNet(nn.Module):
    """
    Simplified U-Net for knee X-ray ROI segmentation.
    Input: (B, 1, 256, 256) grayscale X-ray
    Output: (B, 1, 256, 256) segmentation mask
    """
    
    def __init__(self):
        super(SimpleUNet, self).__init__()
        
        # Encoder
        self.enc1 = self.conv_block(1, 32)
        self.enc2 = self.conv_block(32, 64)
        self.enc3 = self.conv_block(64, 128)
        
        # Bottleneck
        self.bottleneck = self.conv_block(128, 256)
        
        # Decoder
        self.dec3 = self.conv_block(256 + 128, 128)
        self.dec2 = self.conv_block(128 + 64, 64)
        self.dec1 = self.conv_block(64 + 32, 32)
        
        # Output
        self.out = nn.Conv2d(32, 1, kernel_size=1)
        
        # Pooling and upsampling
        self.pool = nn.MaxPool2d(2, 2)
        self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
    
    def conv_block(self, in_ch, out_ch):
        """Double conv block."""
        return nn.Sequential(
            nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True)
        )
    
    def forward(self, x):
        # Encoder
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        
        # Bottleneck
        b = self.bottleneck(self.pool(e3))
        
        # Decoder with skip connections
        d3 = self.dec3(torch.cat([self.up(b), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up(d2), e1], dim=1))
        
        # Output
        out = self.out(d1)
        return torch.sigmoid(out)


class SimpleEfficientNet(nn.Module):
    """
    Simplified EfficientNet-style classifier for Kellgren-Lawrence grading.
    Input: (B, 1, 256, 256) segmented/preprocessed X-ray
    Output: (B, 5) logits for KL grades 0-4
    """
    
    def __init__(self, num_classes=5):
        super(SimpleEfficientNet, self).__init__()
        
        # Feature extraction
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1))
        )
        
        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(128, num_classes)
        )
        
        self.num_classes = num_classes
    
    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


class XRayDataset(Dataset):
    """Synthetic X-ray dataset for training."""
    
    def __init__(self, X, y, mode='classification'):
        self.X = X
        self.y = y
        self.mode = mode
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, idx):
        img = torch.FloatTensor(self.X[idx:idx+1])
        if self.mode == 'segmentation':
            mask = torch.FloatTensor(self.y[idx])
            return img, mask

        label = torch.tensor(int(self.y[idx]), dtype=torch.long)
        return img, label


class XRayAnalysisPipeline:
    """
    Complete X-ray analysis pipeline: segmentation + KL grading.
    """
    
    def __init__(self, device='cpu'):
        self.device = torch.device(device)
        self.unet = SimpleUNet().to(self.device)
        self.efficientnet = SimpleEfficientNet(num_classes=5).to(self.device)
        
        self.unet_optimizer = Adam(self.unet.parameters(), lr=1e-3)
        self.segmentation_loss = nn.BCELoss()
        
        self.efficientnet_optimizer = Adam(self.efficientnet.parameters(), lr=1e-3)
        self.classification_loss = nn.CrossEntropyLoss()
        
        self.performance_metrics = {}
    
    def generate_synthetic_xray_data(self, n_samples=300):
        """
        Generate synthetic X-ray images with random KL grades.
        In production, this comes from OAI, MOST, or Kaggle datasets.
        """
        np.random.seed(42)
        
        images = []
        labels = []
        masks = []
        
        for i in range(n_samples):
            # Random KL grade (0-4)
            kl_grade = np.random.randint(0, 5)
            
            # Generate synthetic X-ray image
            img = self._generate_synthetic_xray(kl_grade)
            images.append(img)
            labels.append(kl_grade)
            
            # Generate corresponding segmentation mask
            mask = self._generate_synthetic_mask(kl_grade)
            masks.append(mask)
        
        return np.array(images), np.array(labels), np.array(masks)
    
    def _generate_synthetic_xray(self, kl_grade):
        """Generate synthetic knee X-ray image."""
        img = np.zeros((256, 256))
        
        # Add anatomical structure
        y, x = np.ogrid[:256, :256]
        
        # Femur (upper part)
        femur_mask = (x - 128)**2 + (y - 80)**2 <= 50**2
        img[femur_mask] = 0.7
        
        # Tibia (lower part)
        tibia_mask = (x - 128)**2 + (y - 180)**2 <= 40**2
        img[tibia_mask] = 0.65
        
        # Knee joint space
        joint_mask = (np.abs(y - 128) < 20) & (np.abs(x - 128) < 40)
        img[joint_mask] = 0.4
        
        # Add severity based on KL grade
        # Higher grades show narrowing and osteophytes
        if kl_grade >= 1:
            # Osteophyte-like formations
            osteophyte = (x - 100)**2 + (y - 128)**2 <= (15 + 5*kl_grade)**2
            img[osteophyte] += 0.15 * kl_grade
        
        if kl_grade >= 2:
            # Joint space narrowing
            joint_mask = (np.abs(y - 128) < 15 - 3*kl_grade) & (np.abs(x - 128) < 35)
            img[joint_mask] = 0.25 + 0.1 * kl_grade
        
        # Add noise
        noise = np.random.normal(0, 0.03, img.shape)
        img = np.clip(img + noise, 0, 1)
        
        return img.astype(np.float32)
    
    def _generate_synthetic_mask(self, kl_grade):
        """Generate synthetic segmentation mask for ROI."""
        mask = np.zeros((256, 256))
        
        # Segment knee region (both femur and tibia with joint space)
        y, x = np.ogrid[:256, :256]
        
        # Femur region
        femur_mask = (x - 128)**2 + (y - 80)**2 <= 55**2
        mask[femur_mask] = 1.0
        
        # Tibia region
        tibia_mask = (x - 128)**2 + (y - 180)**2 <= 45**2
        mask[tibia_mask] = 1.0
        
        # Joint space
        joint_mask = (np.abs(y - 128) < 25) & (np.abs(x - 128) < 50)
        mask[joint_mask] = 1.0
        
        return mask.astype(np.float32)
    
    def train_segmentation(self, X_seg, y_masks, epochs=10, batch_size=16):
        """
        Train U-Net for ROI segmentation.
        y_masks: ground truth segmentation masks
        """
        dataset = XRayDataset(X_seg, y_masks, mode='segmentation')
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        print("  Training U-Net segmentation model...")
        self.unet.train()
        
        for epoch in range(epochs):
            total_loss = 0
            
            for batch_img, batch_mask in dataloader:
                batch_img = batch_img.to(self.device)
                batch_mask = batch_mask.unsqueeze(1).to(self.device)
                
                self.unet_optimizer.zero_grad()
                pred_mask = self.unet(batch_img)
                loss = self.segmentation_loss(pred_mask, batch_mask)
                loss.backward()
                self.unet_optimizer.step()
                
                total_loss += loss.item()
            
            if (epoch + 1) % 5 == 0 or epoch == 0:
                print(f"    Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(dataloader):.4f}")
    
    def train_classification(self, X_clf, y_clf, epochs=15, batch_size=16):
        """
        Train EfficientNet for KL grade classification.
        """
        X_train, X_test, y_train, y_test = train_test_split(
            X_clf, y_clf, test_size=0.2, random_state=42, stratify=y_clf
        )
        
        train_dataset = XRayDataset(X_train, y_train, mode='classification')
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        
        test_dataset = XRayDataset(X_test, y_test, mode='classification')
        test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
        
        print("  Training EfficientNet KL classification model...")
        best_acc = 0
        
        for epoch in range(epochs):
            self.efficientnet.train()
            total_loss = 0
            
            for batch_img, batch_label in train_loader:
                batch_img = batch_img.to(self.device)
                batch_label = batch_label.to(self.device)
                
                self.efficientnet_optimizer.zero_grad()
                logits = self.efficientnet(batch_img)
                loss = self.classification_loss(logits, batch_label)
                loss.backward()
                self.efficientnet_optimizer.step()
                
                total_loss += loss.item()
            
            # Evaluate on test set
            self.efficientnet.eval()
            all_preds = []
            all_labels = []
            
            with torch.no_grad():
                for batch_img, batch_label in test_loader:
                    batch_img = batch_img.to(self.device)
                    logits = self.efficientnet(batch_img)
                    preds = logits.argmax(dim=1)
                    all_preds.extend(preds.cpu().numpy())
                    all_labels.extend(batch_label.numpy())
            
            acc = accuracy_score(all_labels, all_preds)
            
            if (epoch + 1) % 5 == 0 or epoch == 0:
                print(f"    Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(train_loader):.4f}, Acc: {acc:.4f}")
            
            best_acc = max(best_acc, acc)
        
        self.performance_metrics['classification_accuracy'] = best_acc
        self.performance_metrics['test_samples'] = len(X_test)
        self.performance_metrics['train_samples'] = len(X_train)
        
        # Final evaluation
        self.efficientnet.eval()
        with torch.no_grad():
            all_preds = []
            all_labels = []
            for batch_img, batch_label in test_loader:
                batch_img = batch_img.to(self.device)
                logits = self.efficientnet(batch_img)
                preds = logits.argmax(dim=1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(batch_label.numpy())
        
        self.performance_metrics['final_accuracy'] = accuracy_score(all_labels, all_preds)
        self.performance_metrics['kl_grades'] = 5
    
    def predict_kl_grade(self, xray_image):
        """
        Predict Kellgren-Lawrence grade for an X-ray image.
        
        Args:
            xray_image: (256, 256) numpy array
        
        Returns:
            dict with KL grade and probabilities
        """
        self.efficientnet.eval()
        
        # Preprocess
        img_tensor = torch.FloatTensor(xray_image).unsqueeze(0).unsqueeze(0)
        img_tensor = img_tensor.to(self.device)
        
        with torch.no_grad():
            logits = self.efficientnet(img_tensor)
            probs = torch.softmax(logits, dim=1)
            kl_pred = logits.argmax(dim=1).item()
            kl_probs = probs[0].cpu().numpy()
        
        kl_grades = {0: 'Normal', 1: 'Doubtful', 2: 'Minimal', 3: 'Moderate', 4: 'Severe'}
        
        return {
            'kl_grade': kl_pred,
            'kl_description': kl_grades[kl_pred],
            'confidence': float(kl_probs[kl_pred]),
            'probabilities': {
                f'Grade_{i}_({kl_grades[i]})': float(p) for i, p in enumerate(kl_probs)
            }
        }
    
    def segment_xray(self, xray_image):
        """
        Segment X-ray ROI using U-Net.
        
        Args:
            xray_image: (256, 256) numpy array
        
        Returns:
            segmentation mask
        """
        self.unet.eval()
        
        img_tensor = torch.FloatTensor(xray_image).unsqueeze(0).unsqueeze(0)
        img_tensor = img_tensor.to(self.device)
        
        with torch.no_grad():
            mask = self.unet(img_tensor)
            mask = (mask > 0.5).squeeze().cpu().numpy().astype(np.float32)
        
        return mask


def demo_stream3():
    """Demonstrate Evidence Stream 3."""
    print("\n" + "="*70)
    print("EVIDENCE STREAM 3: X-ray Analysis (U-Net + EfficientNet)")
    print("="*70)
    
    # Initialize pipeline
    print("\n[1] Initializing X-ray analysis pipeline...")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    pipeline = XRayAnalysisPipeline(device=device)
    print(f"  - Device: {device}")
    print(f"  - U-Net: Initialized")
    print(f"  - EfficientNet: Initialized (KL grades: 0-4)")
    
    # Generate synthetic data
    print("\n[2] Generating synthetic X-ray dataset...")
    X, y, masks = pipeline.generate_synthetic_xray_data(n_samples=300)
    print(f"  - X-ray images: {X.shape}")
    print(f"  - KL grade distribution: {np.bincount(y)}")
    print(f"  - Segmentation masks: {masks.shape}")
    
    # Train segmentation
    print("\n[3] Training U-Net for ROI segmentation...")
    pipeline.train_segmentation(X, masks, epochs=10, batch_size=32)
    print("  ✓ U-Net training complete")
    
    # Train classification
    print("\n[4] Training EfficientNet for KL grade classification...")
    pipeline.train_classification(X, y, epochs=15, batch_size=32)
    print(f"  - Final accuracy: {pipeline.performance_metrics['final_accuracy']:.4f}")
    print(f"  - Training samples: {pipeline.performance_metrics['train_samples']}")
    print(f"  - Test samples: {pipeline.performance_metrics['test_samples']}")
    
    # Test prediction
    print("\n[5] Testing KL grade prediction on sample X-ray...")
    test_xray = pipeline.generate_synthetic_xray_data(n_samples=1)[0][0]
    prediction = pipeline.predict_kl_grade(test_xray)
    
    print(f"  - Predicted KL Grade: {prediction['kl_grade']} ({prediction['kl_description']})")
    print(f"  - Confidence: {prediction['confidence']:.4f}")
    print(f"  - All probabilities:")
    for grade, prob in prediction['probabilities'].items():
        print(f"      • {grade}: {prob:.4f}")
    
    # Test segmentation
    print("\n[6] Testing ROI segmentation...")
    segmentation_mask = pipeline.segment_xray(test_xray)
    print(f"  - Mask shape: {segmentation_mask.shape}")
    print(f"  - Segmented pixels: {(segmentation_mask > 0).sum()}")
    
    print("\n✓ Evidence Stream 3 demonstration complete")
    
    return pipeline


if __name__ == '__main__':
    demo_stream3()
