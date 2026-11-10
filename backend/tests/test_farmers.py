import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.core.database import Base, get_db


@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "farmers_test.db")
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


def test_farmer_registration_login_and_language_update(client):
    # 1. Register with Telugu preference
    phone = "+919849112233"
    reg_payload = {
        "full_name": "Ramu K",
        "phone_number": phone,
        "language_pref": "te",
    }
    res_reg = client.post("/api/v1/farmers/register", json=reg_payload)
    assert res_reg.status_code == 201
    auth_data = res_reg.json()
    assert "access_token" in auth_data
    assert auth_data["farmer"]["full_name"] == "Ramu K"
    assert auth_data["farmer"]["language_pref"] == "te"
    farmer_id = auth_data["farmer"]["id"]

    # 2. Login by phone number
    res_login = client.post("/api/v1/farmers/login", json={"phone_number": phone})
    assert res_login.status_code == 200
    login_data = res_login.json()
    assert login_data["farmer"]["id"] == farmer_id
    assert "access_token" in login_data

    # 3. Update language preference to Hindi ('hi')
    res_lang = client.patch(f"/api/v1/farmers/{farmer_id}/language", json={"language_pref": "hi"})
    assert res_lang.status_code == 200
    assert res_lang.json()["language_pref"] == "hi"

    # 4. Fetch farmer by ID
    res_get = client.get(f"/api/v1/farmers/{farmer_id}")
    assert res_get.status_code == 200
    assert res_get.json()["language_pref"] == "hi"

    # 5. Non-existent login returns 404
    res_non = client.post("/api/v1/farmers/login", json={"phone_number": "+919999999999"})
    assert res_non.status_code == 404
