import uuid
import json
import base64
import hashlib
from datetime import datetime, timezone
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
    test_db = str(tmp_path / "seq_test.db")
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


def test_sequence_monotonicty_and_idempotency_flow(client):
    # Setup farmer, device, farm
    rf = client.post("/api/v1/farmers", json={
        "full_name": "Seq Farmer",
        "phone_number": "+919811223344",
        "language_pref": "en",
    })
    farmer_id = rf.json()["id"]

    priv_key, pub_key = generate_keypair()
    pub_pem = public_key_to_pem(pub_key)
    device_id = str(uuid.uuid4())

    client.post("/api/v1/devices/register", json={
        "device_id": device_id,
        "farmer_id": farmer_id,
        "public_key_pem": pub_pem,
    })

    farm_res = client.post("/api/v1/farms", json={
        "farmer_id": farmer_id,
        "farm_name": "Field 1",
        "crop_type": "Cotton",
        "boundary_geojson": json.dumps({
            "type": "Polygon",
            "coordinates": [[[78.5, 19.6], [78.51, 19.6], [78.51, 19.61], [78.5, 19.61], [78.5, 19.6]]]
        }),
    })
    farm_id = farm_res.json()["id"]

    # Build and sign evidence helper
    def build_submission(seq: int, payload_bytes: bytes, evidence_id=None, capture_ts=None):
        img_hash = hashlib.sha256(payload_bytes).hexdigest()
        env = {
            "device_id": device_id,
            "evidence_id": evidence_id or str(uuid.uuid4()),
            "farm_id": farm_id,
            "image_hash": img_hash,
            "lifecycle_stage": "SOWING",
            "metadata": {
                "capture_source": "CAMERA",
                "capture_timestamp": capture_ts or datetime.now(timezone.utc).isoformat(),
                "gps_accuracy": 5.0,
                "latitude": 19.605,
                "longitude": 78.505,
            },
            "schema_version": "1.0",
            "sequence_number": seq,
        }
        can_bytes = canonicalize(env)
        sig_der = sign(priv_key, can_bytes)
        sig_b64 = base64.b64encode(sig_der).decode("utf-8")
        files = {"file": ("img.jpg", payload_bytes, "image/jpeg")}
        data = {"envelope": json.dumps(env), "signature": sig_b64}
        return data, files, env

    # 1. Sequence 1 accepted -> 201 Created
    data1, files1, env1 = build_submission(seq=1, payload_bytes=b"IMAGE_PAYLOAD_1")
    r1 = client.post("/api/v1/evidence/ingest", data=data1, files=files1)
    assert r1.status_code == 201
    receipt1 = r1.json()
    assert receipt1["sequence_number"] == 1
    assert receipt1["status"] == "DURABLY_ACKED"

    # 2. Idempotent retry of Sequence 1 with identical envelope and image -> 200 OK
    files1_retry = {"file": ("img.jpg", b"IMAGE_PAYLOAD_1", "image/jpeg")}
    r1_retry = client.post("/api/v1/evidence/ingest", data=data1, files=files1_retry)
    assert r1_retry.status_code == 200
    assert r1_retry.json()["sequence_number"] == 1
    assert r1_retry.json()["status"] == "DURABLY_ACKED"

    # 3. Replay of Sequence 1 with altered payload -> 409 Conflict
    data1_bad, files1_bad, _ = build_submission(seq=1, payload_bytes=b"ALTERED_IMAGE_PAYLOAD")
    r1_replay_bad = client.post("/api/v1/evidence/ingest", data=data1_bad, files=files1_bad)
    assert r1_replay_bad.status_code == 409

    # 4. Sequence gap (submitting sequence 3 when next is 2) -> 409 Conflict
    data3, files3, _ = build_submission(seq=3, payload_bytes=b"IMAGE_PAYLOAD_3")
    r3_gap = client.post("/api/v1/evidence/ingest", data=data3, files=files3)
    assert r3_gap.status_code == 409

    # 5. Normal progression to Sequence 2 -> 201 Created
    data2, files2, _ = build_submission(seq=2, payload_bytes=b"IMAGE_PAYLOAD_2")
    r2 = client.post("/api/v1/evidence/ingest", data=data2, files=files2)
    assert r2.status_code == 201
    assert r2.json()["sequence_number"] == 2

    # 6. Verify audit logs recorded IDEMPOTENT_RETRY and REPLAY_CONFLICT_ATTEMPT
    r_audit = client.get("/api/v1/audit/logs")
    assert r_audit.status_code == 200
    logs = r_audit.json()
    event_types = [l["event_type"] for l in logs]
    assert "EVIDENCE_INGESTED" in event_types
    assert "IDEMPOTENT_RETRY" in event_types
    assert "REPLAY_CONFLICT_ATTEMPT" in event_types
