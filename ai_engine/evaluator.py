from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ai_engine.quality import (
    compute_laplacian_variance,
    compute_luminance_clipping,
    validate_image_dimensions,
    inspect_exif,
)
from ai_engine.hashing import (
    compute_sha256,
    compute_phash_64,
    hamming_distance_hex,
)
from ai_engine.classifier import CropCategoryClassifier
from ai_engine.registry import ModelRegistry
from ai_engine.forensics import ImageForensicsAnalyzer
from ai_engine.unvalidated import ManipulationDetectorGovernance


class AIEvaluator:
    """Unified local AI intelligence engine enforcing the Never-Autonomous-Reject rule.
    Integrates genuine deterministic quality CV, exact/perceptual dedup, local PyTorch
    crop classification, and Error Level Analysis (ELA) / noise forensics.
    """

    def __init__(self):
        self.classifier = CropCategoryClassifier()
        self.registry = ModelRegistry()
        self.forensics = ImageForensicsAnalyzer()
        self.tamper_governance = ManipulationDetectorGovernance()

    def evaluate_evidence(
        self,
        evidence_id: str,
        image_bytes: bytes,
        envelope: Dict[str, Any],
        known_hashes: Optional[List[str]] = None,
        known_phashes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Performs full AI assessment of evidence bytes against envelope metadata."""
        meta = envelope.get("metadata", {})
        capture_ts = meta.get("capture_timestamp") or datetime.now(timezone.utc).isoformat()
        lifecycle_stage = envelope.get("lifecycle_stage", "CROP_GROWTH")

        # 1. Image Quality Assessment
        blur_score = compute_laplacian_variance(image_bytes)
        is_blurry = blur_score < 80.0

        under_pct, over_pct = compute_luminance_clipping(image_bytes)
        is_exposure_valid = (under_pct < 35.0) and (over_pct < 35.0)

        dim_res = validate_image_dimensions(image_bytes)
        exif_res = inspect_exif(image_bytes, capture_ts)

        # 2. Duplicate Detection
        current_sha256 = compute_sha256(image_bytes)
        known_h = known_hashes or []
        exact_match = current_sha256.lower() in [h.lower() for h in known_h]

        current_phash = compute_phash_64(image_bytes)
        min_dist = 64
        for prev_p in (known_phashes or []):
            dist = hamming_distance_hex(current_phash, prev_p)
            if dist < min_dist:
                min_dist = dist

        is_near_dup = min_dist <= 10
        is_duplicate = exact_match or is_near_dup

        # 3. Category Consistency (genuine local PyTorch MobileNetV3 inference)
        cat_res = self.classifier.predict(image_bytes, declared_stage=lifecycle_stage)

        # 4. Forensic Tamper Detection (genuine ELA & noise residual analysis)
        forensics_res = self.forensics.evaluate_tamper(image_bytes)

        # 5. Core Invariant: Never Autonomous Reject
        # Any anomaly flags for human reviewer; otherwise approved for batching. Never REJECT.
        anomalies = [
            is_blurry,
            not is_exposure_valid,
            not dim_res["is_valid"],
            not exif_res["is_consistent"],
            is_duplicate,
            not cat_res["is_consistent"],
            forensics_res["is_tamper_suspected"],
        ]
        has_anomaly = any(anomalies)

        recommended_action = "FLAG_FOR_REVIEW" if has_anomaly else "APPROVE"
        review_recommended = has_anomaly
        state_transition = "PENDING_REVIEW" if has_anomaly else "PENDING_BATCH"

        return {
            "evidence_id": evidence_id,
            "quality": {
                "blur_score": round(blur_score, 2),
                "is_blurry": is_blurry,
                "exposure_under_pct": round(under_pct, 2),
                "exposure_over_pct": round(over_pct, 2),
                "is_exposure_valid": is_exposure_valid,
                "width": dim_res["width"],
                "height": dim_res["height"],
                "is_resolution_valid": dim_res["is_valid"],
                "exif_consistent": exif_res["is_consistent"],
            },
            "duplicate": {
                "exact_sha256_match": exact_match,
                "phash": current_phash,
                "nearest_phash_distance": min_dist,
                "is_duplicate": is_duplicate,
            },
            "category": {
                "declared_stage": cat_res["declared_stage"],
                "predicted_class": cat_res["predicted_class"],
                "confidence": cat_res["confidence"],
                "is_consistent": cat_res["is_consistent"],
            },
            "forensics": {
                "ela_variance": forensics_res["ela_variance"],
                "noise_variance": forensics_res["noise_variance"],
                "is_tamper_suspected": forensics_res["is_tamper_suspected"],
            },
            "governance": {
                "model_tiers_used": ["deterministic", "pretrained", "custom", "forensic"],
                "manipulation_detector_status": forensics_res["validation_status"],
                "review_recommended": review_recommended,
                "recommended_action": recommended_action,
                "state_transition": state_transition,
                "advisory_note": "Evaluated locally on CPU without external API inference.",
            },
            "recommendation": "AUTO_APPROVE" if not has_anomaly else "PENDING_REVIEW",
        }


ai_evaluator = AIEvaluator()
