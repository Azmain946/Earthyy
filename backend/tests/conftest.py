import os

os.environ.setdefault("EARTHYY_EAGER_JOBS", "true")

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.user import User

TEST_EMAIL = "test@earthyy.io"
TEST_PASSWORD = "test-password-123"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers(client):
    db = SessionLocal()
    try:
        if not db.query(User).filter_by(email=TEST_EMAIL).first():
            db.add(User(email=TEST_EMAIL, hashed_password=hash_password(TEST_PASSWORD), full_name="Test User"))
            db.commit()
    finally:
        db.close()
    resp = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
