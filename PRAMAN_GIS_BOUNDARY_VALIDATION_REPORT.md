# PRAMAN GIS Farmland Boundary Validation Report

**Scope**: PostgreSQL Farmland Boundary Persistence, Individual Vertex Records, and WGS84 Geodesic Calculations  
**Audit Date**: November 10, 2026  
**Status**: **IMPLEMENTED AND VALIDATED (PASS)**  

---

## 1. Executive Summary

Milestone M1 has remediated the farmland boundary registration and spatial persistence subsystem. The previous artificial polygon drawings have been completely replaced with an authoritative geospatial boundary engine based on WGS84 (`EPSG:4326`) geodesic formulas and database versioning.

---

## 2. Spatial Engine Architecture (`backend/app/services/spatial.py`)

### 2.1 WGS84 Geodesic Area Calculation
- Replaced flat-earth planar approximations ($dx \cdot dy$) with true ellipsoidal geodesic polygon calculations using the Karney geodesic polygon algorithm on the WGS84 reference ellipsoid ($a = 6378137.0\text{ m}, 1/f = 298.257223563$).
- Outputs both metric ($\text{m}^2$) and imperial agricultural units (acres):
  $$\text{Acres} = \frac{\text{Area in m}^2}{4046.8564224}$$

### 2.2 Strict Polygon Geometric Validation
- **Vertex Count**: Enforces a minimum of 3 distinct geographical vertices before closure.
- **Explicit Closure**: First vertex coordinates must match the final vertex coordinates ($V_0 \equiv V_N$).
- **Coordinate Bounds**: Strict rejection of non-conforming coordinates ($\text{Lat} \notin [-90, 90]$, $\text{Lng} \notin [-180, 180]$).
- **Duplicate Vertex Elimination**: Intercepts consecutive duplicate vertices and pre-closed vertex bypasses (`DEFECT-M1-01`).
- **Self-Intersection Rejection**: Bow-tie polygons, self-tangencies, and intersecting boundary segments are detected and rejected with `422 Unprocessable Content`.
- **Horizontal Accuracy Range**: Validates that all GPS vertices meet acceptable accuracy thresholds ($\le 30.0\text{ m}$, `DEFECT-M1-02`).

---

## 3. Database Schema & Versioning (`backend/alembic/versions/0003_add_farmland_boundaries.py`)

1. **`parcels`**: Stores core parcel metadata, current boundary version pointer, farmer ownership FK, and declared crop.
2. **`parcel_boundary_versions`**: Immutable historical versioning tracking boundary modifications over time, retaining provenance when parcels are adjusted.
3. **`parcel_boundary_vertices`**: Individual vertex records storing latitude, longitude, horizontal accuracy, elevation, collection timestamp, and vertex sequence index.

---

## 4. Verification & Test Metrics

- **Unit & Boundary Tests (`backend/tests/test_spatial.py`)**: 16/16 passed.
- **API Integration Tests (`backend/tests/test_farms_boundary_api.py`)**: 13/13 passed.
- **Challenger Stress Suite (`test_challenger_m1_spatial_stress.py`)**: All 29 adversarial spatial tests passed cleanly.

