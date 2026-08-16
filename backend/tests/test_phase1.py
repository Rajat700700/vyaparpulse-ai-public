"""Phase 1 automated tests using FastAPI TestClient.

Each test gets its own TestClient so the app lifespan resets the motor client
onto the current event loop. This avoids "attached to a different loop"
errors when multiple TestClient instances would otherwise share the cached
async Mongo client.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import pytest
from fastapi.testclient import TestClient


def _client():
    import importlib
    server = importlib.import_module("server")
    return TestClient(server.app)


# ---------------------------- Auth ----------------------------

def test_health():
    with _client() as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_login_success_and_me():
    with _client() as c:
        r = c.post(
            "/api/auth/login",
            json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == os.environ["ADMIN_EMAIL"].lower()
        assert data["role"] == "ENTERPRISE_ADMIN"
        assert data["is_demo"] is False
        assert data["access_token"], "token expected in body for header-based tests"

        r2 = c.get("/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
        assert r2.status_code == 200
        assert r2.json()["email"] == os.environ["ADMIN_EMAIL"].lower()


def test_login_wrong_password():
    with _client() as c:
        r = c.post(
            "/api/auth/login",
            json={"email": os.environ["ADMIN_EMAIL"], "password": "wrong-password"},
        )
        assert r.status_code == 401


def test_me_requires_auth():
    with _client() as c:
        r = c.get("/api/auth/me")
        assert r.status_code == 401


# ---------------------------- Sandbox demo ----------------------------

def test_demo_session_issues_demo_token():
    with _client() as c:
        r = c.post("/api/demo/session")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["role"] == "DEMO"
        assert data["is_demo"] is True
        assert data["access_token"]

        r2 = c.get("/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
        assert r2.status_code == 200
        assert r2.json()["is_demo"] is True


def test_demo_cannot_login_with_password():
    with _client() as c:
        r = c.post(
            "/api/auth/login",
            json={"email": "sandbox@vyaparpulse.ai", "password": "anything"},
        )
        assert r.status_code == 401


# ---------------------------- Tenant scoping ----------------------------

def test_tenant_isolation_admin_vs_demo():
    with _client() as admin:
        r_login = admin.post(
            "/api/auth/login",
            json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]},
        )
        admin_token = r_login.json()["access_token"]
        r_admin = admin.get(
            "/api/tenant/command-centre",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r_admin.status_code == 200
        a = r_admin.json()

    with _client() as demo:
        r_demo_session = demo.post("/api/demo/session")
        demo_token = r_demo_session.json()["access_token"]
        r_demo = demo.get(
            "/api/tenant/command-centre",
            headers={"Authorization": f"Bearer {demo_token}"},
        )
        assert r_demo.status_code == 200
        d = r_demo.json()

    assert a["enterprise"]["is_demo"] is False
    assert d["enterprise"]["is_demo"] is True
    assert a["enterprise"]["id"] != d["enterprise"]["id"]
    # After Phase 3 the demo tenant is populated with a contest-ready dataset,
    # so is_empty may be False. The isolation guarantee itself is what matters.


def test_command_centre_requires_auth():
    with _client() as c:
        r = c.get("/api/tenant/command-centre")
        assert r.status_code == 401


# ---------------------------- Persistent-write guard ----------------------------

def test_persistent_write_guard_rejects_demo():
    from fastapi import HTTPException
    from app.security import require_persistent_write, ROLE_DEMO
    demo_user = {"role": ROLE_DEMO, "is_demo": True, "id": "x", "enterprise_id": "y"}
    with pytest.raises(HTTPException) as exc:
        require_persistent_write(demo_user)
    assert exc.value.status_code == 403

    real_user = {"role": "ENTERPRISE_ADMIN", "is_demo": False, "id": "x", "enterprise_id": "y"}
    assert require_persistent_write(real_user) is real_user


# ---------------------------- Password hashing ----------------------------

def test_bcrypt_hash_and_verify():
    from app.security import hash_password, verify_password
    h = hash_password("SuperSecret!")
    assert h.startswith("$2b$")
    assert verify_password("SuperSecret!", h) is True
    assert verify_password("wrong", h) is False
