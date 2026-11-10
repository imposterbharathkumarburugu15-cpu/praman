# PRAMAN Final Defect Register & Resolution Ledger

**Audit Scope**: Complete Platform Defect Discovery, Remediation, and Regression Ledger  
**Date**: November 10, 2026  
**Final Status**: **ALL 58 DEFECTS PERMANENTLY REMEDIATED**  

---

## 1. Summary of Defects Remediated

| Subsystem | Defects Discovered | Severity Breakdown | Status |
|---|---|---|:---:|
| **Android Client & Mobile UI** | 17 | 6 Critical, 8 High, 3 Medium | **100% REMEDIATED** |
| **Backend & PostgreSQL Storage** | 26 | 9 Critical, 12 High, 5 Medium | **100% REMEDIATED** |
| **AI, CV & Duplicate Detection** | 15 | 7 Critical, 5 High, 3 Medium | **100% REMEDIATED** |
| **Total** | **58** | **22 Critical, 25 High, 11 Medium** | **0 DEFECTS REMAIN** |

---

## 2. Key Critical Defect Resolutions

1. **`DEF-MOB-01` (In-Memory Array Queue Data Loss)**:
   - *Issue*: Queue was stored in a volatile JavaScript array (`this.queue = []`).
   - *Fix*: Implemented native Android `EvidenceDbHelper.java` using persistent SQLite with WAL journaling.
2. **`DEF-MOB-02` (Camera Heap OutOfMemoryError)**:
   - *Issue*: Loading 12MP-48MP photos directly into WebView crashed the app.
   - *Fix*: Added `inJustDecodeBounds` probing and `RGB_565` downsampling with native 16KB streaming SHA-256 computation.
3. **`DEF-GIS-01` (Artificial Polygon & Flat-Earth Area)**:
   - *Issue*: Area was estimated with planar formulas on artificial coordinate jitter.
   - *Fix*: Implemented ellipsoidal WGS84 geodesic polygon calculations and interactive corner-walking with boundary versioning.
4. **`DEF-DEDUP-01` (Inert Duplicate Detection)**:
   - *Issue*: Repeated submissions created redundant evidence records.
   - *Fix*: Implemented `duplicate_service.py` with dual-track exact SHA-256 and 64-bit DCT pHash/dHash comparisons.
5. **`DEF-ML-01` (Mock AI Confidence Return)**:
   - *Issue*: `predict_mock()` returned hardcoded `0.88` confidence with zero model weights.
   - *Fix*: Fine-tuned PyTorch `MobileNetV3-Small` on crop lifecycle stages, saved `.pth` weights to disk, and wired real tensor CPU forward passes.
6. **`DEF-NET-01` (Mobile Data Offline False Positive)**:
   - *Issue*: App reported offline when connected over mobile data.
   - *Fix*: Implemented 3-tier Android `ConnectivityManager` monitoring device network state, internet ping, and local backend health.

