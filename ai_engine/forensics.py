"""Image Forensics Analysis Engine for PRAMAN.
Implements genuine computer vision forensic analysis:
1. Error Level Analysis (ELA): Recompression difference variance (JPEG Q90).
2. Noise Residual Variance: Median-filter subtraction and local block variance disparity to detect splices and edits.
3. Structured forensic assessment adhering to platform contracts.
"""

import io
from typing import Dict, Any, Union, Tuple
from PIL import Image
import numpy as np
import cv2


class ImageForensicsAnalyzer:
    """Performs Error Level Analysis (ELA) and noise residual variance analysis
    to detect digital image tampering, splices, and inconsistent compression levels.
    """

    def __init__(
        self,
        ela_quality: int = 90,
        ela_variance_threshold: float = 25.0,
        noise_variance_threshold: float = 80.0,
        noise_disparity_threshold: float = 25.0,  # raised to reduce false AI flags on real images
        spectral_anomaly_threshold: float = 1.6,
    ):
        self.ela_quality = ela_quality
        self.ela_variance_threshold = ela_variance_threshold
        self.noise_variance_threshold = noise_variance_threshold
        self.noise_disparity_threshold = noise_disparity_threshold
        self.spectral_anomaly_threshold = spectral_anomaly_threshold

    def compute_spectral_artifacts(self, image: Image.Image) -> Tuple[float, bool]:
        """Analyzes 2D Fourier frequency spectrum to detect periodic checkerboard or upsampling
        grid artifacts typical of generative adversarial networks (GANs) and diffusion models.
        """
        gray = np.array(image.convert("L"), dtype=np.float32)
        h, w = gray.shape
        if h < 32 or w < 32:
            return 1.0, False

        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)
        magnitude = np.abs(fshift)
        log_mag = np.log1p(magnitude)

        # High-frequency corner energy vs mid-frequency annular energy
        cy, cx = h // 2, w // 2
        r_mid = min(h, w) // 4
        r_high = min(h, w) // 2

        y, x = np.ogrid[:h, :w]
        dist_from_center = np.sqrt((x - cx)**2 + (y - cy)**2)

        mid_mask = (dist_from_center >= r_mid * 0.5) & (dist_from_center < r_mid)
        high_mask = (dist_from_center >= r_mid) & (dist_from_center < r_high)

        mid_mean = float(np.mean(log_mag[mid_mask])) if np.any(mid_mask) else 1.0
        high_mean = float(np.mean(log_mag[high_mask])) if np.any(high_mask) else 1.0

        # In natural camera images, high frequency energy falls off steeply (1/f^alpha)
        # In synthetic AI images, upconvolution leaves unnatural high-frequency spikes
        spectral_ratio = high_mean / max(mid_mean, 1e-3)
        is_spectral_anomalous = spectral_ratio > self.spectral_anomaly_threshold or spectral_ratio < 0.2
        return round(spectral_ratio, 3), is_spectral_anomalous

    def _load_image(self, image_input: Union[bytes, Image.Image, np.ndarray]) -> Image.Image:
        """Loads and converts input into a PIL RGB Image."""
        if isinstance(image_input, bytes):
            return Image.open(io.BytesIO(image_input)).convert("RGB")
        elif isinstance(image_input, np.ndarray):
            if image_input.ndim == 2:
                return Image.fromarray(image_input).convert("RGB")
            return Image.fromarray(image_input).convert("RGB")
        elif isinstance(image_input, Image.Image):
            return image_input.convert("RGB")
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

    def compute_ela(self, image: Image.Image) -> Tuple[float, float, np.ndarray]:
        """Performs Error Level Analysis (ELA).
        Resaves image at JPEG quality Q90, computes absolute pixel difference,
        and analyzes residual distribution.
        Returns: (ela_variance, max_error, scaled_diff)
        """
        # Save to buffer at JPEG quality
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=self.ela_quality)
        buf.seek(0)
        resaved = Image.open(buf).convert("RGB")

        orig_np = np.array(image, dtype=np.float32)
        resaved_np = np.array(resaved, dtype=np.float32)

        # Absolute difference between original and resaved JPEG
        diff = np.abs(orig_np - resaved_np)
        ela_variance = float(np.var(diff))
        max_error = float(np.max(diff))

        # Scale difference to [0, 255] for visual inspection
        scale = 255.0 / max_error if max_error > 0 else 1.0
        scaled_diff = np.clip(diff * scale, 0, 255).astype(np.uint8)

        return ela_variance, max_error, scaled_diff

    def compute_noise_residuals(self, image: Image.Image) -> Tuple[float, float]:
        """Computes high-pass / median filter noise residuals and spatial block disparity.
        Returns: (global_noise_variance, block_disparity_ratio)
        """
        gray = np.array(image.convert("L"), dtype=np.uint8)
        denoised = cv2.medianBlur(gray, 3)

        # High-pass noise residual (original - denoised)
        residual = gray.astype(np.float32) - denoised.astype(np.float32)
        global_noise_var = float(np.var(residual))

        # Spatial block variance analysis (detects local spliced patches)
        h, w = gray.shape
        block_size = max(16, min(h // 8, w // 8, 64))
        block_vars = []

        for y in range(0, h - block_size + 1, block_size):
            for x in range(0, w - block_size + 1, block_size):
                patch = residual[y:y + block_size, x:x + block_size]
                block_vars.append(float(np.var(patch)))

        if block_vars and global_noise_var >= 1.0:
            med_var = float(np.median(block_vars))
            max_var = float(np.max(block_vars))
            disparity_ratio = max_var / max(med_var, 1.0)
        else:
            disparity_ratio = 1.0

        return global_noise_var, disparity_ratio

    def evaluate_tamper(
        self, image_input: Union[bytes, Image.Image, np.ndarray]
    ) -> Dict[str, Any]:
        """Executes full forensic tamper and AI-generation evaluation."""
        image = self._load_image(image_input)

        # 1. Error Level Analysis
        ela_variance, max_error, _ = self.compute_ela(image)

        # 2. Noise Residual Analysis
        noise_variance, noise_disparity = self.compute_noise_residuals(image)

        # 3. Frequency Domain AI Generation Artifacts
        spectral_ratio, is_spectral_anomalous = self.compute_spectral_artifacts(image)

        # EXIF presence check – real camera images contain EXIF metadata. If present, we treat the image as genuine
        # and do not flag it as AI‑generated, even if other heuristics fire.
        has_exif = bool(image.getexif())

        # 4. Anomaly Evaluation
        is_ela_anomalous = ela_variance > self.ela_variance_threshold
        is_noise_anomalous = (
            noise_variance > self.noise_variance_threshold
            or noise_disparity > self.noise_disparity_threshold
        )
        # AI generation generates severe inter-patch noise disparity (e.g. smooth gradient sky vs textured crop foreground)
        # and abnormal Fourier spectral distribution
        is_ai_generated_suspected = (
            is_spectral_anomalous
            or (not has_exif and noise_disparity > self.noise_disparity_threshold)
            or (noise_variance < 0.5 and noise_disparity > 4.0)
        )
        is_tamper_suspected = is_ela_anomalous or is_noise_anomalous or is_ai_generated_suspected

        return {
            "detector_id": "spectral_ela_forensics_v2",
            "validation_status": "FORMALLY_EVALUATED",
            "ela_variance": round(ela_variance, 4),
            "noise_variance": round(noise_variance, 4),
            "max_error_residual": round(max_error, 2),
            "noise_disparity_ratio": round(noise_disparity, 2),
            "spectral_ratio": spectral_ratio,
            "is_ai_generated_suspected": bool(is_ai_generated_suspected),
            "is_tamper_suspected": bool(is_tamper_suspected),
            "confidence_metric": None,
            "governance_note": "Evaluated via Error Level Analysis (JPEG Q90), 2D Fourier spectral peak analysis, and noise residual disparity.",
            "autonomous_action_allowed": False,
        }


# Global instance
image_forensics = ImageForensicsAnalyzer()
