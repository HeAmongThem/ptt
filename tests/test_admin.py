import pytest
from fastapi.testclient import TestClient

from poc_trust_tower.core import repository as repo
from poc_trust_tower.core.security import verify_password
from poc_trust_tower.server.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, follow_redirects=False)


INDICATOR_FORM = {
    "category_id": "FIN",
    "business_unit_id": "RET",
    "nature_of_information": "Quantitatif",
    "description_action_expected": "Suivi",
    "availability_date": "2026-11-01T09:00",
    "validation_committee": "COMEX",
    "unit": "%",
    "value": "80",
    "value_previous": "64",
    "thresold_certified_without_reserves": "90",
    "thresold_acceptable": "75",
    "thresold_certified_with_significant_reserves": "60",
    "thresold_not_certified": "40",
}


@pytest.mark.parametrize("tab", ["business-units", "categories", "campaigns", "users", "indicators"])
def test_admin_tabs(client: TestClient, tab: str) -> None:
    response = client.get("/admin", params={"tab": tab})
    assert response.status_code == 200
    assert f'class="nav-link active" href="/admin?tab={tab}"' in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/admin/business-units/new",
        "/admin/business-units/RET",
        "/admin/categories/new",
        "/admin/categories/FIN",
        "/admin/campaigns/new",
        "/admin/campaigns/1",
        "/admin/users/new",
        "/admin/users/1",
        "/admin/indicators/new",
        "/admin/indicators/7",
    ],
)
def test_admin_forms_render(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200


def test_admin_edit_form_prefilled(client: TestClient) -> None:
    html = client.get("/admin/indicators/7").text
    assert '<option value="OPS" selected>' in html
    assert 'name="value"' in html


def test_business_unit_crud(client: TestClient) -> None:
    created = client.post("/admin/business-units/new", data={"name": "BU Nord"})
    assert created.status_code == 303
    assert created.headers["location"] == "/admin?tab=business-units"
    assert repo.get_business_unit("BUNORD").name == "BU Nord"

    assert client.post("/admin/business-units/new", data={"name": "BU Nord"}).status_code == 409
    assert client.post("/admin/business-units/new", data={"name": ""}).status_code == 422

    assert client.post("/admin/business-units/BUNORD", data={"name": "BU Grand Nord"}).status_code == 303
    assert repo.get_business_unit("BUNORD").name == "BU Grand Nord"

    assert client.post("/admin/business-units/RET/delete").status_code == 409  # utilisée
    assert client.post("/admin/business-units/BUNORD/delete").status_code == 303
    with pytest.raises(repo.NotFoundError):
        repo.get_business_unit("BUNORD")
    assert client.get("/admin/business-units/BUNORD").status_code == 404


def test_category_crud(client: TestClient) -> None:
    created = client.post("/admin/categories/new", data={"name": "Juridique"})
    assert created.status_code == 303
    assert created.headers["location"] == "/admin?tab=categories"
    assert repo.get_category("JURIDIQUE") is not None

    assert client.post("/admin/categories/new", data={"name": "Juridique"}).status_code == 409
    assert client.post("/admin/categories/new", data={"name": ""}).status_code == 422

    assert client.post("/admin/categories/JURIDIQUE", data={"name": "Legal"}).status_code == 303
    assert repo.get_category("JURIDIQUE").name == "Legal"

    assert client.post("/admin/categories/FIN/delete").status_code == 409  # utilisée
    assert client.post("/admin/categories/JURIDIQUE/delete").status_code == 303
    assert repo.get_category("JURIDIQUE") is None


def test_user_crud(client: TestClient) -> None:
    data = {"email": "x@trust-tower.example", "password": "abcd", "business_unit_id": "DIG", "role": "BU"}
    assert client.post("/admin/users/new", data=data).status_code == 303
    user_id = repo.repoUsers[-1].id

    update = {"email": "y@trust-tower.example", "password": "", "business_unit_id": "RET", "role": "CFO"}
    assert client.post(f"/admin/users/{user_id}", data=update).status_code == 303
    user = repo.get_user(user_id)
    assert (user.email, user.role.value, user.business_unit.id) == ("y@trust-tower.example", "CFO", "RET")
    assert verify_password("abcd", user.password)  # mot de passe vide = inchangé, et stocké haché
    assert client.post(f"/admin/users/{user_id}", data={**update, "password": "ab"}).status_code == 422

    assert client.post(f"/admin/users/{user_id}/delete").status_code == 303
    with pytest.raises(repo.NotFoundError):
        repo.get_user(user_id)


def test_indicator_and_campaign_crud(client: TestClient) -> None:
    assert client.post("/admin/indicators/new", data=INDICATOR_FORM).status_code == 303
    indicator_id = repo.repoIndicators[-1].id
    assert repo.get_indicator(indicator_id).variation == 25.0

    assert client.post(f"/admin/indicators/{indicator_id}", data={**INDICATOR_FORM, "value": "32"}).status_code == 303
    assert repo.get_indicator(indicator_id).variation == -50.0
    assert client.post(f"/admin/indicators/{indicator_id}", data={**INDICATOR_FORM, "thresold_acceptable": "95"}).status_code == 422

    campaign = {"name": "T1 2027", "start_date": "2027-01-01", "end_date": "2027-03-31", "indicator_ids": [indicator_id, "1"]}
    assert client.post("/admin/campaigns/new", data=campaign).status_code == 303
    campaign_id = repo.repoCampaigns[-1].id
    assert [i.id for i in repo.get_campaign(campaign_id).indicators] == [indicator_id, "1"]
    assert client.post("/admin/campaigns/new", data={**campaign, "start_date": "2027-12-31"}).status_code == 422

    # Supprimer un indicateur le retire des campagnes qui le référencent.
    assert client.post(f"/admin/indicators/{indicator_id}/delete").status_code == 303
    assert [i.id for i in repo.get_campaign(campaign_id).indicators] == ["1"]

    assert client.post(f"/admin/campaigns/{campaign_id}/delete").status_code == 303
    assert client.get(f"/admin/campaigns/{campaign_id}").status_code == 404


# Import ================================================================
def test_import_page_and_templates(client: TestClient) -> None:
    assert client.get("/admin/indicators/import").status_code == 200
    for ext, expected_type in [("csv", "text/csv"), ("json", "application/json"), ("xlsx", "spreadsheetml")]:
        response = client.get(f"/admin/indicators/import/template.{ext}")
        assert response.status_code == 200
        assert expected_type in response.headers["content-type"]
        assert f'filename="indicators-template.{ext}"' in response.headers["content-disposition"]


@pytest.mark.parametrize("ext", ["csv", "json", "xlsx"])
def test_import_template_roundtrip(client: TestClient, ext: str) -> None:
    content = client.get(f"/admin/indicators/import/template.{ext}").content
    before = len(repo.repoIndicators)
    response = client.post("/admin/indicators/import", files={"file": (f"indicateurs.{ext}", content)})
    assert response.status_code == 200
    assert "1 indicateur(s) importé(s)" in response.text
    assert len(repo.repoIndicators) == before + 1
    created = repo.repoIndicators[-1]
    assert created.category.id == "FIN" and created.variation == 9.55
    repo.delete_indicator(created.id)


def test_import_invalid_rows_is_all_or_nothing(client: TestClient) -> None:
    header = "category_id;business_unit_id;nature_of_information;description_action_expected;availability_date;validation_committee;unit;value;value_previous;thresold_certified_without_reserves;thresold_acceptable;thresold_certified_with_significant_reserves;thresold_not_certified"
    rows = [
        "FIN;RET;Q;Ligne valide;2026-12-01;COMEX;%;50;40;90;75;60;40",
        "XXX;RET;Q;Catégorie inconnue;2026-12-01;COMEX;%;50;40;90;75;60;40",
    ]
    content = ("\n".join([header, *rows]) + "\n").encode()
    before = len(repo.repoIndicators)
    response = client.post("/admin/indicators/import", files={"file": ("bad.csv", content)})
    assert response.status_code == 422
    assert "catégorie inconnue : XXX" in response.text
    assert "<td>3</td>" in response.text  # numéro de ligne
    assert len(repo.repoIndicators) == before


def test_import_unsupported_format(client: TestClient) -> None:
    response = client.post("/admin/indicators/import", files={"file": ("notes.txt", b"hello")})
    assert response.status_code == 422
    assert "non supporté" in response.text
