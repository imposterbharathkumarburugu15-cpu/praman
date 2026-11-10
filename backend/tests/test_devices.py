import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.core.database import Base, get_db
from crypto.ecdsa_p256 import generate_keypair, public_key_to_pem


@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "devices_test.db")
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


def test_device_lifecycle_and_idempotency(client):
    # 1. Register farmer
    rf = client.post("/api/v1/farmers", json={
        "full_name": "Device Test Farmer",
        "phone_number": "+919876543211",
        "language_pref": "en",
    })
    farmer_id = rf.json()["id"]

    # 2. Register device with valid P-256 key
    _, pub_key = generate_keypair()
    pub_pem = public_key_to_pem(pub_key)
    dev_id = str(uuid.uuid4())

    payload = {
        "device_id": dev_id,
        "farmer_id": farmer_id,
        "public_key_pem": pub_pem,
    }
    r_dev = client.post("/api/v1/devices/register", json=payload)
    assert r_dev.status_code == 201
    data = r_dev.json()
    assert data["id"] == dev_id
    assert data["status"] == "ACTIVE"
    assert data["last_sequence_number"] == 0

    # 3. Idempotent re-registration with same key returns 200 OK
    r_idem = client.post("/api/v1/devices/register", json=payload)
    assert r_idem.status_code == 200
    assert r_idem.json()["id"] == dev_id

    # 4. Re-registration with altered key returns 409 Conflict
    _, pub_key2 = generate_keypair()
    r_conflict = client.post("/api/v1/devices/register", json={
        "device_id": dev_id,
        "farmer_id": farmer_id,
        "public_key_pem": public_key_to_pem(pub_key2),
    })
    assert r_conflict.status_code == 409

    # 5. Non-existent farmer returns 404 Not Found
    r_missing_farmer = client.post("/api/v1/devices/register", json={
        "device_id": str(uuid.uuid4()),
        "farmer_id": str(uuid.uuid4()),
        "public_key_pem": pub_pem,
    })
    assert r_missing_farmer.status_code == 404

    # 6. Status update to SUSPENDED and REVOKED
    r_susp = client.patch(f"/api/v1/devices/{dev_id}/status", json={"status": "SUSPENDED"})
    assert r_susp.status_code == 200
    assert r_susp.json()["status"] == "SUSPENDED"

    r_rev = client.patch(f"/api/v1/devices/{dev_id}/status", json={"status": "REVOKED"})
    assert r_rev.status_code == 200
    assert r_rev.json()["status"] == "REVOKED"
