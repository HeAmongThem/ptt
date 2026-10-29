import json

import httpx
import pytest
from fastapi.testclient import TestClient

from poc_trust_tower.core import sharepoint
from poc_trust_tower.core.config import SharePointConfig, load_sharepoint_config

URL = "https://okmitconsulting.sharepoint.com/sites/Rgulation/Shared%20Documents/Forms/AllItems.aspx"


# Configuration ==========================================================
def test_config_derives_site_library_and_folder() -> None:
    config = SharePointConfig(use=True, url=URL, folder="Régulation", login_timeout=180)
    assert config.site_url == "https://okmitconsulting.sharepoint.com/sites/Rgulation"
    assert config.site_path == "/sites/Rgulation"
    assert config.library == "Shared Documents"
    assert config.target_folder == "/sites/Rgulation/Shared Documents/Régulation"
    assert SharePointConfig(use=True, url=URL, folder="", login_timeout=1).target_folder == "/sites/Rgulation/Shared Documents"


def test_config_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHAREPOINT_USE", "false")
    monkeypatch.setenv("SHAREPOINT_URL", URL)
    monkeypatch.setenv("SHAREPOINT_FOLDER", "X")
    monkeypatch.setenv("SHAREPOINT_LOGIN_TIMEOUT", "42")
    config = load_sharepoint_config()
    assert (config.use, config.folder, config.login_timeout) == (False, "X", 42)
    monkeypatch.setenv("SHAREPOINT_USE", "TRUE")
    assert load_sharepoint_config().use is True


def test_dotenv_is_loaded() -> None:
    # Le .env versionné active l'intégration et pointe vers la bibliothèque Régulation.
    config = load_sharepoint_config()
    assert config.use is True and config.folder == "Régulation" and config.url == URL


# Détection de l'authentification =======================================
def test_is_authenticated_requires_site_host_and_cookies() -> None:
    host = "okmitconsulting.sharepoint.com"
    cookies = {"FedAuth": "a", "rtFa": "b"}
    assert sharepoint._is_authenticated(f"https://{host}/sites/Rgulation/x.aspx", cookies, host)
    assert not sharepoint._is_authenticated("https://login.microsoftonline.com/common/oauth2", cookies, host)
    assert not sharepoint._is_authenticated(f"https://{host}/sites/Rgulation/x.aspx", {"FedAuth": "a"}, host)
    assert not sharepoint._is_authenticated("https://other.sharepoint.com/sites/x", cookies, host)


# Client REST ============================================================
def _fake_sharepoint(calls: list[dict], *, upload_status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append({"method": request.method, "path": request.url.path, "headers": dict(request.headers), "body": request.content})
        if request.url.path.endswith("/_api/contextinfo"):
            return httpx.Response(200, json={"d": {"GetContextWebInformation": {"FormDigestValue": "DIGEST-123"}}})
        if request.url.path.endswith("/_api/web/folders"):
            return httpx.Response(201, json={"d": {}})
        if "/Files/add(" in request.url.path:
            if upload_status != 200:
                return httpx.Response(upload_status, text="denied")
            name = request.url.path.split("url='")[1].split("'")[0]
            return httpx.Response(200, json={"d": {"ServerRelativeUrl": f"/sites/Rgulation/Shared Documents/Régulation/{name}"}})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _session(transport) -> sharepoint.SharePointSession:
    return sharepoint.SharePointSession(
        site_url="https://okmitconsulting.sharepoint.com/sites/Rgulation",
        cookies={"FedAuth": "fed", "rtFa": "rt"},
        target_folder="/sites/Rgulation/Shared Documents/Régulation",
        transport=transport,
    )


def test_upload_uses_digest_cookies_and_returns_url() -> None:
    calls: list[dict] = []
    url = _session(_fake_sharepoint(calls)).upload("indicateurs.csv", b"a;b\n1;2\n")
    assert url == "https://okmitconsulting.sharepoint.com/sites/Rgulation/Shared%20Documents/R%C3%A9gulation/indicateurs.csv"
    assert [c["path"] for c in calls] == [
        "/sites/Rgulation/_api/contextinfo",
        "/sites/Rgulation/_api/web/folders",
        "/sites/Rgulation/_api/web/GetFolderByServerRelativeUrl('/sites/Rgulation/Shared Documents/Régulation')/Files/add(url='indicateurs.csv',overwrite=true)",
    ]
    upload = calls[-1]
    assert upload["headers"]["x-requestdigest"] == "DIGEST-123"
    assert "FedAuth=fed" in upload["headers"]["cookie"] and upload["body"] == b"a;b\n1;2\n"
    assert json.loads(calls[1]["body"])["ServerRelativeUrl"] == "/sites/Rgulation/Shared Documents/Régulation"


def test_upload_raises_auth_error_on_403() -> None:
    with pytest.raises(sharepoint.SharePointAuthError):
        _session(_fake_sharepoint([], upload_status=403)).upload("x.csv", b"x")


def test_upload_raises_upload_error_on_network_failure() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(sharepoint.SharePointUploadError):
        _session(httpx.MockTransport(boom)).upload("x.csv", b"x")


# Intégration à l'import =================================================
@pytest.fixture(autouse=True)
def _reset_session():
    yield
    sharepoint.set_session(None)


def test_import_warns_when_no_sharepoint_session(admin_client: TestClient) -> None:
    sharepoint.set_session(None)
    content = admin_client.get("/admin/indicators/import/template.csv").content
    response = admin_client.post("/admin/indicators/import", files={"file": ("indicateurs.csv", content)})
    assert response.status_code == 200
    assert "1 indicateur(s) importé(s)" in response.text  # l'import local reste effectif
    assert "dépôt SharePoint impossible" in response.text
    from poc_trust_tower.core import repository as repo
    repo.delete_indicator(repo.repoIndicators[-1].id)


def test_import_stores_file_on_sharepoint(admin_client: TestClient) -> None:
    calls: list[dict] = []
    sharepoint.set_session(_session(_fake_sharepoint(calls)))
    content = admin_client.get("/admin/indicators/import/template.json").content
    response = admin_client.post("/admin/indicators/import", files={"file": ("indicateurs.json", content)})
    assert response.status_code == 200
    assert "Fichier déposé sur SharePoint" in response.text
    assert calls[-1]["body"] == content
    assert calls[-1]["path"].endswith("_indicateurs.json',overwrite=true)")
    from poc_trust_tower.core import repository as repo
    repo.delete_indicator(repo.repoIndicators[-1].id)


def test_import_skips_sharepoint_when_disabled(admin_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHAREPOINT_USE", "false")
    content = admin_client.get("/admin/indicators/import/template.csv").content
    response = admin_client.post("/admin/indicators/import", files={"file": ("indicateurs.csv", content)})
    assert "SharePoint" not in response.text.split("Fichier à importer")[0]
    from poc_trust_tower.core import repository as repo
    repo.delete_indicator(repo.repoIndicators[-1].id)


# Démarrage ==============================================================
def test_startup_blocks_when_login_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    import poc_trust_tower.main as main

    monkeypatch.setenv("SHAREPOINT_USE", "true")
    monkeypatch.setattr(sharepoint, "login_interactive", lambda config: (_ for _ in ()).throw(sharepoint.SharePointAuthError("refusé")))
    messages: list[str] = []
    monkeypatch.setattr(main, "fail_and_exit", lambda message: (messages.append(message), (_ for _ in ()).throw(SystemExit(1))))
    with pytest.raises(SystemExit):
        main.connect_sharepoint()
    assert messages and "refusé" in messages[0]
    assert sharepoint.current_session() is None and "refusé" in sharepoint.last_error()


def test_startup_skips_login_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import poc_trust_tower.main as main

    monkeypatch.setenv("SHAREPOINT_USE", "false")
    monkeypatch.setattr(sharepoint, "login_interactive", lambda config: pytest.fail("ne doit pas être appelé"))
    main.connect_sharepoint()
    assert sharepoint.current_session() is None
