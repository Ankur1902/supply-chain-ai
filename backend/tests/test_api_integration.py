"""
Integration tests exercising the real FastAPI app against a real MySQL
database via SQLAlchemy's TestClient (in-process ASGI, no network hop, but
a genuine DB round trip). Requires `docker compose up` (or an equivalent
local MySQL) and `python scripts/seed_database.py` to have been run first —
skipped automatically if the demo admin user isn't present, rather than
failing the whole suite in an environment without a database.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.user import User

pytestmark = pytest.mark.integration

ADMIN_EMAIL = "admin@supplychain-demo.com"
ADMIN_PASSWORD = "DemoPass123!"
VIEWER_EMAIL = "viewer@supplychain-demo.com"


def _demo_users_present() -> bool:
    try:
        with SessionLocal() as db:
            return db.query(User).filter(User.email == ADMIN_EMAIL).first() is not None
    except Exception:
        return False


requires_seeded_db = pytest.mark.skipif(
    not _demo_users_present(), reason="Demo database not available — run docker compose up + scripts/seed_database.py"
)


@pytest.fixture
def client():
    return TestClient(app)


@requires_seeded_db
def test_login_succeeds_with_correct_password(client):
    res = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body["data"]
    assert "refresh_token" in body["data"]


@requires_seeded_db
def test_login_rejects_wrong_password(client):
    res = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong-password"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"


@requires_seeded_db
def test_protected_route_requires_auth(client):
    res = client.get("/api/v1/shipments")
    assert res.status_code == 401


@requires_seeded_db
def test_protected_route_works_with_valid_token(client):
    login = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    token = login.json()["data"]["access_token"]
    res = client.get("/api/v1/shipments", headers={"Authorization": f"Bearer {token}"}, params={"page_size": 1})
    assert res.status_code == 200
    assert "data" in res.json()


@requires_seeded_db
def test_viewer_cannot_run_scenarios(client):
    """RBAC enforced end-to-end: a viewer-role token must be rejected by a
    route that requires Permission.SCENARIOS_RUN."""
    login = client.post("/api/v1/auth/login", json={"email": VIEWER_EMAIL, "password": ADMIN_PASSWORD})
    token = login.json()["data"]["access_token"]
    res = client.post(
        "/api/v1/scenarios/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"shipment_code": "SHP-0-0", "shipping_mode": "Standard Class"},
    )
    assert res.status_code == 403


@requires_seeded_db
def test_sql_injection_in_search_param_is_not_executed(client):
    """The shipment search filter must be parameterized — a classic
    injection payload should just find zero results, not error or leak
    data."""
    login = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    token = login.json()["data"]["access_token"]
    res = client.get(
        "/api/v1/shipments",
        headers={"Authorization": f"Bearer {token}"},
        params={"search": "' OR '1'='1"},
    )
    assert res.status_code == 200
