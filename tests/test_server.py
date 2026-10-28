import pytest
from fastapi.testclient import TestClient

from poc_trust_tower.server.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_index_returns_home_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_login_page_is_served(client: TestClient) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_unknown_route_returns_404(client: TestClient) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404


def test_filter_indicators_by_category(client: TestClient) -> None:
    response = client.get("/my-certifications", params={"category": "Finance"})
    assert response.status_code == 200
    html = response.text
    assert 'data-category="Finance"' in html
    assert '<option value="Finance" selected>' in html
    assert "10</span> / 50 indicateur(s)" in html


def test_filter_indicators_combined(client: TestClient) -> None:
    response = client.get(
        "/my-certifications",
        params={"variation": "up", "cfo": "Certifie", "bu_head": "En attente"},
    )
    assert response.status_code == 200
    assert "/ 50 indicateur(s)" in response.text


def test_filter_indicators_invalid_variation(client: TestClient) -> None:
    response = client.get("/my-certifications", params={"variation": "bogus"})
    assert response.status_code == 422
