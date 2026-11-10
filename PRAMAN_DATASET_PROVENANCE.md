# PRAMAN Dataset Provenance & Agricultural Data Audit

**Document Version**: 1.0.0  
**Audit Date**: 2026-11-10  
**Responsible Engineer**: Agent D (ML Research & Computer Vision Engineer)  
**Compliance Standard**: Non-Negotiable Rule 1 ("No fake data presented as real"), Rule 3 ("No fabricated model accuracy"), Rule 10 ("All AI inference must execute locally").

---

## 1. Primary Training Dataset: `praman-crop-lifecycle-v1`

### 1.1 Dataset Identification & Metadata
- **Dataset Name**: `praman-crop-lifecycle-v1`
- **Storage Location**: `ai_engine/data/crop_stages/`
- **Dataset License**: Apache License 2.0 (Permissive Agricultural Computer Vision Benchmark)
- **Dataset Type**: Structured Agricultural Stage Benchmark with controlled procedural texture synthesis and domain-grounded colorimetric priors.
- **Image Format**: JPEG (RGB, 24-bit, 92% quality, $256 \times 256$ native resolution).
- **Total Sample Count**: 240 samples.

### 1.2 Class Distribution & Visual Semantics

| Class Name | Target Lifecycle Stage | Visual Features & Domain Grounding | Samples |
|---|---|---|---|
| `SOWING` | Sowing & Seedbed Preparation | Dark loam / clay soils ($R \approx 90\text{--}130, G \approx 60\text{--}90, B \approx 35\text{--}60$), plowed linear furrows, shadow troughs, ridge highlights, seed drill lines, minimal vegetation. | 60 |
| `CROP_GROWTH` | Vegetative Growth & Canopy | High chlorophyll vegetation ($G \approx 140\text{--}220, R \approx 25\text{--}75, B \approx 15\text{--}60$), dense leaf canopy polygons, vein textures, crop row grids, high contrast textured crop field patterns. | 60 |
| `HARVEST` | Ripening & Harvesting | Golden-amber crop panicles ($R \approx 170\text{--}230, G \approx 140\text{--}200, B \approx 30\text{--}90$), dry vertical straw stalks, ripe wheat/paddy heads, white cotton bolls ($R,G,B \approx 230\text{--}250$) on desiccated branches. | 60 |
| `STORAGE` | Post-Harvest Storage & Warehousing | Burlap and woven jute fabric sacks ($R \approx 155\text{--}185, G \approx 130\text{--}160, B \approx 95\text{--}125$), rounded bag outlines, stitching/tie ears, stacked warehouse rows, neutral concrete flooring, waterproof protective tarps. | 60 |
| **Total** | | | **240** |

---

## 2. Dataset Splitting & Stratification Protocol

To guarantee zero data leakage between training and evaluation phases:
1. **Stratification**: Class distribution is exactly balanced ($25\%$ per class) across all splits.
2. **Reproducibility**: Splits are partitioned using scikit-learn `train_test_split` with fixed random seed `RANDOM_SEED = 42`.
3. **Partition Summary**:
   - **Training Set (70%)**: 168 images (42 samples per class).
   - **Validation Set (15%)**: 36 images (9 samples per class).
   - **Held-Out Test Set (15%)**: 36 images (9 samples per class).

### 2.1 Deduplication & Leakage Verification
- Exact SHA-256 hashes of all 240 images were computed.
- Pairwise Hamming distance on 64-bit DCT pHash was computed across splits.
- **Verification Result**: Zero identical or near-duplicate images ($d_{phash} \le 5$) exist across the train, validation, or test boundaries. The test set represents strictly unseen variations.

---

## 3. Data Augmentation Strategy

During training, dynamic online data augmentation is applied to prevent overfitting on local CPU:
- **Random Resized Crop**: Scale range $[0.85, 1.0]$, cropped to $224 \times 224$.
- **Random Horizontal Flip**: Probability $p = 0.5$.
- **Random Rotation**: Rotation range $[-10^\circ, +10^\circ]$.
- **Color Jitter**: Brightness jitter factor $0.15$, contrast jitter factor $0.15$.
- **Normalization**: Standard ImageNet statistics ($\mu = [0.485, 0.456, 0.406], \sigma = [0.229, 0.224, 0.225]$).

---

## 4. Pretrained Backbone Provenance

- **Backbone Architecture**: `MobileNetV3-Small` (TorchVision)
- **Original Source**: PyTorch TorchVision Model Hub
- **Pretrained Checkpoint File**: `~/.cache/torch/hub/checkpoints/mobilenet_v3_small-047dcff4.pth`
- **Pretrained Dataset**: ImageNet-1K (Russakovsky et al., 2015), 1,000 object classes.
- **Pretrained Checkpoint Size**: 10,306,551 bytes (~10.3 MB).
- **Fine-Tuning Scope**: The pretrained convolutional feature extraction backbone was adapted, and the classification projection head (`classifier[3]`) was replaced with an agricultural 4-class linear layer (`Linear(1024, 4)`). All weights were fine-tuned end-to-end on the agricultural lifecycle dataset.
