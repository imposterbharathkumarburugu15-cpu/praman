import io
import os
import logging
from typing import Dict, Any, List, Optional, Union
from PIL import Image
import numpy as np
import torch
import torch.nn as nn
from torchvision import transforms, models

logger = logging.getLogger("praman.ai_engine.classifier")


class CropCategoryClassifier:
    """Classifies agricultural phenological lifecycle stages and cross-checks stage consistency
    using a locally executed PyTorch MobileNetV3-Small neural network.

    IMPORTANT ARCHITECTURAL DISTINCTION:
    This model classifies **Crop Lifecycle Stages** (CROP_GROWTH, HARVEST, SOWING, STORAGE),
    NOT **Crop Species** (e.g., Cotton, Paddy/Rice, Maize, Wheat, Chili, Groundnut).
    In PRAMAN, crop species is a farmer/parcel declaration verified by agricultural field rules
    and administrative records, whereas this computer vision model verifies visual phenological
    stage consistency (e.g., verifying that a photo declared as 'HARVEST' does not display bare
    furrows or early sowing).
    """

    KNOWN_CLASSES: Dict[str, List[str]] = {
        "SOWING": ["plowed_field", "soil_seeds", "furrows", "SOWING", "sowing"],
        "INPUT_APPLICATION": ["fertilizer_sprayer", "irrigation_pipe", "treated_soil", "INPUT_APPLICATION", "input_application"],
        "CROP_GROWTH": ["cotton_canopy", "maize_field", "green_foliage", "CROP_GROWTH", "crop_growth"],
        "HARVEST": ["cotton_bolls", "ripe_paddy", "combine_harvester", "HARVEST", "harvest"],
        "STORAGE": ["grain_bags", "warehouse_silo", "storage_tarp", "STORAGE", "storage"],
    }

    STAGE_TO_REPRESENTATIVE_CLASS: Dict[str, str] = {
        "SOWING": "plowed_field",
        "INPUT_APPLICATION": "treated_soil",
        "CROP_GROWTH": "green_foliage",
        "HARVEST": "ripe_paddy",
        "STORAGE": "grain_bags",
    }

    DEFAULT_CLASSES = ["CROP_GROWTH", "HARVEST", "SOWING", "STORAGE"]

    def __init__(self, weights_path: Optional[str] = None):
        self.weights_path = weights_path or os.path.join(
            os.path.dirname(__file__), "weights", "crop_mobilenet_v3.pth"
        )
        self.device = torch.device("cpu")
        self.classes = list(self.DEFAULT_CLASSES)
        self.model = None
        self.status = "INITIALIZING"
        self.error_message: Optional[str] = None
        self._load_model()

        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def _load_model(self):
        """Initializes MobileNetV3-Small architecture and loads weights if present.
        If weights are missing or corrupt, marks status as MODEL_UNAVAILABLE.
        Never leaves uninitialized Gaussian weights active for prediction.
        """
        if not os.path.exists(self.weights_path):
            self.model = None
            self.status = "MODEL_UNAVAILABLE"
            self.error_message = f"Model weights file does not exist at {self.weights_path}"
            logger.warning(self.error_message)
            return

        try:
            model = models.mobilenet_v3_small(weights=None)
            in_features = model.classifier[3].in_features
            model.classifier[3] = nn.Linear(in_features, len(self.classes))

            checkpoint = torch.load(self.weights_path, map_location=self.device, weights_only=False)
            if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                model.load_state_dict(checkpoint["model_state_dict"])
                if "classes" in checkpoint:
                    self.classes = checkpoint["classes"]
            elif isinstance(checkpoint, dict):
                model.load_state_dict(checkpoint)
            else:
                raise ValueError(f"Unrecognized checkpoint format: {type(checkpoint)}")

            model.to(self.device)
            model.eval()
            self.model = model
            self.status = "READY"
            self.error_message = None
            logger.info(f"Loaded MobileNetV3-Small crop stage classifier from {self.weights_path}")
        except Exception as e:
            # Model loading failed - mark as MODEL_UNAVAILABLE; DO NOT leave random Gaussian weights!
            self.model = None
            self.status = "MODEL_UNAVAILABLE"
            self.error_message = f"Failed to load model weights: {e}"
            logger.error(self.error_message)

    def evaluate(self, declared_stage: str, predicted_class: Optional[str], confidence: Optional[float]) -> Dict[str, Any]:
        """Evaluates stage consistency against predicted visual class and confidence score.
        If model is unavailable or prediction is missing, returns MODEL_UNAVAILABLE.
        """
        if self.status != "READY" or self.model is None or predicted_class is None or confidence is None:
            return {
                "status": "MODEL_UNAVAILABLE",
                "declared_stage": declared_stage,
                "predicted_class": None,
                "confidence": None,
                "is_consistent": None,
            }

        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"Confidence score {confidence} must be in [0.0, 1.0]")

        valid_stage_classes = self.KNOWN_CLASSES.get(declared_stage, [])
        is_consistent = (
            predicted_class in valid_stage_classes
            or predicted_class.upper() == declared_stage.upper()
        )

        return {
            "status": "SUCCESS",
            "declared_stage": declared_stage,
            "predicted_class": predicted_class,
            "confidence": round(confidence, 3),
            "is_consistent": is_consistent,
        }

    def evaluate_consistency(
        self,
        declared_stage: str,
        predicted_class: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Evaluates lifecycle stage consistency adhering to platform error-gating contract.
        If model is unavailable, returns MODEL_UNAVAILABLE status without fabricating scores.
        """
        return self.evaluate(declared_stage=declared_stage, predicted_class=predicted_class, confidence=confidence)

    def predict(
        self,
        image_input: Union[bytes, Image.Image, np.ndarray],
        declared_stage: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executes genuine local PyTorch forward-pass inference on the input image.
        Returns predicted class, predicted stage, genuine confidence, and stage consistency.

        Error Gating:
        - If weights are missing or failed to load, returns status='MODEL_UNAVAILABLE'.
          Does NOT substitute uninitialized random Gaussian weights.
        - If image bytes are corrupted or decode fails, returns status='ANALYSIS_FAILED'.
        """
        if self.status != "READY" or self.model is None:
            return {
                "status": "MODEL_UNAVAILABLE",
                "declared_stage": declared_stage,
                "predicted_class": None,
                "predicted_stage": None,
                "confidence": None,
                "probabilities": {},
                "is_consistent": None,
                "error": self.error_message or "Model weights unavailable",
            }

        # 1. Convert input to PIL RGB Image
        try:
            if isinstance(image_input, bytes):
                if len(image_input) == 0:
                    raise ValueError("Empty image bytes provided")
                image = Image.open(io.BytesIO(image_input))
                image.load()
                image = image.convert("RGB")
            elif isinstance(image_input, np.ndarray):
                if image_input.size == 0:
                    raise ValueError("Empty numpy array provided")
                if image_input.ndim == 2:
                    image = Image.fromarray(image_input).convert("RGB")
                else:
                    image = Image.fromarray(image_input).convert("RGB")
            elif isinstance(image_input, Image.Image):
                image = image_input.convert("RGB")
            else:
                raise TypeError(f"Unsupported image input type: {type(image_input)}")
        except Exception as e:
            logger.warning(f"Failed to decode image input for classification: {e}")
            return {
                "status": "ANALYSIS_FAILED",
                "declared_stage": declared_stage,
                "predicted_class": None,
                "predicted_stage": None,
                "confidence": None,
                "probabilities": {},
                "is_consistent": None,
                "error": f"Failed to decode or process image: {e}",
            }

        # 2. Preprocess & Forward pass
        try:
            tensor = self.transform(image).unsqueeze(0).to(self.device)
            with torch.no_grad():
                logits = self.model(tensor)
                probs = torch.softmax(logits, dim=1)[0]
                top_idx = torch.argmax(probs).item()
                predicted_stage = self.classes[top_idx]
                confidence = float(probs[top_idx].item())
        except Exception as e:
            logger.error(f"Forward-pass inference failed: {e}")
            return {
                "status": "ANALYSIS_FAILED",
                "declared_stage": declared_stage,
                "predicted_class": None,
                "predicted_stage": None,
                "confidence": None,
                "probabilities": {},
                "is_consistent": None,
                "error": f"Inference execution failed: {e}",
            }

        # 3. Map to representative visual class
        predicted_class = self.STAGE_TO_REPRESENTATIVE_CLASS.get(
            predicted_stage, predicted_stage.lower()
        )

        # 4. Consistency check with declared stage
        if declared_stage:
            valid_classes = self.KNOWN_CLASSES.get(declared_stage, [])
            direct_match = (
                (predicted_class in valid_classes)
                or (predicted_stage.upper() == declared_stage.upper())
                or (
                    declared_stage.upper() == "INPUT_APPLICATION"
                    and predicted_stage in ("SOWING", "CROP_GROWTH")
                )
            )
            # Fallback: if model is uncertain (confidence < 0.60), do not hard-flag mismatch
            is_consistent = direct_match or (confidence < 0.60)
        else:
            is_consistent = True

        return {
            "status": "SUCCESS",
            "declared_stage": declared_stage or predicted_stage,
            "predicted_class": predicted_class,
            "predicted_stage": predicted_stage,
            "confidence": round(confidence, 3),
            "probabilities": {
                cls_name: round(float(probs[i].item()), 4)
                for i, cls_name in enumerate(self.classes)
            },
            "is_consistent": is_consistent,
        }
