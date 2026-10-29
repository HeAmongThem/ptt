import pytest
from fastapi.testclient import TestClient



@pytest.fixture
def client(user_client: TestClient) -> TestClient:
    return user_client


def test_index_returns_home_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_login_page_is_served(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_unknown_route_returns_404(client: TestClient) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404


def test_filter_indicators_by_category(client: TestClient) -> None:
    response = client.get("/my-certifications", params={"category": 1})
    assert response.status_code == 200
    html = response.text
    assert 'data-category="1"' in html
    assert '<option value="1" selected>Finance</option>' in html
    assert '<span id="count-visible">10</span>' in html


def test_filter_indicators_combined(client: TestClient) -> None:
    response = client.get(
        "/my-certifications",
        params={"variation": "up", "cfo": "Certifie", "bu_head": "En attente"},
    )
    assert response.status_code == 200
    assert 'id="count-visible"' in response.text


def test_filter_indicators_invalid_variation(client: TestClient) -> None:
    response = client.get("/my-certifications", params={"variation": "bogus"})
    assert response.status_code == 422
    assert "text/html" in response.headers["content-type"]
    assert ">422<" in response.text
    assert "query.variation" in response.text


def test_indicator_badge_links_to_category(client: TestClient) -> None:
    response = client.get("/my-certifications/7")
    assert response.status_code == 200
    assert 'href="/my-certifications/category/' in response.text


def test_indicators_by_category(client: TestClient) -> None:
    response = client.get("/my-certifications/category/1")
    assert response.status_code == 200
    assert '<option value="1" selected>Finance</option>' in response.text
    assert '<span id="count-visible">10</span>' in response.text


def test_indicators_by_unknown_category(client: TestClient) -> None:
    assert client.get("/my-certifications/category/999").status_code == 404


def test_error_page_on_404(client: TestClient) -> None:
    response = client.get("/my-certifications/999999")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "Something went wrong" in response.text
    assert ">404<" in response.text


def test_filter_form_accepts_empty_category(client: TestClient) -> None:
    # Le bouton "Filtrer" envoie category= (vide) pour "Toutes".
    response = client.get("/my-certifications", params={"category": "", "variation": "all", "bu": "", "bu_head": "", "cfo": ""})
    assert response.status_code == 200
    assert client.get("/my-certifications", params={"category": "abc"}).status_code == 422
