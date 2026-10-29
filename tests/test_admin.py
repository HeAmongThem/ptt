import pytest
from fastapi.testclient import TestClient

from poc_trust_tower.core import repository as repo
from poc_trust_tower.core.security import verify_password


@pytest.fixture
def client(admin_client: TestClient) -> TestClient:
    return admin_client


INDICATOR_FORM = {
    "category_id": "1",
    "business_unit_id": "1",
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


@pytest.mark.parametrize("tab", ["business-units", "categories", "campaigns", "users", "indicators", "campaign-indicators", "settings"])
def test_admin_tabs(client: TestClient, tab: str) -> None:
    response = client.get("/admin", params={"tab": tab})
    assert response.status_code == 200
    assert f'class="nav-link active" href="/admin?tab={tab}"' in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/admin/business-units/new",
        "/admin/business-units/1",
        "/admin/categories/new",
        "/admin/categories/1",
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
    assert '<option value="3" selected>' in html
    assert 'name="value"' in html


def test_business_unit_crud(client: TestClient) -> None:
    created = client.post("/admin/business-units/new", data={"name": "BU Nord"})
    assert created.status_code == 303
    assert created.headers["location"] == "/admin?tab=business-units"
    bu_id = repo.repoBusinessUnits[-1].id
    assert repo.get_business_unit(bu_id).name == "BU Nord"

    assert client.post("/admin/business-units/new", data={"name": "BU Nord"}).status_code == 409
    assert client.post("/admin/business-units/new", data={"name": ""}).status_code == 422

    assert client.post(f"/admin/business-units/{bu_id}", data={"name": "BU Grand Nord"}).status_code == 303
    assert repo.get_business_unit(bu_id).name == "BU Grand Nord"

    assert client.post("/admin/business-units/1/delete").status_code == 409  # utilisée
    assert client.post(f"/admin/business-units/{bu_id}/delete").status_code == 303
    with pytest.raises(repo.NotFoundError):
        repo.get_business_unit(bu_id)
    assert client.get(f"/admin/business-units/{bu_id}").status_code == 404


def test_category_crud(client: TestClient) -> None:
    created = client.post("/admin/categories/new", data={"name": "Juridique"})
    assert created.status_code == 303
    assert created.headers["location"] == "/admin?tab=categories"
    category_id = repo.repoCategories[-1].id
    assert repo.get_category(category_id).name == "Juridique"

    assert client.post("/admin/categories/new", data={"name": "Juridique"}).status_code == 409
    assert client.post("/admin/categories/new", data={"name": ""}).status_code == 422

    assert client.post(f"/admin/categories/{category_id}", data={"name": "Legal"}).status_code == 303
    assert repo.get_category(category_id).name == "Legal"

    assert client.post("/admin/categories/1/delete").status_code == 409  # utilisée
    assert client.post(f"/admin/categories/{category_id}/delete").status_code == 303
    assert repo.get_category(category_id) is None


def test_user_crud(client: TestClient) -> None:
    data = {"email": "x@trust-tower.example", "password": "abcd", "business_unit_id": "3", "role": "BU"}
    assert client.post("/admin/users/new", data=data).status_code == 303
    user_id = repo.repoUsers[-1].id

    update = {"email": "y@trust-tower.example", "password": "", "business_unit_id": "1", "role": "CFO"}
    assert client.post(f"/admin/users/{user_id}", data=update).status_code == 303
    user = repo.get_user(user_id)
    assert (user.email, user.role.value, user.business_unit.id) == ("y@trust-tower.example", "CFO", 1)
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

    campaign = {"name": "T1 2027", "start_date": "2027-01-01", "end_date": "2027-03-31", "indicator_ids": [indicator_id, 1], "actif": "true"}
    assert client.post("/admin/campaigns/new", data=campaign).status_code == 303
    campaign_id = repo.repoCampaigns[-1].id
    assert repo.get_campaign(campaign_id).actif is True
    # Case décochée -> non envoyée -> inactif
    assert client.post(f"/admin/campaigns/{campaign_id}", data={k: v for k, v in campaign.items() if k != "actif"}).status_code == 303
    assert repo.get_campaign(campaign_id).actif is False
    assert repo.campaign_indicator_ids(campaign_id) == [indicator_id, 1]
    assert client.post("/admin/campaigns/new", data={**campaign, "start_date": "2027-12-31"}).status_code == 422

    # Supprimer un indicateur le retire des campagnes qui le référencent.
    assert client.post(f"/admin/indicators/{indicator_id}/delete").status_code == 303
    assert repo.campaign_indicator_ids(campaign_id) == [1]

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
    assert created.category.id == 1 and created.variation == 9.55
    repo.delete_indicator(created.id)


def test_import_invalid_rows_is_all_or_nothing(client: TestClient) -> None:
    header = "category_id;business_unit_id;nature_of_information;description_action_expected;availability_date;validation_committee;unit;value;value_previous;thresold_certified_without_reserves;thresold_acceptable;thresold_certified_with_significant_reserves;thresold_not_certified"
    rows = [
        "1;1;Q;Ligne valide;2026-12-01;COMEX;%;50;40;90;75;60;40",
        "999;1;Q;Catégorie inconnue;2026-12-01;COMEX;%;50;40;90;75;60;40",
    ]
    content = ("\n".join([header, *rows]) + "\n").encode()
    before = len(repo.repoIndicators)
    response = client.post("/admin/indicators/import", files={"file": ("bad.csv", content)})
    assert response.status_code == 422
    assert "catégorie inconnue : 999" in response.text
    assert "<td>3</td>" in response.text  # numéro de ligne
    assert len(repo.repoIndicators) == before


def test_import_unsupported_format(client: TestClient) -> None:
    response = client.post("/admin/indicators/import", files={"file": ("notes.txt", b"hello")})
    assert response.status_code == 422
    assert "non supporté" in response.text


# Campaign indicators ===================================================
def test_campaign_indicators_tab_shows_checklist(client: TestClient) -> None:
    campaign = repo.get_campaign(2)
    html = client.get("/admin", params={"tab": "campaign-indicators", "campaign": campaign.id}).text
    assert f'<option value="{campaign.id}" selected>' in html
    assert html.count('name="indicator_ids"') == len(repo.repoIndicators)
    assert html.count('name="indicator_ids" value=') == len(repo.repoIndicators)
    checked = [int(x) for x in __import__("re").findall(r'name="indicator_ids" value="(\d+)"\s+id="ci-\d+" checked', html)]
    assert sorted(checked) == sorted(repo.campaign_indicator_ids(campaign.id))
    assert f"{len(repo.repoCampaignIndicators)} association(s)" in html


def test_campaign_indicators_tab_defaults_to_first_campaign(client: TestClient) -> None:
    html = client.get("/admin", params={"tab": "campaign-indicators"}).text
    assert f'<option value="{repo.repoCampaigns[0].id}" selected>' in html


def test_campaign_indicators_bulk_save(client: TestClient) -> None:
    campaign = repo.get_campaign(1)
    original = repo.campaign_indicator_ids(campaign.id)
    try:
        new_ids = [1, 2, 3, 2]  # doublon volontaire
        response = client.post(f"/admin/campaign-indicators/{campaign.id}", data={"indicator_ids": new_ids})
        assert response.status_code == 303
        assert response.headers["location"] == f"/admin?tab=campaign-indicators&campaign={campaign.id}&saved=1"
        assert repo.campaign_indicator_ids(campaign.id) == [1, 2, 3]
        assert {l.indicateur_id for l in repo.repoCampaignIndicators if l.campain_id == campaign.id} == {1, 2, 3}

        # Aucune case cochée -> campagne vidée
        assert client.post(f"/admin/campaign-indicators/{campaign.id}", data={}).status_code == 303
        assert repo.campaign_indicator_ids(campaign.id) == []
        assert not any(l.campain_id == campaign.id for l in repo.repoCampaignIndicators)

        assert client.post(f"/admin/campaign-indicators/{campaign.id}", data={"indicator_ids": [999]}).status_code == 404
        assert client.post("/admin/campaign-indicators/999", data={"indicator_ids": [1]}).status_code == 404
        assert client.post(f"/admin/campaign-indicators/{campaign.id}", data={"indicator_ids": ["abc"]}).status_code == 422
    finally:
        client.post(f"/admin/campaign-indicators/{campaign.id}", data={"indicator_ids": original})
        assert repo.campaign_indicator_ids(campaign.id) == original


def test_campaign_links_follow_campaign_and_indicator_lifecycle(client: TestClient) -> None:
    assert client.post("/admin/indicators/new", data=INDICATOR_FORM).status_code == 303
    indicator_id = repo.repoIndicators[-1].id
    campaign = {"name": "Liens", "start_date": "2027-01-01", "end_date": "2027-03-31", "indicator_ids": [indicator_id, 1]}
    assert client.post("/admin/campaigns/new", data=campaign).status_code == 303
    campaign_id = repo.repoCampaigns[-1].id
    links = lambda: {(l.campain_id, l.indicateur_id) for l in repo.repoCampaignIndicators if l.campain_id == campaign_id}
    assert links() == {(campaign_id, indicator_id), (campaign_id, 1)}

    # Supprimer l'indicateur retire son lien ; supprimer la campagne retire les siens.
    assert client.post(f"/admin/indicators/{indicator_id}/delete").status_code == 303
    assert links() == {(campaign_id, 1)}
    assert client.post(f"/admin/campaigns/{campaign_id}/delete").status_code == 303
    assert links() == set()


def test_campaign_form_uses_checkbox_picker(client: TestClient) -> None:
    html = client.get("/admin/campaigns/new").text
    assert html.count('name="indicator_ids"') == len(repo.repoIndicators)
    assert 'id="ci-search"' in html and 'id="f-actif"' in html
    assert "<select" not in html.split('id="ci-table"')[0].split("<form")[1]  # plus de listbox multi-sélection

    campaign = repo.get_campaign(2)
    html = client.get(f"/admin/campaigns/{campaign.id}").text
    checked = [int(x) for x in __import__("re").findall(r'name="indicator_ids" value="(\d+)"\s+id="ci-\d+" checked', html)]
    assert sorted(checked) == sorted(repo.campaign_indicator_ids(campaign.id))
