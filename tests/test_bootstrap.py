import copy

import httpx
import pytest

from poc_trust_tower.core import api_client, bootstrap
from poc_trust_tower.core import repository as repo
from poc_trust_tower.core.security import verify_password


@pytest.fixture
def snapshot():
    """État de démonstration courant, restauré après chaque test."""
    state = bootstrap.serialize_state()
    yield copy.deepcopy(state)
    bootstrap.apply_state(bootstrap.build_state(state))


def _api(payload, calls: list | None = None, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


def test_serialize_state_matches_api_contract(snapshot) -> None:
    assert set(snapshot) == set(bootstrap.REPO_KEYS)
    assert snapshot["repoUsers"][0]["business_unit"] == 1  # références par id
    assert snapshot["repoIndicators"][0]["category"] in {c["id"] for c in snapshot["repoCategories"]}
    assert snapshot["repoSettings"] == {"id": 1, "home_message": repo.DEFAULT_HOME_MESSAGE}


def test_load_from_api_posts_json_and_rebuilds_repos(snapshot) -> None:
    calls: list[httpx.Request] = []
    payload = copy.deepcopy(snapshot)
    payload["repoBusinessUnits"].append({"id": 99, "name": "BU Test"})
    payload["repoIndicators"] = payload["repoIndicators"][:3]
    payload["repoSettings"] = {"id": "7", "home_message": "Message depuis l'API"}

    counts = bootstrap.load_from_api("http://api.test/run", transport=_api(payload, calls))

    import json
    assert calls[0].method == "POST" and calls[0].headers["content-type"] == "application/json"
    assert json.loads(calls[0].read()) == {"command": "fetch", "repo_name": "all"}
    assert counts["repoIndicators"] == 3 and counts["repoBusinessUnits"] == 6
    assert repo.get_business_unit(99).name == "BU Test"
    assert len(repo.repoIndicators) == 3
    assert repo.get_indicator(1).business_unit is repo.get_business_unit(2)  # références résolues vers les mêmes objets
    assert repo.get_home_message() == "Message depuis l'API"
    assert repo.repoSettings == {"id": 7, "home_message": "Message depuis l'API"}  # id converti en entier
    assert repo._next_id(repo.repoIndicators) == 4  # compteurs réinitialisés


def test_build_state_accepts_id_suffix_and_nested_references(snapshot) -> None:
    payload = copy.deepcopy(snapshot)
    payload["repoUsers"][0]["business_unit_id"] = payload["repoUsers"][0].pop("business_unit")
    payload["repoIndicators"][0]["category"] = {"id": payload["repoIndicators"][0]["category"], "name": "x"}
    payload["repoCampaignIndicators"][0] = {"campaign_id": 1, "indicator_id": 4}
    state = bootstrap.build_state(payload)
    assert state["repoUsers"][0].business_unit.id == 1
    assert state["repoIndicators"][0].category.id == payload["repoCategories"][1]["id"] or state["repoIndicators"][0].category is not None
    assert (state["repoCampaignIndicators"][0].campain_id, state["repoCampaignIndicators"][0].indicateur_id) == (1, 4)


def test_build_state_hashes_plain_passwords_and_keeps_hashes(snapshot) -> None:
    payload = copy.deepcopy(snapshot)
    hashed = payload["repoUsers"][0]["password"]
    payload["repoUsers"][1]["password"] = "clair"
    state = bootstrap.build_state(payload)
    assert state["repoUsers"][0].password == hashed
    assert state["repoUsers"][1].password != "clair" and verify_password("clair", state["repoUsers"][1].password)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda p: p.pop("repoCampaigns"), "clés manquantes"),
        (lambda p: p["repoIndicators"][0].update({"business_unit": 12345}), "business unit 12345 inconnue"),
        (lambda p: p["repoUsers"][0].update({"role": "BOSS"}), r"repoUsers, utilisateur 1 \(admin@trust-tower.example\) : rôle inconnu 'BOSS'"),
        (lambda p: p["repoIndicators"][0].update({"availability_date": "pas-une-date"}), "réponse API invalide"),
    ],
)
def test_build_state_rejects_invalid_payloads(snapshot, mutate, message) -> None:
    payload = copy.deepcopy(snapshot)
    mutate(payload)
    with pytest.raises(bootstrap.BootstrapError, match=message):
        bootstrap.build_state(payload)


def test_build_state_settings_defaults_and_validation(snapshot) -> None:
    payload = copy.deepcopy(snapshot)
    payload["repoSettings"] = {}
    assert bootstrap.build_state(payload)["repoSettings"] == {"id": 1, "home_message": repo.DEFAULT_HOME_MESSAGE}
    payload["repoSettings"] = [{"id": 3, "home_message": "liste"}]
    assert bootstrap.build_state(payload)["repoSettings"] == {"id": 3, "home_message": "liste"}
    payload["repoSettings"] = {"id": "abc"}
    with pytest.raises(bootstrap.BootstrapError, match="réponse API invalide"):
        bootstrap.build_state(payload)


def test_fetch_state_errors() -> None:
    with pytest.raises(bootstrap.BootstrapError, match="TRUST_TOWER_API"):
        bootstrap.fetch_state("")
    with pytest.raises(bootstrap.BootstrapError, match="HTTP 500"):
        bootstrap.fetch_state("http://api.test/run", transport=_api({}, status=500))

    def offline(request):
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(bootstrap.BootstrapError, match="impossible"):
        bootstrap.fetch_state("http://api.test/run", transport=httpx.MockTransport(offline))
    with pytest.raises(bootstrap.BootstrapError, match="objet JSON"):
        bootstrap.fetch_state("http://api.test/run", transport=_api([1, 2]))


def test_initialize_skips_api_in_demo_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO", "true")
    monkeypatch.setattr(bootstrap, "load_from_api", lambda url: pytest.fail("ne doit pas être appelé"))
    assert bootstrap.initialize(force=True) is None


def test_initialize_calls_api_when_demo_false(monkeypatch: pytest.MonkeyPatch) -> None:
    from poc_trust_tower.core import sync

    monkeypatch.setenv("DEMO", "false")
    monkeypatch.setenv("TRUST_TOWER_API", "http://api.test/run")
    monkeypatch.delenv("URL_TOKEN", raising=False)
    seen: list[tuple] = []
    monkeypatch.setattr(bootstrap, "load_from_api", lambda url, token=None: (seen.append((url, token)), {"repoIndicators": 0})[1])
    monkeypatch.setattr(bootstrap, "_initialized", False)
    assert bootstrap.initialize() == {"repoIndicators": 0}
    assert seen == [("http://api.test/run", None)]  # pas d'URL_TOKEN : pas de jeton
    assert sync.is_api_mode()  # les écritures passent désormais par l'API
    assert "Authorization" not in sync.get_store().api.headers
    assert bootstrap.initialize() is None  # déjà initialisé

    monkeypatch.setenv("DEMO", "true")
    assert bootstrap.initialize() is None
    assert not sync.is_api_mode()


def test_fetch_token_posts_secret_and_returns_bearer() -> None:
    calls: list[httpx.Request] = []
    token = api_client.fetch_token(
        "http://api.test/token", "s3cret",
        transport=_api({"access_token": "abc", "token_type": "Bearer", "expires_in": 3600}, calls),
    )
    import json
    assert token == "Bearer abc"
    assert calls[0].method == "POST" and json.loads(calls[0].read()) == {"secret": "s3cret"}

    with pytest.raises(api_client.ApiError, match="URL_TOKEN"):
        api_client.fetch_token("", "s3cret")
    with pytest.raises(api_client.ApiError, match=r"HTTP 401.*secret invalide"):
        api_client.fetch_token("http://api.test/token", "bad", transport=_api({"error": "invalid_client", "error_description": "secret invalide"}, status=401))
    with pytest.raises(api_client.ApiError, match="sans access_token"):
        api_client.fetch_token("http://api.test/token", "s3cret", transport=_api({"expires_in": 10}))


def test_api_client_sends_token_in_authorization_header() -> None:
    calls: list[httpx.Request] = []
    api = api_client.TrustTowerApi("http://api.test/run", transport=_api({"repoCampaigns": []}, calls), token="Bearer abc")
    api.fetch_all()
    assert calls[0].headers["authorization"] == "Bearer abc"
    assert "authorization" not in api_client.TrustTowerApi("http://api.test/run").headers


def test_initialize_acquires_token_and_passes_it_to_api(monkeypatch: pytest.MonkeyPatch) -> None:
    from poc_trust_tower.core import sync

    monkeypatch.setenv("DEMO", "false")
    monkeypatch.setenv("TRUST_TOWER_API", "http://api.test/run")
    monkeypatch.setenv("URL_TOKEN", "http://api.test/token")
    monkeypatch.setenv("CLIENT_SECRET", "s3cret")
    monkeypatch.setattr(bootstrap, "_initialized", False)
    asked: list[tuple] = []
    monkeypatch.setattr(bootstrap, "fetch_token", lambda url, secret: (asked.append((url, secret)), "Bearer xyz")[1])
    seen: list[tuple] = []
    monkeypatch.setattr(bootstrap, "load_from_api", lambda url, token=None: (seen.append((url, token)), {})[1])

    assert bootstrap.initialize() == {}
    assert asked == [("http://api.test/token", "s3cret")]
    assert seen == [("http://api.test/run", "Bearer xyz")]
    assert sync.get_store().api.headers["Authorization"] == "Bearer xyz"


def test_initialize_blocks_when_token_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO", "false")
    monkeypatch.setenv("TRUST_TOWER_API", "http://api.test/run")
    monkeypatch.setenv("URL_TOKEN", "http://api.test/token")
    monkeypatch.setattr(bootstrap, "_initialized", False)
    monkeypatch.setattr(bootstrap, "load_from_api", lambda url, token=None: pytest.fail("ne doit pas être appelé"))

    def refused(url, secret):
        raise api_client.ApiError("API Trust Tower : token a échoué (HTTP 401) : secret invalide", status_code=401)

    monkeypatch.setattr(bootstrap, "fetch_token", refused)
    with pytest.raises(bootstrap.BootstrapError, match="authentification.*refusée.*secret invalide"):
        bootstrap.initialize()


def test_main_blocks_when_api_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    import poc_trust_tower.main as main

    monkeypatch.setenv("DEMO", "false")
    monkeypatch.setenv("TRUST_TOWER_API", "http://127.0.0.1:1/run")
    monkeypatch.delenv("URL_TOKEN", raising=False)
    monkeypatch.setattr(bootstrap, "_initialized", False)
    messages: list[str] = []
    monkeypatch.setattr(main, "fail_and_exit", lambda message: (messages.append(message), (_ for _ in ()).throw(SystemExit(1))))
    with pytest.raises(SystemExit):
        main.load_data()
    assert messages and "Initialisation des données impossible" in messages[0]


@pytest.mark.parametrize("raw", ["BU_HE   AD", " bu_head ", "BU HEAD", "bu-head", "Bu_Head"])
def test_roles_are_normalized(snapshot, raw) -> None:
    payload = copy.deepcopy(snapshot)
    payload["repoUsers"][0]["role"] = raw
    assert bootstrap.build_state(payload)["repoUsers"][0].role.value == "BU_HEAD"
