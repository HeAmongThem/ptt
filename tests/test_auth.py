import pytest
from fastapi.testclient import TestClient

from poc_trust_tower.core.security import hash_password, verify_password
from poc_trust_tower.server.server import app

ADMIN = {"email": "admin@trust-tower.example", "password": "aaa"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, follow_redirects=False)


def test_password_hashing_roundtrip() -> None:
    hashed = hash_password("secret", rounds=4)
    assert hashed != "secret" and hashed.startswith("$2b$")
    assert verify_password("secret", hashed)
    assert not verify_password("other", hashed)
    assert not verify_password("secret", "not-a-hash")


def test_login_form(client: TestClient) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    assert 'name="email"' in response.text and 'name="password"' in response.text


def test_login_wrong_password(client: TestClient) -> None:
    response = client.post("/login", data={**ADMIN, "password": "wrong"})
    assert response.status_code == 401
    assert "Email ou mot de passe incorrect" in response.text
    assert f'value="{ADMIN["email"]}"' in response.text
    assert "session" not in response.headers.get("set-cookie", "")


def test_login_unknown_user(client: TestClient) -> None:
    assert client.post("/login", data={"email": "nobody@trust-tower.example", "password": "aaa"}).status_code == 401


def test_login_invalid_email(client: TestClient) -> None:
    assert client.post("/login", data={"email": "not-an-email", "password": "aaa"}).status_code == 422


def test_login_logout_flow(client: TestClient) -> None:
    response = client.post("/login", data={"email": ADMIN["email"].upper(), "password": ADMIN["password"]})
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session=" in response.headers["set-cookie"]

    home = client.get("/")
    assert ADMIN["email"] in home.text
    assert "Se déconnecter" in home.text
    assert 'href="/admin"' in home.text

    assert client.get("/login").status_code == 303  # déjà connecté

    response = client.post("/logout")
    assert response.status_code == 303 and response.headers["location"] == "/login"
    home = client.get("/")
    assert "Se déconnecter" not in home.text and "Se connecter" in home.text


def test_login_redirects_to_next(client: TestClient) -> None:
    response = client.post("/login?next=/my-certifications", data=ADMIN)
    assert response.headers["location"] == "/my-certifications"


@pytest.mark.parametrize("target", ["//evil.com", "https://evil.com", "evil"])
def test_login_rejects_open_redirect(client: TestClient, target: str) -> None:
    response = client.post("/login", params={"next": target}, data=ADMIN)
    assert response.headers["location"] == "/"


def test_non_admin_has_no_admin_link(client: TestClient) -> None:
    client.post("/login", data={"email": "cfo@trust-tower.example", "password": "aaa"})
    home = client.get("/")
    assert "CFO" in home.text and 'href="/admin"' not in home.text


# Contrôle d'accès ======================================================
@pytest.mark.parametrize("path", ["/my-certifications", "/my-certifications/7", "/admin", "/admin/indicators/import"])
def test_anonymous_is_redirected_to_login(anonymous_client: TestClient, path: str) -> None:
    response = anonymous_client.get(path)
    assert response.status_code == 303
    assert response.headers["location"] == f"/login?next={path}"


def test_anonymous_cannot_post_to_admin(anonymous_client: TestClient) -> None:
    assert anonymous_client.post("/admin/categories/new", data={"name": "X"}).status_code == 303


def test_logged_user_can_see_certifications(user_client: TestClient) -> None:
    assert user_client.get("/my-certifications").status_code == 200
    assert user_client.get("/my-certifications/7").status_code == 200


def test_non_admin_is_forbidden_on_admin(user_client: TestClient) -> None:
    response = user_client.get("/admin")
    assert response.status_code == 403
    assert "Accès réservé" in response.text
    assert user_client.post("/admin/categories/new", data={"name": "X"}).status_code == 403


def test_admin_can_access_admin(admin_client: TestClient) -> None:
    assert admin_client.get("/admin").status_code == 200
    assert admin_client.get("/my-certifications").status_code == 200


def test_login_next_round_trip(anonymous_client: TestClient) -> None:
    redirect = anonymous_client.get("/admin")
    login = anonymous_client.post(redirect.headers["location"], data={"email": "admin@trust-tower.example", "password": "aaa"})
    assert login.status_code == 303 and login.headers["location"] == "/admin"
    assert anonymous_client.get("/admin").status_code == 200
