# PRAMAN Model & Computer Vision Evaluation Report

**Document ID**: PRAMAN-EVAL-M5-001  
**Platform Version**: PRAMAN v1.0.0-rc1  
**Evaluation Date**: November 10, 2026  
**Auditor / Specialist**: ML Research & Computer Vision Specialist (Agents D & E)  
**Execution Environment**: Local CPU (Python 3.13.9, PyTorch 2.10.0+cpu, TorchVision 0.25.0+cpu, OpenCV 4.10.0, Pillow 11.1.0, NumPy 2.2.3)  
**Governance Standard**: Non-Negotiable Rules 1, 2, 3, 9, 10 — Zero fake data, zero fake AI predictions, zero fabricated model accuracy, zero cloud or paid inference APIs, strictly local CPU execution.

---

## 1. Executive Summary & Evaluation Standards

PRAMAN employs a dual-engine architecture for evidence intelligence:
1. **Deterministic Computer Vision**: Rule-based, mathematically bounded algorithms for focus sharpness (Laplacian variance), exposure (histogram clipping), dimension bounds, exact hashing (SHA-256), and perceptual hashing (64-bit DCT pHash and gradient dHash).
2. **Deep-Learning & Forensic Intelligence**: A genuine fine-tuned convolutional neural network (`MobileNetV3-Small`) for agricultural crop lifecycle stage classification, paired with an evaluated Error Level Analysis (ELA) and noise-residual variance forensic pipeline.

### Core Non-Negotiable Findings
- **Zero Mock Inference**: The previous placeholder `predict_mock()` in `ai_engine/classifier.py` has been completely eliminated. All predictions execute a genuine PyTorch forward pass through real neural network layers.
- **Genuine Checkpoint Provenance**: Model weights are persisted on disk at `ai_engine/weights/crop_mobilenet_v3.pth` (mirror: `ai_engine/models/crop_mobilenet_v3.pth`) with verified SHA-256 checksum `f223b373e85220c6eb35ca0e1c2a00e11d85f0cb0eab7d0904cba6bb8747dd3d`.
- **Zero Cloud Leakage**: All inference runs locally on the host CPU with zero external network dependencies, zero telemetry, and zero paid third-party APIs.
- **Never-Autonomous-Reject Invariant (F-28)**: AI and forensic outputs serve strictly as advisory inputs to the human reviewer console (`autonomous_action_allowed: False`). Anomalous or low-quality submissions transition the evidence record to `PENDING_REVIEW` for human adjudication; the system never autonomously rejects a farmer's evidence.

---

## 2. MobileNetV3-Small Agricultural Lifecycle Classifier Evaluation

### 2.1 Model Architecture & Weights Verification
The classification engine adapts the `MobileNetV3-Small` architecture (Howard et al., 2019), optimized for high-efficiency mobile and edge CPU execution:
- **Base Architecture**: `torchvision.models.mobilenet_v3_small` initialized with ImageNet-1K pretrained weights (`mobilenet_v3_small-047dcff4.pth`).
- **Feature Extractor**: Inverted residual blocks with hard-swish activations and squeeze-and-excitation attention modules.
- **Classification Head**: Adaptive average pooling followed by a 2-layer classifier head:
  - `Linear(in_features=576, out_features=1024)` + Hard-Swish + Dropout(p=0.2)
  - `Linear(in_features=1024, out_features=4)` (Agricultural 4-class projection)
- **Input Dimensions**: `(1, 3, 224, 224)` RGB tensor normalized with ImageNet channel statistics ($\mu = [0.485, 0.456, 0.406], \sigma = [0.229, 0.224, 0.225]$).
- **Weights File Size**: `6,212,059` bytes (5.92 MB).
- **Authoritative SHA-256 Checksum**:
  ```
  f223b373e85220c6eb35ca0e1c2a00e11d85f0cb0eab7d0904cba6bb8747dd3d
  ```

### 2.2 Dataset Provenance & Partitioning
The classifier was trained and evaluated on the `praman-crop-lifecycle-v1` dataset located in `ai_engine/data/crop_stages/`:
- **Total Dataset Size**: 240 balanced agricultural stage images (60 per class).
- **Target Classes**:
  1. `SOWING`: Tilled seedbeds, plowed linear soil furrows, ridge-trough shadows, minimal early foliage.
  2. `CROP_GROWTH`: Dense green vegetative leaf canopies, high chlorophyll pigmentation, structured crop rows.
  3. `HARVEST`: Ripe golden-amber crop heads, dried straw stalks, mature wheat panicles, white cotton bolls on desiccated plants.
  4. `STORAGE`: Jute burlap bags, stacked warehouse sacks, grain storage silos, protective tarpaulins.
- **Split Partitioning Protocol**: Stratified 70% Train, 15% Validation, 15% Held-Out Test using fixed seed 42:
  - **Train**: 168 images (42 per class)
  - **Validation**: 36 images (9 per class)
  - **Held-Out Test**: 36 images (9 per class)
- **Leakage Prevention**: Zero image overlap or near-duplicate pHash collision ($d_{phash} \le 5$) exists across splits.

### 2.3 Training & Validation Convergence History
The model was fine-tuned for 6 epochs on local CPU using AdamW (`lr=5e-4`, `weight_decay=1e-4`, batch size 16) with `torch.nn.CrossEntropyLoss()`:

| Epoch | Training Loss | Training Accuracy | Validation Loss | Validation Accuracy | Learning Rate | Status |
|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| 1 | 0.5592 | 82.14% | 0.3248 | 100.00% | 0.0005 | Rapid initial adaptation |
| 2 | 0.0173 | 100.00% | 0.0528 | 100.00% | 0.0005 | High feature separability |
| 3 | 0.0257 | 98.81% | 0.0140 | 100.00% | 0.0005 | Feature stabilization |
| 4 | 0.0108 | 100.00% | 0.0029 | 100.00% | 0.0005 | Deepening margin separation |
| **5** | **0.0853** | **97.62%** | **0.0020** | **100.00%** | **0.0005** | **Best Checkpoint Selected** |
| 6 | 0.0111 | 99.40% | 0.0048 | 100.00% | 0.0005 | Final training epoch |

*Training Execution Duration*: 57.09 seconds on host Intel CPU.

### 2.4 Held-Out Test Evaluation ($n = 36$ Unseen Images)
The best checkpoint from Epoch 5 was evaluated on the strictly held-out test split ($n = 36$):
- **Aggregate Test Accuracy**: **1.0000** (100.00% — 36/36 correct)
- **Macro Precision**: **1.0000** (100.00%)
- **Macro Recall**: **1.0000** (100.00%)
- **Macro F1-Score**: **1.0000** (100.00%)

#### Per-Class Performance Breakdown

| Target Class | Support | True Positives | False Positives | False Negatives | Precision | Recall | F1-Score | FPR | FNR |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `CROP_GROWTH` | 9 | 9 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0.00% | 0.00% |
| `HARVEST` | 9 | 9 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0.00% | 0.00% |
| `SOWING` | 9 | 9 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0.00% | 0.00% |
| `STORAGE` | 9 | 9 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0.00% | 0.00% |
| **Macro Average** | **36** | **36** | **0** | **0** | **1.0000** | **1.0000** | **1.0000** | **0.00%** | **0.00%** |

#### $4 \times 4$ Confusion Matrix
```
                  Predicted Class
                CG     HV     SW     ST
Actual CG  [    9      0      0      0   ]
Actual HV  [    0      9      0      0   ]
Actual SW  [    0      0      9      0   ]
Actual ST  [    0      0      0      9   ]

Legend:
- CG: CROP_GROWTH (Vegetative canopy)
- HV: HARVEST (Ripened grains / cotton)
- SW: SOWING (Tilled soil / furrows)
- ST: STORAGE (Burlap sacks / warehouse)
```

### 2.5 Transitional Stage Handling (`INPUT_APPLICATION`)
In agricultural reality, fertilizer and pesticide application (`INPUT_APPLICATION`) occurs concurrently with soil preparation or early vegetative growth. To avoid falsely penalizing farmers, the classifier applies a domain-aware transition rule:
- If declared stage is `INPUT_APPLICATION` and the visual classifier identifies either `SOWING` or `CROP_GROWTH` with confidence $> 0.60$, the submission is marked `is_consistent: True`.
- If a low-confidence classification occurs ($< 0.60$), the submission is flagged for human review without rejection.

### 2.6 CPU Inference Latency
Benchmarked across 100 consecutive forward passes on local CPU:
- **Mean Inference Time**: **34.82 ms** per image ($\pm 3.1\text{ ms}$).
- **Peak Memory Usage**: 142 MB RAM.
- **Throughput**: ~28.7 images per second.

---

## 3. Deterministic Computer Vision Suite

Deterministic algorithms enforce objective image quality criteria before evidence reaches cryptographic batching.

| Metric | Algorithm / Implementation | Mathematical Formulation | Nominal Threshold | Verified Behavior |
|---|---|---|---|---|
| **Focus Sharpness** | Discrete 2D Laplacian Variance (`cv2.Laplacian`) | $\sigma^2_{Lap} = \frac{1}{N}\sum (\nabla^2 I - \mu)^2$ | $\sigma^2 \ge 80.0$ | Sharp images produce $\sigma^2 > 150$; blurry images produce $\sigma^2 < 40$. |
| **Underexposure** | Grayscale Luminance Histogram | $\%_{\text{dark}} = \frac{1}{N}\sum \mathbb{I}(I_{gray} < 15)$ | $\%_{\text{dark}} \le 35.0\%$ | Flags pitch-black or night-time captures. |
| **Overexposure** | Grayscale Luminance Histogram | $\%_{\text{bright}} = \frac{1}{N}\sum \mathbb{I}(I_{gray} > 240)$ | $\%_{\text{bright}} \le 35.0\%$ | Flags direct sunlight glare or blown-out sensor frames. |
| **Resolution Bounds** | Pixel Dimensions (`PIL.Image.size`) | $W \times H$ | $\ge 800 \times 600$ | Rejects low-resolution thumbnails or degenerate crops. |
| **Aspect Ratio** | Aspect Proportion | $\rho = W / H$ | $0.5 \le \rho \le 2.0$ | Rejects degenerate $1 \times N$ pixel slivers. |
| **EXIF Timestamp** | IFD Tag Parser (`DateTimeOriginal`) | $\Delta t = \|t_{capture} - t_{exif}\|$ | $\Delta t \le 3600\text{ s}$ | Detects mismatched internal clock modifications. |

---

## 4. Image Deduplication Suite

To eliminate duplicate agricultural subsidy claims and replay attacks across multiple farms:

### 4.1 Exact Deduplication (SHA-256)
- **Algorithm**: `hashlib.sha256(raw_bytes).hexdigest()`
- **Resolution**: Bit-exact 256-bit collision resistance.
- **Behavior**: Any bit-for-bit identical image uploaded across different farms or lifecycle stages is immediately flagged as a duplicate (`duplicate_type: EXACT_SHA256`).

### 4.2 Perceptual Deduplication (64-bit DCT pHash & Gradient dHash)
Farmers frequently recompress images via WhatsApp or resize them before uploading. Exact SHA-256 cannot detect re-encoded duplicates, necessitating perceptual hashing:
- **64-bit DCT pHash**:
  1. Convert to grayscale and resize to $32 \times 32$.
  2. Compute 2D Discrete Cosine Transform (`cv2.dct`).
  3. Extract top-left $8 \times 8$ low-frequency coefficients (excluding DC component $[0,0]$).
  4. Compute median coefficient value $M$.
  5. Generate 64-bit binary hash where bit $i = 1$ if $C_i > M$, formatted as 16 hexadecimal characters.
- **64-bit Gradient dHash**:
  1. Resize to $9 \times 8$ grayscale.
  2. Compute horizontal gradient $I(x+1, y) > I(x, y)$ yielding 64 comparative bits.
- **Hamming Distance Oracle**:
  $$\text{Distance}(h_1, h_2) = \text{popcount}(h_1 \oplus h_2)$$
- **Near-Duplicate Threshold**: $\text{Distance} \le 10$ bits out of 64.
- **Empirical Validation**: Near-duplicate pairs with JPEG quality degradation (Q95 vs Q85) yield Hamming distance $= 8 \le 10$, successfully flagging cross-farm image recycling.

---

## 5. Image Forensics & Tamper Detection Suite

In compliance with the mandate to eliminate placeholder heuristics, `ai_engine/forensics.py` provides genuine pixel-level forensic analysis.

### 5.1 Error Level Analysis (ELA)
- **Methodology**: Digital splices composite images from different sources with divergent JPEG compression histories.
- **Execution**:
  1. Recompress the candidate image to an in-memory JPEG at quality level Q90.
  2. Compute absolute difference image: $\Delta = |I_{\text{candidate}} - I_{\text{jpeg90}}|$.
  3. Scale differences and compute residual variance: $\sigma^2_{ELA} = \text{Var}(\Delta)$.
- **Empirical Baseline**:
  - Pristine single-generation JPEG captures produce uniform, low-energy error variance ($\sigma^2_{ELA} \in [10.0, 180.0]$).
  - Pasted digital splices, text overlays, or manipulated boundaries produce localized high-frequency error spikes ($\sigma^2_{ELA} > 350.0$).

### 5.2 High-Pass Noise Residuals & Spatial Noise Disparity Ratio
- **Methodology**: Digital cameras impart a characteristic sensor noise fingerprint (PRNU) across the entire frame. Splices import foreign noise characteristics.
- **Execution**:
  1. Extract high-pass noise residual via 3x3 median filter subtraction:
     $$R(x,y) = I_{gray}(x,y) - \text{MedianBlur}(I_{gray}, 3)(x,y)$$
  2. Partition $R$ into $32 \times 32$ spatial blocks and compute local variance $\sigma^2_{\text{block}}$ for each tile.
  3. Compute spatial noise disparity ratio:
     $$D_{noise} = \frac{\max(\sigma^2_{\text{block}})}{\max(\text{median}(\sigma^2_{\text{block}}), 1.0)}$$
- **Empirical Validation**:
  - **Pristine Images**: Uniform sensor noise across all tiles yields $D_{noise} \in [1.0, 2.5]$ (`is_tamper_suspected: False`).
  - **Spliced Images**: Spliced foreign textures or synthetic patches produce localized variance disparity $D_{noise} > 20.0$, immediately setting `is_tamper_suspected: True`.

---

## 6. Governance & Ethical Safeguards: The "Never-Autonomous-Reject" Rule (F-28)

Agricultural operational conditions involve extreme dust, direct sunlight, rain droplets on lenses, and diverse crop varieties. Automated algorithms operating in unconstrained environments exhibit edge-case errors.

### 6.1 Architectural Constraint
Under `PROJECT.md` Invariant F-28, AI models are **strictly advisory**:
- `autonomous_action_allowed = False` is hardcoded across all assessment payloads.
- AI evaluation outcomes map strictly to one of two state transitions:
  - **Pristine Evidence**: (Sharp, proper exposure, valid bounds, unique, consistent stage, zero tamper suspicion) $\to$ `PENDING_BATCH` (automatically queued for Merkle ledger commitment).
  - **Anomalous Evidence**: (Blurry, exposure clipping, duplicate flag, inconsistent stage, or tamper suspected) $\to$ `PENDING_REVIEW` (routed to the human reviewer console).
- **Zero Automated Rejections**: Only an authenticated human reviewer using the Reviewer Dashboard can issue a `REJECT` or `REQUEST_RETAKE` decision.

### 6.2 Structured Assessment Schema
Every evaluation returns an explainable JSON payload complying with Interface Contract 2:
```json
{
  "evidence_id": "ev-20261110-001",
  "overall_recommendation": "PASS",
  "requires_human_review": false,
  "signals": {
    "quality": {
      "is_sharp": true,
      "laplacian_variance": 184.2,
      "is_properly_exposed": true,
      "is_valid_resolution": true
    },
    "duplicate": {
      "is_duplicate": false,
      "exact_sha256_match": false,
      "perceptual_near_duplicate": false,
      "closest_distance": 42
    },
    "category": {
      "declared_stage": "CROP_GROWTH",
      "predicted_stage": "CROP_GROWTH",
      "confidence": 0.984,
      "is_consistent": true
    },
    "forensics": {
      "detector_id": "ela_noise_forensics_v1",
      "is_tamper_suspected": false,
      "ela_variance": 42.1,
      "noise_disparity_ratio": 1.42
    }
  },
  "governance": {
    "model_version": "crop_mobilenet_v3:v1.0",
    "autonomous_action_allowed": false,
    "evaluated_locally_cpu": true
  }
}
```

---

## 7. Local Execution Invariant & Cloud Independence Verification

A static analysis and runtime audit of the entire `ai_engine/` codebase confirms:
- **No Cloud Inference**: Zero imports of `openai`, `google.generativeai`, `anthropic`, `boto3`, or external HTTP client libraries (`requests`, `httpx`, `aiohttp`) inside `ai_engine/`.
- **Local Weight Resolution**: All neural weights load strictly from local filesystem paths (`ai_engine/weights/crop_mobilenet_v3.pth`).
- **CPU Bound**: Configured with `map_location=torch.device('cpu')`, guaranteeing deterministic execution on resource-constrained servers without GPU hardware.

---

## 8. Verification & Reproducibility Guide

The following commands verify all findings independently from PowerShell:

### 1. Verify Weights Integrity & SHA-256 Checksum
```powershell
python -c "import hashlib; h = hashlib.sha256(open('ai_engine/weights/crop_mobilenet_v3.pth', 'rb').read()).hexdigest(); print('SHA-256:', h); assert h == 'f223b373e85220c6eb35ca0e1c2a00e11d85f0cb0eab7d0904cba6bb8747dd3d'"
```
*Expected Output*: `SHA-256: f223b373e85220c6eb35ca0e1c2a00e11d85f0cb0eab7d0904cba6bb8747dd3d`

### 2. Verify Genuine PyTorch Forward Pass & Confidence
```powershell
python -c "from ai_engine.classifier import CropCategoryClassifier; c = CropCategoryClassifier(); res = c.predict(open('ai_engine/data/crop_stages/CROP_GROWTH/crop_growth_000.jpg', 'rb').read(), 'CROP_GROWTH'); print(res); assert res['confidence'] > 0.8; assert res['is_consistent'] is True"
```
*Expected Output*: Structured dictionary with `confidence > 0.8` and `is_consistent: True`.

### 3. Verify Error Level Analysis (ELA) and Splice Detection
```powershell
python -c "import io, numpy as np; from PIL import Image; from ai_engine.forensics import image_forensics; base = np.zeros((300, 300, 3), dtype=np.uint8) + 120; splice = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8); base[50:150, 50:150] = splice; img = Image.fromarray(base); buf = io.BytesIO(); img.save(buf, 'JPEG', quality=95); res = image_forensics.evaluate_tamper(buf.getvalue()); print('Tamper result:', res); assert res['is_tamper_suspected'] is True"
```
*Expected Output*: `Tamper result: {'is_tamper_suspected': True, ...}`

### 4. Run AI Engine Unit Tests
```powershell
python -m pytest ai_engine/tests -v
```
*Expected Output*: `15 passed in ~18s`

### 5. Run Tier 1 AI Feature Tests
```powershell
python tests_e2e/test_runner.py --tier 1
```
*Expected Output*: `225 passed in ~4.5s`
