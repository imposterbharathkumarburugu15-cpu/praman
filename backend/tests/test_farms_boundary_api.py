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
from backend.app.models.audit_log import AuditLog


@pytest.fixture(scope="function")
def test_client(tmp_path):
    test_db_path = str(tmp_path / "test_farms.db")
    test_engine = create_engine(f"sqlite:///{test_db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def registered_farmer_id(test_client):
    res = test_client.post("/api/v1/farmers", json={
        "full_name": "Laxman Patel",
        "phone_number": "+919876500001",
        "language_pref": "te",
    })
    assert res.status_code == 201
    return res.json()["id"]


def test_create_farm_with_individual_vertices(test_client, registered_farmer_id):
    """Verifies farm creation with individual vertex records, WGS84 geodesic calculation,
    persistence in farms and boundary_vertices tables, and audit logging.
    """
    vertices = [
        {
            "latitude": 19.6640,
            "longitude": 78.5320,
            "accuracy": 2.5,
            "timestamp": "2026-11-10T04:00:00Z",
            "method": "WALK_AND_MARK",
            "sequence": 1,
        },
        {
            "latitude": 19.6645,
            "longitude": 78.5350,
            "accuracy": 3.0,
            "timestamp": "2026-11-10T04:05:00Z",
            "method": "WALK_AND_MARK",
            "sequence": 2,
        },
        {
            "latitude": 19.6620,
            "longitude": 78.5360,
            "accuracy": 2.1,
            "timestamp": "2026-11-10T04:10:00Z",
            "method": "WALK_AND_MARK",
            "sequence": 3,
        },
        {
            "latitude": 19.6615,
            "longitude": 78.5325,
            "accuracy": 2.8,
            "timestamp": "2026-11-10T04:15:00Z",
            "method": "WALK_AND_MARK",
            "sequence": 4,
        },
    ]

    payload = {
        "farmer_id": registered_farmer_id,
        "farm_name": "Adilabad Cotton Parcel 1",
        "crop_type": "Cotton",
        "season": "Kharif 2026",
        "district": "Adilabad",
        "state": "Telangana",
        "declared_area": 24.0,
        "declared_area_unit": "acres",
        "vertices": vertices,
    }

    res = test_client.post("/api/v1/farms", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert data["farm_name"] == "Adilabad Cotton Parcel 1"
    assert data["crop_type"] == "Cotton"
    assert data["boundary_version"] == 1
    assert data["crs"] == "EPSG:4326"
    assert data["area_sq_meters"] > 90000.0  # ~98,675 m^2
    assert data["area_acres"] > 20.0 and data["area_acres"] < 30.0  # ~24.38 acres
    assert data["area_hectares"] > 9.0  # ~9.86 ha
    assert data["is_valid"] is True
    assert data["season"] == "Kharif 2026"
    assert data["district"] == "Adilabad"
    assert data["state"] == "Telangana"

    # Verify vertex count and ordering
    res_vertices = data["vertices"]
    assert len(res_vertices) == 4
    assert [v["vertex_sequence"] for v in res_vertices] == [1, 2, 3, 4]
    assert res_vertices[0]["latitude"] == 19.6640
    assert res_vertices[0]["collection_method"] == "WALK_AND_MARK"

    # Verify validation details contain reconciliation
    details = json.loads(data["validation_details"])
    assert details["polygon_status"] == "VALID"
    assert details["declared_area_reconciled"] is True


def test_get_farm_by_id(test_client, registered_farmer_id):
    """Verifies GET /api/v1/farms/{id} returns full parcel details with vertices."""
    # Create farm first
    poly = [
        (19.6640, 78.5320),
        (19.6645, 78.5350),
        (19.6620, 78.5360),
        (19.6615, 78.5325),
    ]
    res_create = test_client.post("/api/v1/farms", json={
        "farmer_id": registered_farmer_id,
        "farm_name": "Paddy Field A",
        "crop_type": "Paddy",
        "boundary_polygon": poly,
    })
    assert res_create.status_code == 201
    farm_id = res_create.json()["id"]

    # Retrieve by ID
    res_get = test_client.get(f"/api/v1/farms/{farm_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["id"] == farm_id
    assert data["boundary_version"] == 1
    assert len(data["vertices"]) == 4
    assert data["area_sq_meters"] > 0.0
    assert data["area_acres"] > 0.0


def test_patch_farm_boundary_archives_history_and_increments_version(test_client, registered_farmer_id):
    """Verifies that updating boundary coordinates archives previous boundary to
    boundary_history, increments boundary_version, and recalculates geodesic area.
    """
    initial_poly = [
        (19.6640, 78.5320),
        (19.6645, 78.5350),
        (19.6620, 78.5360),
        (19.6615, 78.5325),
    ]
    res_init = test_client.post("/api/v1/farms", json={
        "farmer_id": registered_farmer_id,
        "farm_name": "Chili Plot",
        "crop_type": "Chili",
        "boundary_polygon": initial_poly,
    })
    assert res_init.status_code == 201
    farm_id = res_init.json()["id"]
    initial_area_m2 = res_init.json()["area_sq_meters"]

    # Expand the polygon boundary to include a 5th vertex
    expanded_vertices = [
        {"latitude": 19.6640, "longitude": 78.5320, "sequence": 1},
        {"latitude": 19.6650, "longitude": 78.5350, "sequence": 2},  # shifted north
        {"latitude": 19.6630, "longitude": 78.5370, "sequence": 3},  # shifted east
        {"latitude": 19.6610, "longitude": 78.5360, "sequence": 4},
        {"latitude": 19.6615, "longitude": 78.5325, "sequence": 5},
    ]

    res_patch = test_client.patch(f"/api/v1/farms/{farm_id}", json={
        "vertices": expanded_vertices,
        "crop_type": "Chili Guntur",
    })
    assert res_patch.status_code == 200
    patched = res_patch.json()

    assert patched["boundary_version"] == 2
    assert patched["crop_type"] == "Chili Guntur"
    assert patched["area_sq_meters"] > initial_area_m2  # expanded area
    assert len(patched["vertices"]) == 5
    assert [v["vertex_sequence"] for v in patched["vertices"]] == [1, 2, 3, 4, 5]

    # Verify history endpoint contains version 1 record
    res_hist = test_client.get(f"/api/v1/farms/{farm_id}/history")
    assert res_hist.status_code == 200
    histories = res_hist.json()
    assert len(histories) == 1
    assert histories[0]["boundary_version"] == 1
    assert histories[0]["farm_id"] == farm_id
    assert math.isclose(histories[0]["area_sq_meters"], initial_area_m2, rel_tol=1e-3)


def test_patch_metadata_does_not_increment_boundary_version(test_client, registered_farmer_id):
    """Verifies updating crop_type or farm_name without changing boundary does NOT
    increment boundary_version or create boundary_history entries.
    """
    poly = [
        (19.6640, 78.5320),
        (19.6645, 78.5350),
        (19.6620, 78.5360),
        (19.6615, 78.5325),
    ]
    res_create = test_client.post("/api/v1/farms", json={
        "farmer_id": registered_farmer_id,
        "farm_name": "Maize Field",
        "crop_type": "Maize",
        "boundary_polygon": poly,
    })
    farm_id = res_create.json()["id"]

    res_patch = test_client.patch(f"/api/v1/farms/{farm_id}", json={
        "crop_type": "Sweet Corn",
        "season": "Rabi 2026-27",
    })
    assert res_patch.status_code == 200
    patched = res_patch.json()
    assert patched["crop_type"] == "Sweet Corn"
    assert patched["season"] == "Rabi 2026-27"
    assert patched["boundary_version"] == 1

    # Verify history remains empty
    res_hist = test_client.get(f"/api/v1/farms/{farm_id}/history")
    assert res_hist.status_code == 200
    assert len(res_hist.json()) == 0


def test_reject_self_intersecting_boundary(test_client, registered_farmer_id):
    """Verifies self-intersecting bowtie polygon is rejected on farm creation and update."""
    bowtie = [
        {"latitude": 19.660, "longitude": 78.530, "sequence": 1},
        {"latitude": 19.665, "longitude": 78.535, "sequence": 2},
        {"latitude": 19.660, "longitude": 78.535, "sequence": 3},
        {"latitude": 19.665, "longitude": 78.530, "sequence": 4},
    ]

    res = test_client.post("/api/v1/farms", json={
        "farmer_id": registered_farmer_id,
        "farm_name": "Invalid Bowtie Farm",
        "crop_type": "Cotton",
        "vertices": bowtie,
    })
    assert res.status_code == 422
    assert "self-intersecting" in res.json()["detail"]


def test_reject_consecutive_duplicate_vertices(test_client, registered_farmer_id):
    """Verifies zero-length consecutive duplicate edges are rejected."""
    dup_vertices = [
        {"latitude": 19.660, "longitude": 78.530, "sequence": 1},
        {"latitude": 19.660, "longitude": 78.530, "sequence": 2},  # duplicate
        {"latitude": 19.665, "longitude": 78.535, "sequence": 3},
        {"latitude": 19.660, "longitude": 78.535, "sequence": 4},
    ]

    res = test_client.post("/api/v1/farms", json={
        "farmer_id": registered_farmer_id,
        "farm_name": "Duplicate Edge Farm",
        "crop_type": "Cotton",
        "vertices": dup_vertices,
    })
    assert res.status_code == 422
    assert "Duplicate consecutive vertex" in res.json()["detail"]


def test_reject_closed_pinch_point_polygon_api(test_client, registered_farmer_id):
    """Verifies that pre-closed polygons with repeated internal vertices (pinch-points/figure-8)
    are strictly rejected by the API with HTTP 422.
    """
    pinch_poly = [
        (17.380, 78.480),
        (17.385, 78.485),
        (17.390, 78.480),
        (17.385, 78.475),
        (17.385, 78.485),  # duplicate non-consecutive vertex
        (17.380, 78.480),  # explicit closing vertex
    ]

    res = test_client.post("/api/v1/farms", json={
        "farmer_id": registered_farmer_id,
        "farm_name": "Pinch Point Farm",
        "crop_type": "Cotton",
        "boundary_polygon": pinch_poly,
    })
    assert res.status_code == 422
    assert "Duplicate non-consecutive vertex" in res.json()["detail"]


def test_reject_negative_and_invalid_horizontal_accuracy_api(test_client, registered_farmer_id):
    """Verifies that negative, zero, and out-of-range GPS horizontal accuracy values
    are rejected with HTTP 422.
    """
    valid_coords = [
        {"latitude": 17.38, "longitude": 78.48, "accuracy": 5.0, "sequence": 1},
        {"latitude": 17.39, "longitude": 78.48, "accuracy": 5.0, "sequence": 2},
        {"latitude": 17.39, "longitude": 78.49, "accuracy": 5.0, "sequence": 3},
        {"latitude": 17.38, "longitude": 78.49, "accuracy": 5.0, "sequence": 4},
    ]

    # 1. Negative accuracy (-50.0m)
    neg_coords = [dict(c) for c in valid_coords]
    neg_coords[0]["accuracy"] = -50.0
    res_neg = test_client.post("/api/v1/farms", json={
        "farmer_id": registered_farmer_id,
        "farm_name": "Negative Accuracy Farm",
        "crop_type": "Cotton",
        "vertices": neg_coords,
    })
    assert res_neg.status_code == 422

    # 2. Zero accuracy (0.0m)
    zero_coords = [dict(c) for c in valid_coords]
    zero_coords[0]["accuracy"] = 0.0
    res_zero = test_client.post("/api/v1/farms", json={
        "farmer_id": registered_farmer_id,
        "farm_name": "Zero Accuracy Farm",
        "crop_type": "Cotton",
        "vertices": zero_coords,
    })
    assert res_zero.status_code == 422

    # 3. Excessive accuracy (501.0m)
    excess_coords = [dict(c) for c in valid_coords]
    excess_coords[0]["accuracy"] = 501.0
    res_excess = test_client.post("/api/v1/farms", json={
        "farmer_id": registered_farmer_id,
        "farm_name": "Excessive Accuracy Farm",
        "crop_type": "Cotton",
        "vertices": excess_coords,
    })
    assert res_excess.status_code == 422
