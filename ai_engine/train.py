"""Reproducible PyTorch training and evaluation script for crop lifecycle classification.
Backbone: MobileNetV3-Small (fine-tuned on agricultural crop stages)
Dataset: ai_engine/data/crop_stages (SOWING, CROP_GROWTH, HARVEST, STORAGE)
Output: ai_engine/weights/crop_mobilenet_v3.pth
"""

import os
import json
import hashlib
import time
from typing import Dict, Any, List, Tuple
from PIL import Image

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support, accuracy_score


# Seed for strict reproducibility
RANDOM_SEED = 42
torch.manual_seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


class CropDataset(Dataset):
    """PyTorch Dataset loading image paths with transforms."""

    def __init__(self, image_paths: List[str], labels: List[int], transform=None):
        self.image_paths = image_paths
        self.labels = labels
        self.transform = transform

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        path = self.image_paths[idx]
        label = self.labels[idx]
        with Image.open(path) as img:
            img = img.convert("RGB")
            if self.transform:
                img = self.transform(img)
        return img, label


def load_dataset_splits(data_dir: str = "ai_engine/data/crop_stages") -> Tuple[Any, Any, Any, List[str], Dict[str, int]]:
    """Loads images, applies stratified splits (70/15/15), and returns Datasets."""
    classes = sorted([d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))])
    class_to_idx = {cls_name: i for i, cls_name in enumerate(classes)}

    all_paths = []
    all_labels = []

    for cls_name in classes:
        cls_dir = os.path.join(data_dir, cls_name)
        for fname in os.listdir(cls_dir):
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                all_paths.append(os.path.join(cls_dir, fname))
                all_labels.append(class_to_idx[cls_name])

    # 70% train, 30% val+test
    train_paths, val_test_paths, train_labels, val_test_labels = train_test_split(
        all_paths, all_labels, test_size=0.30, stratify=all_labels, random_state=RANDOM_SEED
    )

    # 15% val, 15% test
    val_paths, test_paths, val_labels, test_labels = train_test_split(
        val_test_paths, val_test_labels, test_size=0.50, stratify=val_test_labels, random_state=RANDOM_SEED
    )

    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=10),
        transforms.ColorJitter(brightness=0.15, contrast=0.15),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    val_test_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    train_ds = CropDataset(train_paths, train_labels, transform=train_transform)
    val_ds = CropDataset(val_paths, val_labels, transform=val_test_transform)
    test_ds = CropDataset(test_paths, test_labels, transform=val_test_transform)

    return train_ds, val_ds, test_ds, classes, class_to_idx


def build_model(num_classes: int = 4) -> nn.Module:
    """Builds MobileNetV3-Small model loading cached ImageNet backbone."""
    model = models.mobilenet_v3_small(weights=None)

    # Check local cache first
    cached_path = os.path.expanduser("~/.cache/torch/hub/checkpoints/mobilenet_v3_small-047dcff4.pth")
    if os.path.exists(cached_path):
        state_dict = torch.load(cached_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state_dict)
        print(f"Loaded pretrained backbone weights from {cached_path}")
    else:
        print("Cached backbone weights not found; initializing without pretrained weights.")

    # Replace classifier head for agricultural classes
    in_features = model.classifier[3].in_features
    model.classifier[3] = nn.Linear(in_features, num_classes)
    return model


def train_model(
    epochs: int = 6,
    batch_size: int = 16,
    lr: float = 5e-4,
    output_dir: str = "ai_engine/weights",
) -> Dict[str, Any]:
    """Executes genuine training, validation tracking, test evaluation, and saves model weights."""
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs("ai_engine/models", exist_ok=True)

    print("--- 1. Loading Agricultural Dataset ---")
    train_ds, val_ds, test_ds, classes, class_to_idx = load_dataset_splits()
    print(f"Classes: {classes}")
    print(f"Train samples: {len(train_ds)}, Val samples: {len(val_ds)}, Test samples: {len(test_ds)}")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    print("\n--- 2. Building MobileNetV3-Small Model ---")
    model = build_model(num_classes=len(classes))
    device = torch.device("cpu")
    model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

    best_val_loss = float("inf")
    best_weights = None
    history = []

    print(f"\n--- 3. Starting Training Loop ({epochs} epochs) ---")
    start_time = time.time()

    for epoch in range(1, epochs + 1):
        # Training phase
        model.train()
        train_loss = 0.0
        train_correct = 0
        total_train = 0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * images.size(0)
            preds = torch.argmax(outputs, dim=1)
            train_correct += (preds == labels).sum().item()
            total_train += images.size(0)

        epoch_train_loss = train_loss / total_train
        epoch_train_acc = train_correct / total_train

        # Validation phase
        model.eval()
        val_loss = 0.0
        val_correct = 0
        total_val = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)

                val_loss += loss.item() * images.size(0)
                preds = torch.argmax(outputs, dim=1)
                val_correct += (preds == labels).sum().item()
                total_val += images.size(0)

        epoch_val_loss = val_loss / total_val
        epoch_val_acc = val_correct / total_val

        history.append({
            "epoch": epoch,
            "train_loss": round(epoch_train_loss, 4),
            "train_acc": round(epoch_train_acc, 4),
            "val_loss": round(epoch_val_loss, 4),
            "val_acc": round(epoch_val_acc, 4),
        })

        print(
            f"Epoch {epoch:2d}/{epochs:2d} | "
            f"Train Loss: {epoch_train_loss:.4f} - Train Acc: {epoch_train_acc:.4f} | "
            f"Val Loss: {epoch_val_loss:.4f} - Val Acc: {epoch_val_acc:.4f}"
        )

        if epoch_val_loss < best_val_loss:
            best_val_loss = epoch_val_loss
            best_weights = model.state_dict().copy()

    elapsed = time.time() - start_time
    print(f"Training completed in {elapsed:.2f} seconds.")

    # Load best weights for test evaluation
    model.load_state_dict(best_weights)
    model.eval()

    print("\n--- 4. Evaluating on Held-Out Test Set ---")
    all_preds = []
    all_targets = []

    with torch.no_grad():
        for images, labels in test_loader:
            images = images.to(device)
            outputs = model(images)
            preds = torch.argmax(outputs, dim=1)
            all_preds.extend(preds.cpu().numpy().tolist())
            all_targets.extend(labels.numpy().tolist())

    acc = accuracy_score(all_targets, all_preds)
    precision, recall, f1, support = precision_recall_fscore_support(
        all_targets, all_preds, average=None, labels=list(range(len(classes)))
    )
    macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
        all_targets, all_preds, average="macro"
    )
    cm = confusion_matrix(all_targets, all_preds).tolist()

    print(f"Test Accuracy: {acc:.4f}")
    print(f"Macro Precision: {macro_precision:.4f}, Macro Recall: {macro_recall:.4f}, Macro F1: {macro_f1:.4f}")
    print("\nConfusion Matrix:")
    print(np.array(cm))

    per_class_metrics = {}
    for i, cls_name in enumerate(classes):
        per_class_metrics[cls_name] = {
            "precision": round(float(precision[i]), 4),
            "recall": round(float(recall[i]), 4),
            "f1_score": round(float(f1[i]), 4),
            "support": int(support[i]),
        }
        print(f"  {cls_name:12s}: P={precision[i]:.4f}, R={recall[i]:.4f}, F1={f1[i]:.4f} (n={support[i]})")

    # Save model checkpoint
    weights_path = os.path.join(output_dir, "crop_mobilenet_v3.pth")
    checkpoint = {
        "model_state_dict": best_weights,
        "classes": classes,
        "class_to_idx": class_to_idx,
        "architecture": "mobilenet_v3_small",
        "num_classes": len(classes),
        "input_shape": [3, 224, 224],
        "normalization": {
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
        },
        "best_val_loss": round(best_val_loss, 4),
        "test_accuracy": round(float(acc), 4),
        "macro_f1": round(float(macro_f1), 4),
    }

    torch.save(checkpoint, weights_path)
    # Also save a mirror copy in ai_engine/models/
    torch.save(checkpoint, "ai_engine/models/crop_mobilenet_v3.pth")

    # Compute SHA-256
    with open(weights_path, "rb") as f:
        weights_sha256 = hashlib.sha256(f.read()).hexdigest()

    file_size_bytes = os.path.getsize(weights_path)
    print(f"\n--- 5. Saved Checkpoint ---")
    print(f"Path: {weights_path}")
    print(f"Size: {file_size_bytes} bytes ({file_size_bytes / (1024*1024):.2f} MB)")
    print(f"SHA-256: {weights_sha256}")

    training_report = {
        "model_name": "crop_mobilenet_v3",
        "architecture": "MobileNetV3-Small",
        "framework": "PyTorch 2.10.0+cpu",
        "weights_path": weights_path,
        "weights_sha256": weights_sha256,
        "weights_size_bytes": file_size_bytes,
        "classes": classes,
        "dataset_split": {
            "train_samples": len(train_ds),
            "val_samples": len(val_ds),
            "test_samples": len(test_ds),
            "total_samples": len(train_ds) + len(val_ds) + len(test_ds),
        },
        "training_config": {
            "epochs": epochs,
            "batch_size": batch_size,
            "optimizer": "AdamW",
            "learning_rate": lr,
            "random_seed": RANDOM_SEED,
            "training_time_seconds": round(elapsed, 2),
        },
        "history": history,
        "evaluation_metrics": {
            "accuracy": round(float(acc), 4),
            "macro_precision": round(float(macro_precision), 4),
            "macro_recall": round(float(macro_recall), 4),
            "macro_f1": round(float(macro_f1), 4),
            "per_class": per_class_metrics,
            "confusion_matrix": cm,
        },
    }

    report_path = os.path.join(output_dir, "training_metrics.json")
    with open(report_path, "w") as f:
        json.dump(training_report, f, indent=2)

    return training_report


if __name__ == "__main__":
    train_model()
