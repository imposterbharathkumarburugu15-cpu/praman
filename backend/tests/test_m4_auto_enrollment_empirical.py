import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.core.database import Base, get_db
from crypto.ecdsa_p256 import generate_keypair, public_key_to_pem, sign
from crypto.rfc8785 import canonicalize


@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "m4_enrollment_test.db")
    engine = create_engine(f"sqlite:///{test_db}", connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    test_c = TestClient(app)
    yield test_c
    app.dependency_overrides.clear()


def test_android_auto_enrollment_sequence_empirical(client):
    """
    Empirically verifies the exact auto-enrollment sequence implemented in
    EvidenceSyncEngine.java:ensureDeviceEnrolled(deviceId).
    """
    device_id = "android_hw_device_" + str(uuid.uuid4())[:8]
    farmer_id = "farmer_" + device_id
    phone = "+919848012345"
    full_name = "PRAMAN Farmer"
    lang = "te"

    # Step 1: Check device registration (GET /api/v1/devices/{id}) -> expected 404
    r_check = client.get(f"/api/v1/devices/{device_id}")
    assert r_check.status_code == 404, "Unregistered device must return 404 on initial probe"

    # Step 2: Generate valid NIST P-256 keypair mimicking AndroidKeystoreBridge
    priv_key, pub_key = generate_keypair()
    pub_pem = public_key_to_pem(pub_key).strip()
    assert "BEGIN PUBLIC KEY" in pub_pem

    # Step 3: Register Farmer via POST /api/v1/farmers with Java EvidenceSyncEngine payload
    f_payload = {
        "id": farmer_id,
        "farmer_id": farmer_id,
        "full_name": full_name,
        "phone_number": phone,
        "language_pref": lang,
    }
    r_farmer = client.post("/api/v1/farmers", json=f_payload)
    assert r_farmer.status_code in (201, 200), f"Farmer registration failed: {r_farmer.text}"
    farmer_data = r_farmer.json()
    actual_farmer_id = farmer_data.get("id") or farmer_data.get("farmer", {}).get("id")
    assert actual_farmer_id is not None

    # Step 4: Test 409 Conflict handling and login fallback
    r_conflict = client.post("/api/v1/farmers", json=f_payload)
    assert r_conflict.status_code == 409, "Duplicate phone must trigger 409 Conflict"

    # Fallback to login
    r_login = client.post("/api/v1/farmers/login", json={"phone_number": phone})
    assert r_login.status_code == 200
    login_id = r_login.json().get("id") or r_login.json().get("farmer", {}).get("id")
    assert login_id == actual_farmer_id

    # Step 5: Register Device via POST /api/v1/devices/register with Java payload
    d_payload = {
        "device_id": device_id,
        "id": device_id,
        "farmer_id": actual_farmer_id,
        "public_key_pem": pub_pem,
    }
    r_dev = client.post("/api/v1/devices/register", json=d_payload)
    assert r_dev.status_code in (201, 200), f"Device enrollment failed: {r_dev.text}"
    dev_data = r_dev.json()
    assert dev_data["id"] == device_id
    assert dev_data["status"] == "ACTIVE"

    # Step 6: Verify device is now queryable via GET /api/v1/devices/{device_id}
    r_verify = client.get(f"/api/v1/devices/{device_id}")
    assert r_verify.status_code == 200
    assert r_verify.json()["id"] == device_id
    assert r_verify.json()["status"] == "ACTIVE"


def test_unregistered_device_403_reproduction(client):
    """
    Confirms that uploading evidence from an unregistered device unconditionally triggers HTTP 403 Forbidden.
    """
    fake_device_id = "unregistered_device_999"
    priv_key, pub_key = generate_keypair()

    import hashlib
    raw_bytes = b"fake image bytes for testing"
    img_hash = hashlib.sha256(raw_bytes).hexdigest().lower()

    envelope = {
        "evidence_id": str(uuid.uuid4()),
        "device_id": fake_device_id,
        "capture_timestamp_utc": "2026-11-10T04:50:00Z",
        "sequence_number": 1,
        "image_hash": img_hash,
        "farmer_id": str(uuid.uuid4()),
        "farm_id": str(uuid.uuid4()),
        "gps_latitude": 17.385044,
        "gps_longitude": 78.486671,
        "gps_accuracy": 5.0,
    }
    import json
    import base64
    import io
    env_bytes = canonicalize(envelope)
    sig_der = sign(priv_key, env_bytes)
    sig_b64 = base64.b64encode(sig_der).decode("ascii")

    files = {
        "envelope": (None, json.dumps(envelope), "application/json"),
        "signature": (None, sig_b64, "text/plain"),
        "file": ("test.jpg", io.BytesIO(raw_bytes), "image/jpeg"),
    }

    resp = client.post("/api/v1/evidence/ingest", files=files)
    print("Ingest response:", resp.status_code, resp.json())
    assert resp.status_code == 403, f"Expected 403 Forbidden for unregistered device, got {resp.status_code}: {resp.text}"
    assert "Unregistered device" in resp.json()["detail"]


def test_enrolled_device_upload_avoids_403(client):
    """
    Empirically verifies that following auto-enrollment, evidence upload succeeds
    and does NOT receive HTTP 403 Forbidden.
    """
    import hashlib
    import json
    import base64
    import io

    # 1. Device keypair
    priv_key, pub_key = generate_keypair()
    pub_pem = public_key_to_pem(pub_key).strip()

    device_id = "device_test_auto_enrolled_" + str(uuid.uuid4())[:8]
    farmer_id = "farmer_" + device_id
    phone = "+919848099887"

    # 2. Farmer auto-enrollment
    rf = client.post("/api/v1/farmers", json={
        "id": farmer_id,
        "farmer_id": farmer_id,
        "full_name": "Verified Auto Farmer",
        "phone_number": phone,
        "language_pref": "te",
    })
    assert rf.status_code == 201

    # 3. Device auto-enrollment
    rd = client.post("/api/v1/devices/register", json={
        "device_id": device_id,
        "id": device_id,
        "farmer_id": farmer_id,
        "public_key_pem": pub_pem,
    })
    assert rd.status_code == 201

    # 4. Upload evidence with registered device
    raw_bytes = b"sample camera image bytes captured on android"
    img_hash = hashlib.sha256(raw_bytes).hexdigest().lower()

    envelope = {
        "evidence_id": str(uuid.uuid4()),
        "device_id": device_id,
        "capture_timestamp_utc": "2026-11-10T04:55:00Z",
        "sequence_number": 1,
        "image_hash": img_hash,
        "farmer_id": farmer_id,
        "farm_id": str(uuid.uuid4()),
        "gps_latitude": 17.385044,
        "gps_longitude": 78.486671,
        "gps_accuracy": 4.5,
    }

    env_bytes = canonicalize(envelope)
    sig_der = sign(priv_key, env_bytes)
    sig_b64 = base64.b64encode(sig_der).decode("ascii")

    files = {
        "envelope": (None, json.dumps(envelope), "application/json"),
        "signature": (None, sig_b64, "text/plain"),
        "file": ("test.jpg", io.BytesIO(raw_bytes), "image/jpeg"),
    }

    resp = client.post("/api/v1/evidence/ingest", files=files)
    assert resp.status_code in (200, 201), f"Expected successful ingest, got {resp.status_code}: {resp.text}"
    receipt = resp.json()
    assert receipt["evidence_id"] == envelope["evidence_id"]
    assert receipt["status"] == "DURABLY_ACKED"
    assert "classification" in receipt
