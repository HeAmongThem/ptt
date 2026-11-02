"""Mode API (DEMO=false) : lectures sans cache et écritures déléguées à l'API Trust Tower."""

import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from poc_trust_tower.core import bootstrap, sync
from poc_trust_tower.core import repository as repo
from poc_trust_tower.core.api_client import ApiError, TrustTowerApi
from poc_trust_tower.core.schemas import (
    BusinessUnitCreateSchema,
    CampaignIndicatorsSchema,
    CategoryCreateSchema,
    IndicatorCreateSchema,
    SettingsSchema,
)
from poc_trust_tower.server.server import app

API_URL = "http://api.test/run"
ADMIN_CREDENTIALS = {"email": "admin@trust-tower.example", "password": "aaa"}


class FakeApi:
    """API Trust Tower minimale en mémoire : gère les repos et attribue les ids (à partir de 1000)."""

    def __init__(self, state: dict):
        self.state = copy.deepcopy(state)
        self.calls: list[dict] = []
        self.fail_on: tuple[str, int, str] | None = None  # (commande, statut HTTP, message)
        self.next_id = 1000

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        self.calls.append(body)
        command, name, item = body["command"], body["repo_name"], body.get("item")
        if self.fail_on and self.fail_on[0] == command:
            _, status, message = self.fail_on
            return httpx.Response(status, json={"error": message})
        if command == "fetch":
            return httpx.Response(200, json=self.state if name == "all" else self.state[name])
        if command == "create":
            if "campain_id" not in item:
                item = {**item, "id": self.next_id}
                self.next_id += 1
            self.state[name].append(item)
            return httpx.Response(200, json=item)
        if command == "update":
            if name == "repoSettings":
                self.state[name] = item
            else:
                self.state[name] = [item if row["id"] == item["id"] else row for row in self.state[name]]
            return httpx.Response(200, json={})
        if command == "delete":
            self.state[name] = [row for row in self.state[name] if any(row[k] != v for k, v in item.items())]
            return httpx.Response(200, json={})
        return httpx.Response(400, json={"error": f"commande inconnue {command}"})

    def commands(self) -> list[tuple[str, str]]:
        return [(c["command"], c["repo_name"]) for c in self.calls]


@pytest.fixture
def api():
    """Active le mode API sur une fausse API initialisée avec le jeu de démo ; restaure la démo ensuite."""
    snapshot = bootstrap.serialize_state()
    high_water = dict(repo._HIGH_WATER_IDS)
    fake = FakeApi(snapshot)
    sync.install(TrustTowerApi(API_URL, transport=fake.transport()))
    yield fake
    repo.set_store(None)
    bootstrap.apply_state(bootstrap.build_state(snapshot))
    repo._HIGH_WATER_IDS.update(high_water)  # les ids supprimés par d'autres tests ne doivent pas être réattribués


def test_create_sends_item_without_id_and_uses_api_id(api: FakeApi) -> None:
    bu = repo.create_business_unit(BusinessUnitCreateSchema(name="BU API"))
    assert api.commands() == [("create", "repoBusinessUnits"), ("fetch", "all")]
    assert api.calls[0]["item"] == {"name": "BU API"}  # l'id est attribué par l'API
    assert bu.id == 1000 and repo.get_business_unit(1000) is bu
    assert {"id": 1000, "name": "BU API"} in api.state["repoBusinessUnits"]


def test_update_and_delete_go_through_api(api: FakeApi) -> None:
    category = repo.update_category(1, CategoryCreateSchema(name="Finance & Co"))
    assert api.calls[0] == {"command": "update", "repo_name": "repoCategories", "item": {"id": 1, "name": "Finance & Co"}}
    assert category.name == "Finance & Co" and repo.get_category(1) is category

    new = repo.create_category(CategoryCreateSchema(name="Temporaire"))
    api.calls.clear()
    repo.delete_category(new.id)
    assert api.calls[0] == {"command": "delete", "repo_name": "repoCategories", "item": {"id": new.id}}  # clé seule
    assert api.commands() == [("delete", "repoCategories"), ("fetch", "all")]
    assert repo.get_category(new.id) is None


def test_create_indicator_serializes_references_and_audits_via_api(api: FakeApi) -> None:
    payload = IndicatorCreateSchema(
        category_id=2, business_unit_id=3, nature_of_information="Quantitatif", description_action_expected="Nouveau",
        availability_date="2026-11-01", validation_committee="COMEX", unit="%", value=10, value_previous=8,
        comment_analysis="", thresold_certified_without_reserves=90, thresold_acceptable=75,
        thresold_certified_with_significant_reserves=60, thresold_not_certified=40,
        certification_bu="pending", certification_bu_head="pending", certification_cfo="pending",
        comment_emr="", comment_bu="", comment_bu_head="", comment_cfo="",
    )
    indicator = repo.create_indicator(payload, actor=repo.get_user(1))
    assert api.commands() == [("create", "repoIndicators"), ("fetch", "all"), ("create", "repoIndicatorAudits"), ("fetch", "all")]
    sent = api.calls[0]["item"]
    assert "id" not in sent and sent["category"] == 2 and sent["business_unit"] == 3
    assert sent["availability_date"].startswith("2026-11-01") and sent["variation"] == 25.0
    assert indicator.id == 1000 and indicator.category is repo.repoCategories[1]  # références résolues
    audit = api.calls[2]["item"]
    assert audit["indicator_id"] == 1000 and audit["action"] == "created" and audit["user_email"] == "admin@trust-tower.example"
    assert repo.indicator_audit_trail(1000)[0].id == 1001


def test_campaign_links_and_settings_via_api(api: FakeApi) -> None:
    repo.set_campaign_indicators(1, CampaignIndicatorsSchema(indicator_ids=[4, 1]))  # 4 déjà lié, 1 nouveau
    deletes = [c for c in api.calls if c["command"] == "delete"]
    creates = [c for c in api.calls if c["command"] == "create"]
    assert all(set(c["item"]) == {"campain_id", "indicateur_id"} for c in deletes + creates)
    assert creates == [{"command": "create", "repo_name": "repoCampaignIndicators", "item": {"campain_id": 1, "indicateur_id": 1}}]
    assert repo.campaign_indicator_ids(1) == [4, 1]

    api.calls.clear()
    repo.update_settings(SettingsSchema(home_message="  Bonjour  "))
    assert api.calls[0] == {"command": "update", "repo_name": "repoSettings", "item": {"id": 1, "home_message": "Bonjour"}}
    assert repo.get_home_message() == "Bonjour"


def test_api_error_aborts_write_and_keeps_nothing(api: FakeApi) -> None:
    api.fail_on = ("create", 409, "nom déjà utilisé")
    before = len(repo.repoBusinessUnits)
    with pytest.raises(ApiError, match=r"HTTP 409.*nom déjà utilisé") as exc:
        repo.create_business_unit(BusinessUnitCreateSchema(name="Refusée"))
    assert exc.value.status_code == 409
    assert api.commands() == [("create", "repoBusinessUnits")]  # pas de rechargement après échec
    assert len(repo.repoBusinessUnits) == before and len(api.state["repoBusinessUnits"]) == before


def test_each_request_reloads_from_api_without_cache(api: FakeApi) -> None:
    client = TestClient(app, follow_redirects=False)
    assert client.post("/login", data=ADMIN_CREDENTIALS).status_code == 303
    assert api.commands() == [("fetch", "all")]

    assert "Bonjour depuis API" not in client.get("/").text
    api.state["repoSettings"]["home_message"] = "Bonjour depuis API"  # modifié côté API, hors application
    assert "Bonjour depuis API" in client.get("/").text
    assert api.commands() == [("fetch", "all")] * 3
    assert client.get("/statics/app.css").status_code == 200 and len(api.calls) == 3  # statiques : pas d'appel


def test_http_errors_when_api_fails(api: FakeApi) -> None:
    client = TestClient(app, follow_redirects=False)
    assert client.post("/login", data=ADMIN_CREDENTIALS).status_code == 303

    api.fail_on = ("create", 400, "payload invalide")
    response = client.post("/admin/business-units/new", data={"name": "BU KO"})
    assert response.status_code == 502 and "payload invalide" in response.text
    assert not any(b.name == "BU KO" for b in repo.repoBusinessUnits)

    api.fail_on = ("fetch", 500, "indisponible")
    response = client.get("/")
    assert response.status_code == 503 and "indisponible" in response.text


def test_fetch_one_repo_accepts_bare_list(api: FakeApi) -> None:
    client = TrustTowerApi(API_URL, transport=api.transport())
    assert client.fetch("repoCampaigns") == api.state["repoCampaigns"]
    assert api.calls[-1] == {"command": "fetch", "repo_name": "repoCampaigns"}
