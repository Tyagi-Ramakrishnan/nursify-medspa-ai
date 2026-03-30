"""
Basic smoke tests for the Nursify MedSpa AI MVP backend.
Run with: pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app
from app.db.database import Base, get_db

TEST_DB_URL = "postgresql://user:password@localhost:5432/nursify_test"

engine = create_engine(TEST_DB_URL)
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


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_login_success():
    res = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.com", "password": "testpassword"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password():
    res = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.com", "password": "wrongpassword"},
    )
    assert res.status_code == 401


def test_transactions_requires_auth():
    res = client.get("/api/v1/transactions/")
    assert res.status_code == 401


def test_transactions_with_auth():
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.com", "password": "testpassword"},
    )
    token = login_res.json()["access_token"]
    res = client.get("/api/v1/transactions/", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert "transactions" in res.json()


def test_report_today_with_auth():
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.com", "password": "testpassword"},
    )
    token = login_res.json()["access_token"]
    res = client.get("/api/v1/reports/today", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
