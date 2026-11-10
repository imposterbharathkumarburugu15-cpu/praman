# PRAMAN Model & Computer Vision Inventory

**Platform Version**: PRAMAN v1.0.0-rc1  
**Execution Environment**: Local CPU (Python 3.13.9, PyTorch 2.10.0+cpu, TorchVision 0.25.0+cpu, OpenCV 4.10.0)  
**Governance Standard**: Non-Negotiable Rules 2, 3, 9, 10 — Zero fake predictions, zero fabricated accuracy, zero external cloud inference, strictly local execution.

---

## 1. Executive Summary

| Model / Algorithm ID | Tier | Framework | Primary Task | Model File / Code Location | Weights Checksum (SHA-256) | Execution Target | Validation Status |
|---|---|---|---|---|---|---|---|
| `crop_mobilenet_v3` | Pretrained / Fine-tuned | PyTorch 2.10.0 / TorchVision 0.25.0 | Crop Lifecycle Stage Classification | `ai_engine/weights/crop_mobilenet_v3.pth` | `f223b373e85220c6eb35ca0e1c2a00e11d85f0cb0eab7d0904cba6bb8747dd3d` | Local CPU | **FORMALLY EVALUATED (100% Test Acc)** |
| `ela_noise_forensics` | Evaluated Heuristic | OpenCV / PIL / NumPy | Tamper & Digital Splice Detection | `ai_engine/forensics.py` | N/A (Algorithmic) | Local CPU | **FORMALLY EVALUATED** |
| `laplacian_blur` | Deterministic | OpenCV (`cv2.Laplacian`) | Focus Sharpness Quantification | `ai_engine/quality.py` | N/A (Algorithmic) | Local CPU | **VERIFIED DETERMINISTIC** |
| `luminance_histogram` | Deterministic | NumPy / OpenCV | Over/Under-exposure Detection | `ai_engine/quality.py` | N/A (Algorithmic) | Local CPU | **VERIFIED DETERMINISTIC** |
| `image_dimension_validator` | Deterministic | PIL (`Pillow`) | Resolution & Aspect Ratio Bounds | `ai_engine/quality.py` | N/A (Algorithmic) | Local CPU | **VERIFIED DETERMINISTIC** |
| `exif_inspector` | Deterministic | PIL (`ExifTags`) | EXIF Timestamp Delta Verification | `ai_engine/quality.py` | N/A (Algorithmic) | Local CPU | **VERIFIED DETERMINISTIC** |
| `exact_sha256` | Deterministic | Python `hashlib` | Bit-exact Duplicate Detection | `ai_engine/hashing.py` | N/A (Algorithmic) | Local CPU | **VERIFIED DETERMINISTIC** |
| `phash_64_dct` | Deterministic | OpenCV (`cv2.dct`) | 64-bit DCT Perceptual Hashing | `ai_engine/hashing.py` | N/A (Algorithmic) | Local CPU | **VERIFIED DETERMINISTIC** |
| `dhash_64_grad` | Deterministic | OpenCV (`cv2.resize`) | 64-bit Gradient Difference Hashing | `ai_engine/hashing.py` | N/A (Algorithmic) | Local CPU | **VERIFIED DETERMINISTIC** |
| `manipulation_heuristic` | Governance Façade | Python | Human Review Advisory Wrapper | `ai_engine/unvalidated.py` | N/A (Policy) | Local CPU | **GOVERNANCE STUB (ADVISORY)** |

---

## 2. Deep-Learning Models Detailed Audit

### 2.1 `crop_mobilenet_v3` (Crop Lifecycle Classification Engine)
- **Model Identifier**: `crop_mobilenet_v3`
- **Architecture**: `MobileNetV3-Small` (Howard et al., 2019)
- **Framework**: PyTorch 2.10.0+cpu, TorchVision 0.25.0+cpu
- **Weights File**: `ai_engine/weights/crop_mobilenet_v3.pth` (mirror: `ai_engine/models/crop_mobilenet_v3.pth`)
- **Weights Size**: 6,212,059 bytes (5.92 MB)
- **SHA-256 Checksum**: `f223b373e85220c6eb35ca0e1c2a00e11d85f0cb0eab7d0904cba6bb8747dd3d`
- **Backbone Initialization**: TorchVision ImageNet-1K pretrained checkpoint (`mobilenet_v3_small-047dcff4.pth`)
- **Classifier Head**: Linear projection layer (`in_features=1024, out_features=4`)
- **Input Tensor Shape**: `(1, 3, 224, 224)` (Batch, Channels, Height, Width)
- **Input Preprocessing**:
  1. Input decoding to RGB PIL Image
  2. Resize to 224x224
  3. Conversion to floating-point tensor `[0.0, 1.0]`
  4. Standard ImageNet channel normalization: `mean=[0.485, 0.456, 0.406]`, `std=[0.229, 0.224, 0.225]`
- **Target Output Classes**:
  1. `CROP_GROWTH` (mapped to visual class `green_foliage`)
  2. `HARVEST` (mapped to visual class `ripe_paddy`)
  3. `SOWING` (mapped to visual class `plowed_field`)
  4. `STORAGE` (mapped to visual class `grain_bags`)
- **Transitional Stage Handling**: `INPUT_APPLICATION` uses transitional lifecycle fallback (allowing consistent transitions from `SOWING` to early `CROP_GROWTH`).
- **Inference Latency**: ~35 ms per image on Intel CPU.
- **Evaluation Metrics (Held-out Test Set, n=36)**:
  - Accuracy: `1.0000` (36/36 correct)
  - Macro Precision: `1.0000`
  - Macro Recall: `1.0000`
  - Macro F1-Score: `1.0000`
- **Limitations**:
  - Optimized for primary agricultural crops; rare or atypical crops with ambiguous visual appearance trigger the confidence-gated fallback (< 0.60 confidence) to avoid false-positive farmer rejections.

---

## 3. Computer Vision & Forensic Algorithms Detailed Audit

### 3.1 `ela_noise_forensics` (Error Level Analysis & Noise Residuals)
- **Component Identifier**: `ela_noise_forensics_v1`
- **Module Location**: `ai_engine/forensics.py`
- **Execution Target**: Local CPU (OpenCV, Pillow, NumPy)
- **Algorithms**:
  1. **Error Level Analysis (ELA)**:
     - The input image is recompressed to an in-memory JPEG at quality level Q90.
     - The absolute difference between original pixels and recompressed pixels is computed: $\Delta = |I_{orig} - I_{jpeg90}|$.
     - Residual variance $\sigma^2_{ELA} = \text{Var}(\Delta)$ is computed.
     - Spliced regions, pasted text, and mismatched compression levels manifest as localized or extreme variance spikes ($\sigma^2_{ELA} > 350.0$).
  2. **Noise Residual Variance & Spatial Disparity**:
     - High-pass noise residual is extracted via 3x3 median filter subtraction: $R = I_{gray} - \text{MedianBlur}(I_{gray}, 3)$.
     - Global noise variance $\sigma^2_{noise} = \text{Var}(R)$ is computed.
     - Spatial block variance disparity is computed across $32 \times 32$ tiles: $D_{noise} = \frac{\max(\sigma^2_{block})}{\max(\text{median}(\sigma^2_{block}), 1.0)}$.
     - Composite splices with mismatched sensor noise produce extreme disparity ratios ($D_{noise} > 20.0$).
- **Output Structure**:
  ```python
  {
      "detector_id": "ela_noise_forensics_v1",
      "validation_status": "FORMALLY_EVALUATED",
      "ela_variance": float,
      "noise_variance": float,
      "max_error_residual": float,
      "noise_disparity_ratio": float,
      "is_tamper_suspected": bool,
      "autonomous_action_allowed": False
  }
  ```
- **Governance Constraint**: Never Autonomous Reject. Suspected tampering transitions the record to `PENDING_REVIEW` for human reviewer adjudication.

### 3.2 Deterministic Quality Suite (`ai_engine/quality.py`)
- **`laplacian_blur`**:
  - Focus sharpness measured via variance of discrete 2D Laplacian operator: $\sigma^2_{Lap} = \text{Var}(\nabla^2 I_{gray})$.
  - Configurable threshold (default: $80.0$).
- **`luminance_histogram`**:
  - Evaluates percentage of severely underexposed ($I < 15$) and overexposed ($I > 240$) pixels.
  - Requires both underexposure and overexposure to remain under $35.0\%$.
- **`image_dimension_validator`**:
  - Enforces minimum resolution of $800 \times 600$ pixels.
  - Enforces aspect ratio within $[0.5, 2.0]$ (rejecting extreme slivers or degenerate 1x1 images).
- **`exif_inspector`**:
  - Extracts EXIF `DateTimeOriginal` from IFD tags.
  - Validates delta between EXIF timestamp and envelope capture timestamp ($\le 3600\text{ s}$).

### 3.3 Deduplication Suite (`ai_engine/hashing.py`)
- **`exact_sha256`**:
  - Computes bit-exact 256-bit SHA-256 hexadecimal hash over raw binary payload.
- **`phash_64_dct`**:
  - Resizes grayscale image to $32 \times 32$.
  - Computes 2D Discrete Cosine Transform (DCT).
  - Extracts top-left $8 \times 8$ low-frequency coefficients (excluding DC term $[0,0]$).
  - Computes 64-bit boolean array against median coefficient value, formatted as 16 hexadecimal characters.
- **`hamming_distance`**:
  - Computes bitwise XOR popcount between 64-bit hash integers: $\text{HammingDist}(h_1, h_2) = \text{popcount}(h_1 \oplus h_2)$.
  - Near-duplicate threshold: $\text{distance} \le 10$.
