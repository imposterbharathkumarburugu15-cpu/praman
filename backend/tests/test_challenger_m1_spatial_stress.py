"""Milestone M1 Empirical Stress Tests: WGS84 Geodesic Area & Geometry Validation.
Adversarial challenge test suite authored by Challenger 1.
Tests boundary edge cases, mathematical ellipsoidal accuracy, self-intersections,
duplicate vertices, degenerate lines, and full persistence/versioning lifecycle.
"""

import json
import math
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.models.farmer import Farmer
from backend.app.models.farm import Farm
from backend.app.models.boundary_vertex import BoundaryVertex
from backend.app.models.boundary_history import BoundaryHistory
from backend.app.services.spatial import (
    validate_farm_polygon,
    calculate_wgs84_geodesic_area_sq_meters,
    calculate_farm_area_acres,
    calculate_polygon_area_hectares,
    validate_declared_area,
    WGS84_SEMI_MAJOR,
    WGS84_FLATTENING,
    WGS84_E2,
    _authalic_q,
    _QP,
    WGS84_AUTHALIC_RADIUS,
    M2_PER_ACRE,
    M2_PER_HECTARE,
)


@pytest.fixture(scope="function")
def stress_client(tmp_path):
    test_db_path = str(tmp_path / "stress_m1.db")
    engine = create_engine(f"sqlite:///{test_db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client, TestingSessionLocal
    app.dependency_overrides.clear()


@pytest.fixture
def stress_farmer_id(stress_client):
    client, _ = stress_client
    res = client.post("/api/v1/farmers", json={
        "full_name": "Empirical Farmer",
        "phone_number": "+919999900001",
        "language_pref": "te",
    })
    assert res.status_code == 201
    return res.json()["id"]


# ==============================================================================
# SECTION 1: ADVERSARIAL SELF-INTERSECTING POLYGONS
# ==============================================================================

def test_stress_self_intersecting_polygons():
    """Adversarial stress-testing of self-intersecting figures."""
    # 1. Classic bowtie (unclosed)
    bowtie_unclosed = [(10.0, 10.0), (11.0, 11.0), (10.0, 11.0), (11.0, 10.0)]
    valid, msg = validate_farm_polygon(bowtie_unclosed)
    assert not valid, "Unclosed bowtie must be rejected"
    assert "self-intersecting" in msg

    # 2. Classic bowtie (explicitly closed)
    bowtie_closed = [(10.0, 10.0), (11.0, 11.0), (10.0, 11.0), (11.0, 10.0), (10.0, 10.0)]
    valid, msg = validate_farm_polygon(bowtie_closed)
    assert not valid, "Closed bowtie must be rejected"
    assert "self-intersecting" in msg

    # 3. 5-pointed self-crossing star (pentagram)
    star = [(0.0, 0.0), (2.0, 4.0), (4.0, 0.0), (0.0, 3.0), (4.0, 3.0), (0.0, 0.0)]
    valid, msg = validate_farm_polygon(star)
    assert not valid, "Self-intersecting star must be rejected"
    assert "self-intersecting" in msg

    # 4. Hourglass polygon crossing in interior
    hourglass = [
        (17.380, 78.480),
        (17.390, 78.490),
        (17.380, 78.490),
        (17.390, 78.480),
        (17.380, 78.480),
    ]
    valid, msg = validate_farm_polygon(hourglass)
    assert not valid, "Hourglass polygon must be rejected"
    assert "self-intersecting" in msg


# ==============================================================================
# SECTION 2: DUPLICATE VERTICES (CONSECUTIVE & NON-CONSECUTIVE)
# ==============================================================================

def test_stress_duplicate_vertices_consecutive():
    """Adversarial stress-testing of consecutive duplicates."""
    # Consecutive duplicate in middle
    p1 = [(17.385, 78.486), (17.385, 78.486), (17.386, 78.486), (17.386, 78.487), (17.385, 78.486)]
    valid, msg = validate_farm_polygon(p1)
    assert not valid
    assert "Duplicate consecutive vertex" in msg

    # Consecutive duplicate at trailing closure
    p2 = [(17.385, 78.486), (17.386, 78.486), (17.386, 78.487), (17.385, 78.486), (17.385, 78.486)]
    valid, msg = validate_farm_polygon(p2)
    assert not valid
    assert "Duplicate consecutive vertex" in msg

    # Triple consecutive identical points
    p3 = [(17.385, 78.486), (17.385, 78.486), (17.385, 78.486), (17.386, 78.486), (17.386, 78.487)]
    valid, msg = validate_farm_polygon(p3)
    assert not valid
    assert "Duplicate consecutive vertex" in msg


def test_stress_duplicate_vertices_non_consecutive_unclosed():
    """Non-consecutive duplicate vertex in unclosed coordinates."""
    # Repeated point at index 0 and 2
    p_dup = [(17.385, 78.486), (17.386, 78.486), (17.385, 78.486), (17.386, 78.487)]
    valid, msg = validate_farm_polygon(p_dup)
    assert not valid
    assert "Duplicate" in msg


def test_stress_pinch_point_closed_polygon_empirical_check():
    """Empirical check for closed polygons with internal repeated pinch points.
    Reveals whether closed polygon bypasses unclosed duplicate check.
    """
    # A -> B -> C -> D -> B -> A (vertex B is visited twice, forming figure-8 touching at B)
    a, b, c, d = (17.380, 78.480), (17.385, 78.485), (17.390, 78.480), (17.385, 78.475)
    pinch_polygon = [a, b, c, d, b, a]
    valid, msg = validate_farm_polygon(pinch_polygon)
    # Document whether current implementation accepts or rejects this
    # If accepted, this confirms our finding of the 'if not is_closed' bypass
    print(f"Pinch polygon validation outcome: valid={valid}, msg='{msg}'")


# ==============================================================================
# SECTION 3: DEGENERATE COLLINEAR POINTS (ZERO AREA LINE)
# ==============================================================================

def test_stress_collinear_and_degenerate_geometries():
    """Adversarial stress-testing of collinear and zero-area geometries."""
    # Horizontal collinear line
    horiz = [(17.385, 78.480), (17.385, 78.485), (17.385, 78.490), (17.385, 78.480)]
    valid, msg = validate_farm_polygon(horiz)
    assert not valid
    assert "zero or degenerate area" in msg

    # Vertical collinear line
    vert = [(17.380, 78.485), (17.385, 78.485), (17.390, 78.485), (17.380, 78.485)]
    valid, msg = validate_farm_polygon(vert)
    assert not valid
    assert "zero or degenerate area" in msg

    # Diagonal collinear line
    diag = [(17.380, 78.480), (17.385, 78.485), (17.390, 78.490), (17.380, 78.480)]
    valid, msg = validate_farm_polygon(diag)
    assert not valid
    assert "zero or degenerate area" in msg

    # Ultra-thin micro sliver (< 0.1 m^2 area, width ~ 1.1 cm)
    sliver_degenerate = [
        (17.3850000, 78.4860000),
        (17.3860000, 78.4860000),
        (17.3850000, 78.4860001),
        (17.3850000, 78.4860000),
    ]
    valid, msg = validate_farm_polygon(sliver_degenerate)
    assert not valid
    assert "zero or degenerate area" in msg

    # Sub-millimeter sliver (< 1e-9 deg) caught by consecutive duplicate threshold
    sliver_sub_mm = [
        (17.3850000, 78.4860000),
        (17.3860000, 78.4860000),
        (17.3850000, 78.486000001),
        (17.3850000, 78.4860000),
    ]
    valid, msg = validate_farm_polygon(sliver_sub_mm)
    assert not valid
    assert "Duplicate consecutive vertex" in msg or "zero or degenerate area" in msg

    # Degenerate: only 2 unique points
    two_pts = [(17.385, 78.486), (17.386, 78.486), (17.385, 78.486)]
    valid, msg = validate_farm_polygon(two_pts)
    assert not valid
    assert "unique" in msg or "at least" in msg


# ==============================================================================
# SECTION 4: BENCHMARK ACCURACY VS ANALYTICAL ELLIPSOIDAL GEODESICS
# ==============================================================================

def test_benchmark_1_hectare_equator_accuracy():
    """Benchmark 1: 1 hectare (10,000 m^2) box at the Equator.
    Compares computed geodesic area with analytical ellipsoidal surface area.
    """
    # At equator (lat = 0), meridional curvature radius:
    # M0 = a * (1 - e^2)
    m0 = WGS84_SEMI_MAJOR * (1.0 - WGS84_E2)
    # Side length 100m for 1 hectare square
    dlat_rad = 100.0 / m0
    dlat_deg = math.degrees(dlat_rad)
    dlon_rad = 100.0 / WGS84_SEMI_MAJOR
    dlon_deg = math.degrees(dlon_rad)

    equator_box = [
        (0.0, 0.0),
        (0.0, dlon_deg),
        (dlat_deg, dlon_deg),
        (dlat_deg, 0.0),
        (0.0, 0.0),
    ]

    calc_m2 = calculate_wgs84_geodesic_area_sq_meters(equator_box)
    calc_ha = calculate_polygon_area_hectares(equator_box)

    # Analytical ellipsoidal area:
    # A = 0.5 * Rq^2 * dlon * (q(dlat) - q(0)) / (qp / 2)
    true_ellipsoidal_area = (
        0.5 * (WGS84_AUTHALIC_RADIUS ** 2) * dlon_rad *
        (_authalic_q(dlat_rad) - _authalic_q(0.0)) / (_QP / 2.0)
    )

    diff = abs(calc_m2 - true_ellipsoidal_area)
    rel_error = diff / true_ellipsoidal_area

    assert diff < 1e-4, f"Difference {diff} m^2 exceeds 0.0001 m^2 threshold"
    assert rel_error < 1e-8, f"Relative error {rel_error} exceeds 1e-8"
    assert math.isclose(calc_ha, 1.0, abs_tol=1e-3), f"Calculated hectares {calc_ha} must round to 1.0 ha"


def test_benchmark_1_acre_hyderabad_accuracy():
    """Benchmark 2: 1 acre (4,046.8564224 m^2) square at Hyderabad (17.385° N).
    Compares computed geodesic area with analytical ellipsoidal surface area.
    """
    lat0 = 17.3850
    lon0 = 78.4867
    lat0_rad = math.radians(lat0)

    # Ellipsoidal radii of curvature at Hyderabad:
    sin_lat = math.sin(lat0_rad)
    denom = 1.0 - WGS84_E2 * sin_lat * sin_lat
    m_curv = (WGS84_SEMI_MAJOR * (1.0 - WGS84_E2)) / (denom ** 1.5)
    n_curv = WGS84_SEMI_MAJOR / math.sqrt(denom)
    r_parallel = n_curv * math.cos(lat0_rad)

    target_m2 = M2_PER_ACRE  # 4046.8564224 m^2
    side_m = math.sqrt(target_m2)

    dlat_rad = side_m / m_curv
    dlat_deg = math.degrees(dlat_rad)
    dlon_rad = side_m / r_parallel
    dlon_deg = math.degrees(dlon_rad)

    hyd_square = [
        (lat0, lon0),
        (lat0, lon0 + dlon_deg),
        (lat0 + dlat_deg, lon0 + dlon_deg),
        (lat0 + dlat_deg, lon0),
        (lat0, lon0),
    ]

    calc_m2 = calculate_wgs84_geodesic_area_sq_meters(hyd_square)
    calc_acres = calculate_farm_area_acres(hyd_square)

    # Analytical ellipsoidal area:
    true_ellipsoidal_area = (
        0.5 * (WGS84_AUTHALIC_RADIUS ** 2) * dlon_rad *
        (_authalic_q(lat0_rad + dlat_rad) - _authalic_q(lat0_rad)) / (_QP / 2.0)
    )

    diff = abs(calc_m2 - true_ellipsoidal_area)
    rel_error = diff / true_ellipsoidal_area

    assert diff < 1e-4, f"Difference {diff} m^2 exceeds 0.0001 m^2 threshold"
    assert rel_error < 1e-8, f"Relative error {rel_error} exceeds 1e-8"
    assert math.isclose(calc_acres, 1.0, rel_tol=1e-4), f"Calculated acres {calc_acres} must match 1.0000"


def test_benchmark_complex_irregular_farm_parcel_invariance():
    """Benchmark 3: Complex irregular 8-vertex farm parcel in Telangana.
    Tests area calculation invariance under vertex orientation reversal (CW vs CCW)
    and global longitude translation.
    """
    irregular_parcel = [
        (17.3850, 78.4867),
        (17.3875, 78.4880),
        (17.3890, 78.4905),
        (17.3880, 78.4930),
        (17.3860, 78.4940),
        (17.3840, 78.4925),
        (17.3830, 78.4895),
        (17.3835, 78.4870),
        (17.3850, 78.4867),
    ]

    area_ccw = calculate_wgs84_geodesic_area_sq_meters(irregular_parcel)
    assert area_ccw > 0.0

    # Reversed order (CW orientation)
    reversed_parcel = list(reversed(irregular_parcel))
    area_cw = calculate_wgs84_geodesic_area_sq_meters(reversed_parcel)

    # Must be identical within floating point precision
    assert math.isclose(area_ccw, area_cw, rel_tol=1e-12), (
        f"CW vs CCW areas differ: {area_cw} vs {area_ccw}"
    )

    # Longitude translation by 1 degree (same latitude profile)
    shifted_parcel = [(pt[0], pt[1] + 1.0) for pt in irregular_parcel]
    area_shifted = calculate_wgs84_geodesic_area_sq_meters(shifted_parcel)
    assert math.isclose(area_ccw, area_shifted, rel_tol=1e-10), (
        f"Area changed under pure longitude shift: {area_shifted} vs {area_ccw}"
    )


# ==============================================================================
# SECTION 5: BOUNDARY VERSIONING & AUDIT HISTORY API LIFECYCLE
# ==============================================================================

def test_farm_boundary_versioning_and_history_lifecycle(stress_client, stress_farmer_id):
    """Full empirical lifecycle test of boundary versioning:
    1. POST /api/v1/farms -> Verify version 1, vertices created in DB.
    2. GET /api/v1/farms/{id} -> Verify retrieval of v1 parcel.
    3. PATCH /api/v1/farms/{id} with new boundary coordinates ->
       Verify version 2, new area, new vertices created.
    4. GET /api/v1/farms/{id}/history ->
       Verify version 1 preserved in boundary_history with exact original area & GeoJSON.
    5. PATCH metadata only (farm_name, crop_type) ->
       Verify version remains 2, no extra history entry added.
    6. Direct DB verification ->
       Verify boundary_vertices table has both v1 and v2 records tagged with boundary_version.
    """
    client, session_factory = stress_client

    # 1. Create farm with initial 4 vertices
    v1_coords = [
        {"latitude": 17.3850, "longitude": 78.4867, "sequence": 1},
        {"latitude": 17.3870, "longitude": 78.4867, "sequence": 2},
        {"latitude": 17.3870, "longitude": 78.4890, "sequence": 3},
        {"latitude": 17.3850, "longitude": 78.4890, "sequence": 4},
    ]

    res_v1 = client.post("/api/v1/farms", json={
        "farmer_id": stress_farmer_id,
        "farm_name": "Empirical Parcel Alpha",
        "crop_type": "Paddy",
        "season": "Kharif 2026",
        "district": "Rangareddy",
        "state": "Telangana",
        "vertices": v1_coords,
    })
    assert res_v1.status_code == 201, f"Failed to create farm: {res_v1.text}"
    v1_data = res_v1.json()

    farm_id = v1_data["id"]
    assert v1_data["boundary_version"] == 1
    v1_area_m2 = v1_data["area_sq_meters"]
    assert v1_area_m2 > 0.0
    assert len(v1_data["vertices"]) == 4

    # 2. Verify GET /api/v1/farms/{farm_id} returns v1
    res_get_v1 = client.get(f"/api/v1/farms/{farm_id}")
    assert res_get_v1.status_code == 200
    assert res_get_v1.json()["boundary_version"] == 1
    assert len(res_get_v1.json()["vertices"]) == 4

    # Initial history must be empty
    res_hist_initial = client.get(f"/api/v1/farms/{farm_id}/history")
    assert res_hist_initial.status_code == 200
    assert len(res_hist_initial.json()) == 0

    # 3. PATCH boundary coordinates with expanded 5-vertex polygon
    v2_coords = [
        {"latitude": 17.3850, "longitude": 78.4867, "sequence": 1},
        {"latitude": 17.3880, "longitude": 78.4867, "sequence": 2},  # expanded north
        {"latitude": 17.3880, "longitude": 78.4900, "sequence": 3},  # expanded east
        {"latitude": 17.3860, "longitude": 78.4900, "sequence": 4},
        {"latitude": 17.3850, "longitude": 78.4880, "sequence": 5},
    ]

    res_patch = client.patch(f"/api/v1/farms/{farm_id}", json={
        "vertices": v2_coords,
        "crop_type": "Basmati Paddy",
    })
    assert res_patch.status_code == 200, f"PATCH failed: {res_patch.text}"
    v2_data = res_patch.json()

    # Verify version incremented to 2
    assert v2_data["boundary_version"] == 2
    assert v2_data["crop_type"] == "Basmati Paddy"
    assert v2_data["area_sq_meters"] > v1_area_m2  # expanded area
    assert len(v2_data["vertices"]) == 5
    assert [v["vertex_sequence"] for v in v2_data["vertices"]] == [1, 2, 3, 4, 5]

    # 4. GET /api/v1/farms/{farm_id}/history -> verify v1 archived
    res_hist = client.get(f"/api/v1/farms/{farm_id}/history")
    assert res_hist.status_code == 200
    histories = res_hist.json()
    assert len(histories) == 1, "Expected exactly 1 historical version in boundary_history"

    h1 = histories[0]
    assert h1["farm_id"] == farm_id
    assert h1["boundary_version"] == 1
    assert math.isclose(h1["area_sq_meters"], v1_area_m2, rel_tol=1e-5)
    assert h1["boundary_geojson"] == v1_data["boundary_geojson"]
    assert h1["superseded_at"] is not None

    # 5. PATCH metadata only (farm_name, season)
    res_patch_meta = client.patch(f"/api/v1/farms/{farm_id}", json={
        "farm_name": "Empirical Parcel Alpha Updated",
        "season": "Rabi 2026-27",
    })
    assert res_patch_meta.status_code == 200
    meta_data = res_patch_meta.json()
    assert meta_data["farm_name"] == "Empirical Parcel Alpha Updated"
    assert meta_data["season"] == "Rabi 2026-27"
    assert meta_data["boundary_version"] == 2, "Boundary version must NOT increment on metadata-only update"

    # History count must still be 1
    res_hist_meta = client.get(f"/api/v1/farms/{farm_id}/history")
    assert len(res_hist_meta.json()) == 1

    # 6. Direct DB inspection using session_factory
    db = session_factory()
    try:
        # Check all vertices in DB for this farm
        all_vertices = db.query(BoundaryVertex).filter(BoundaryVertex.farm_id == farm_id).all()
        assert len(all_vertices) == 9  # 4 from v1 + 5 from v2

        v1_db_vertices = [v for v in all_vertices if v.boundary_version == 1]
        v2_db_vertices = [v for v in all_vertices if v.boundary_version == 2]

        assert len(v1_db_vertices) == 4
        assert len(v2_db_vertices) == 5

        # Check boundary history in DB
        db_history = db.query(BoundaryHistory).filter(BoundaryHistory.farm_id == farm_id).all()
        assert len(db_history) == 1
        assert db_history[0].boundary_version == 1
    finally:
        db.close()
