import os
import json
import uuid
import base64
import hashlib
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.storage.content_storage import ContentAddressableStorage
from backend.app.services.spatial import validate_farm_polygon, calculate_polygon_area_hectares
from crypto.ecdsa_p256 import generate_keypair, sign, public_key_to_pem
from crypto.rfc8785 import canonicalize


# In-memory SQLite database fixture for isolated testing
@pytest.fixture(scope="function")
def test_client(tmp_path):
    test_db_path = str(tmp_path / "test.db")
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


def test_health_endpoint(test_client):
    res = test_client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"


def test_farmer_registration_and_validation(test_client):
    # Valid registration
    farmer_data = {
        "full_name": "Kishan Rao",
        "phone_number": "+919849012345",
        "language_pref": "te",
    }
    res = test_client.post("/api/v1/farmers", json=farmer_data)
    assert res.status_code == 201
    created = res.json()
    assert created["full_name"] == "Kishan Rao"
    assert created["language_pref"] == "te"
    farmer_id = created["id"]

    # Duplicate phone number rejected
    res_dup = test_client.post("/api/v1/farmers", json=farmer_data)
    assert res_dup.status_code == 409

    # Invalid phone format rejected
    invalid_farmer = {
        "full_name": "Bad Phone",
        "phone_number": "9849012345",  # missing +91
        "language_pref": "en",
    }
    res_bad = test_client.post("/api/v1/farmers", json=invalid_farmer)
    assert res_bad.status_code == 422


def test_device_registration_and_status(test_client):
    # Register farmer first
    res_f = test_client.post("/api/v1/farmers", json={
        "full_name": "Dev Farmer",
        "phone_number": "+919876543210",
        "language_pref": "hi",
    })
    farmer_id = res_f.json()["id"]

    priv_key, pub_key = generate_keypair()
    pub_pem = public_key_to_pem(pub_key)
    device_id = str(uuid.uuid4())

    device_data = {
        "device_id": device_id,
        "farmer_id": farmer_id,
        "public_key_pem": pub_pem,
    }
    res_d = test_client.post("/api/v1/devices/register", json=device_data)
    assert res_d.status_code in (200, 201)
    dev = res_d.json()
    assert dev["id"] == device_id
    assert dev["status"] == "ACTIVE"
    assert dev["last_sequence_number"] == 0

    # Idempotent re-registration with same key
    res_d2 = test_client.post("/api/v1/devices/register", json=device_data)
    assert res_d2.status_code == 200

    # Re-registration with different key -> 409 Conflict
    _, pub_key2 = generate_keypair()
    res_d3 = test_client.post("/api/v1/devices/register", json={
        "device_id": device_id,
        "farmer_id": farmer_id,
        "public_key_pem": public_key_to_pem(pub_key2),
    })
    assert res_d3.status_code == 409

    # Status update to SUSPENDED
    res_patch = test_client.patch(f"/api/v1/devices/{device_id}/status", json={"status": "SUSPENDED"})
    assert res_patch.status_code == 200
    assert res_patch.json()["status"] == "SUSPENDED"


def test_farm_creation_and_spatial_validation(test_client):
    res_f = test_client.post("/api/v1/farmers", json={
        "full_name": "Farm Farmer",
        "phone_number": "+919123456789",
        "language_pref": "en",
    })
    farmer_id = res_f.json()["id"]

    # Valid polygon GeoJSON
    valid_geojson = {
        "type": "Polygon",
        "coordinates": [[
            [78.4866, 17.3850],
            [78.4870, 17.3850],
            [78.4870, 17.3855],
            [78.4866, 17.3855],
            [78.4866, 17.3850],
        ]]
    }
    farm_data = {
        "farmer_id": farmer_id,
        "farm_name": "Telangana Cotton Field",
        "crop_type": "Cotton",
        "boundary_geojson": json.dumps(valid_geojson),
    }
    res_farm = test_client.post("/api/v1/farms", json=farm_data)
    assert res_farm.status_code == 201
    created_farm = res_farm.json()
    assert created_farm["crop_type"] == "Cotton"
    assert created_farm["area_hectares"] > 0.0

    # Self-intersecting polygon rejected
    bowtie_geojson = {
        "type": "Polygon",
        "coordinates": [[
            [78.0, 17.0],
            [78.1, 17.1],
            [78.0, 17.1],
            [78.1, 17.0],
            [78.0, 17.0],
        ]]
    }
    farm_bad = {
        "farmer_id": farmer_id,
        "farm_name": "Bad Field",
        "crop_type": "Chili",
        "boundary_geojson": json.dumps(bowtie_geojson),
    }
    res_bad = test_client.post("/api/v1/farms", json=farm_bad)
    assert res_bad.status_code == 422


def test_evidence_ingest_e2e_lifecycle(test_client, tmp_path):
    # Setup farmer, device, farm
    res_f = test_client.post("/api/v1/farmers", json={
        "full_name": "Evidence Farmer",
        "phone_number": "+919765432109",
        "language_pref": "te",
    })
    farmer_id = res_f.json()["id"]

    priv_key, pub_key = generate_keypair()
    pub_pem = public_key_to_pem(pub_key)
    device_id = str(uuid.uuid4())
    test_client.post("/api/v1/devices/register", json={
        "device_id": device_id,
        "farmer_id": farmer_id,
        "public_key_pem": pub_pem,
    })

    farm_res = test_client.post("/api/v1/farms", json={
        "farmer_id": farmer_id,
        "farm_name": "Harvest Plot",
        "crop_type": "Paddy",
        "boundary_geojson": json.dumps({
            "type": "Polygon",
            "coordinates": [[[78.48, 17.38], [78.49, 17.38], [78.49, 17.39], [78.48, 17.39], [78.48, 17.38]]]
        }),
    })
    farm_id = farm_res.json()["id"]

    # Create dummy sharp image
    image_bytes = b"EXACT_IMAGE_BINARY_DATA_TEST_12345"
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    evidence_id = str(uuid.uuid4())

    envelope = {
        "device_id": device_id,
        "evidence_id": evidence_id,
        "farm_id": farm_id,
        "image_hash": image_hash,
        "lifecycle_stage": "HARVEST",
        "metadata": {
            "capture_source": "CAMERA",
            "capture_timestamp": datetime.now(timezone.utc).isoformat(),
            "gps_accuracy": 3.2,
            "latitude": 17.385,
            "longitude": 78.486,
        },
        "schema_version": "1.0",
        "sequence_number": 1,
    }

    canonical_bytes = canonicalize(envelope)
    der_sig = sign(priv_key, canonical_bytes)
    sig_b64 = base64.b64encode(der_sig).decode("utf-8")

    # Ingest evidence via multipart
    files = {
        "image": ("capture.jpg", image_bytes, "image/jpeg"),
    }
    data = {
        "envelope": json.dumps(envelope),
        "signature": sig_b64,
    }
    res_ingest = test_client.post("/api/v1/evidence/ingest", data=data, files=files)
    assert res_ingest.status_code == 201
    receipt = res_ingest.json()
    assert receipt["status"] == "DURABLY_ACKED"
    assert receipt["sequence_number"] == 1
    assert receipt["evidence_id"] == evidence_id

    # Verify identical retry returns HTTP 200 OK (idempotency)
    res_retry = test_client.post("/api/v1/evidence/ingest", data=data, files=files)
    assert res_retry.status_code == 200
    assert res_retry.json()["status"] == "DURABLY_ACKED"

    # Verify sequence gap rejection (submitting sequence 3 when next is 2) -> 409 Conflict
    envelope_gap = dict(envelope)
    envelope_gap["evidence_id"] = str(uuid.uuid4())
    envelope_gap["sequence_number"] = 3
    gap_canon = canonicalize(envelope_gap)
    gap_sig = base64.b64encode(sign(priv_key, gap_canon)).decode("utf-8")
    res_gap = test_client.post("/api/v1/evidence/ingest", data={
        "envelope": json.dumps(envelope_gap),
        "signature": gap_sig,
    }, files=files)
    assert res_gap.status_code == 409


def test_audit_logs_recorded(test_client):
    res = test_client.get("/api/v1/audit/logs")
    assert res.status_code == 200
    logs = res.json()
    assert isinstance(logs, list)

