import pytest
from fastapi.testclient import TestClient

from poc_trust_tower.server.server import app

ADMIN_CREDENTIALS = {"email": "admin@trust-tower.example", "password": "aaa"}
USER_CREDENTIALS = {"email": "cfo@trust-tower.example", "password": "aaa"}


def _login(client: TestClient, credentials: dict) -> TestClient:
    response = client.post("/login", data=credentials)
    assert response.status_code == 303, response.text
    return client


@pytest.fixture
def anonymous_client() -> TestClient:
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def user_client() -> TestClient:
    """Client connecté avec un rôle non administrateur (CFO)."""
    return _login(TestClient(app, follow_redirects=False), USER_CREDENTIALS)


@pytest.fixture
def admin_client() -> TestClient:
    return _login(TestClient(app, follow_redirects=False), ADMIN_CREDENTIALS)
