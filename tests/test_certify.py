import pytest
from fastapi.testclient import TestClient

from poc_trust_tower.core import repository as repo

# Indicateur 7 -> BU Digital (DIG), indicateur 8 -> BU International (INT)
DIG_INDICATOR = "7"
INT_INDICATOR = "8"


def _snapshot(indicator_id: str) -> dict:
    i = repo.get_indicator(indicator_id)
    return {f: getattr(i, f) for pair in repo.CERTIFICATION_FIELDS.values() for f in pair}


def _certify(client: TestClient, indicator_id: str, status: str, comment: str):
    return client.post(f"/my-certifications/{indicator_id}/certify", data={"status": status, "comment": comment})


@pytest.mark.parametrize(
    ("fixture", "indicator_id", "status_field", "comment_field"),
    [
        ("bu_client", DIG_INDICATOR, "certification_bu", "comment_bu"),
        ("bu_head_client", INT_INDICATOR, "certification_bu_head", "comment_bu_head"),
        ("user_client", DIG_INDICATOR, "certification_cfo", "comment_cfo"),  # CFO
    ],
)
def test_role_updates_only_its_own_fields(request, fixture, indicator_id, status_field, comment_field) -> None:
    client: TestClient = request.getfixturevalue(fixture)
    before = _snapshot(indicator_id)

    response = _certify(client, indicator_id, "certified_without_reserves", "Validé")
    assert response.status_code == 303
    assert response.headers["location"] == f"/my-certifications/{indicator_id}?saved=1"

    after = _snapshot(indicator_id)
    assert after[status_field] == "certified_without_reserves"
    assert after[comment_field] == "Validé"
    untouched = {k: v for k, v in after.items() if k not in (status_field, comment_field)}
    assert untouched == {k: v for k, v in before.items() if k not in (status_field, comment_field)}

    page = client.get(f"/my-certifications/{indicator_id}?saved=1")
    assert "Votre certification a été enregistrée" in page.text
    assert '<option value="certified_without_reserves" selected>' in page.text


def test_bu_cannot_certify_other_business_unit(bu_client: TestClient) -> None:
    before = _snapshot(INT_INDICATOR)
    response = _certify(bu_client, INT_INDICATOR, "not_certified", "tentative")
    assert response.status_code == 403
    assert _snapshot(INT_INDICATOR) == before

    assert bu_client.get(f"/my-certifications/{INT_INDICATOR}").status_code == 403


def test_bu_head_cannot_certify_other_business_unit(bu_head_client: TestClient) -> None:
    assert _certify(bu_head_client, DIG_INDICATOR, "pending", "").status_code == 403


def test_cfo_can_certify_any_business_unit(user_client: TestClient) -> None:
    assert _certify(user_client, INT_INDICATOR, "acceptable", "").status_code == 303
    assert repo.get_indicator(INT_INDICATOR).certification_cfo == "acceptable"


def test_admin_cannot_certify(admin_client: TestClient) -> None:
    assert _certify(admin_client, DIG_INDICATOR, "pending", "").status_code == 403
    page = admin_client.get(f"/my-certifications/{DIG_INDICATOR}")
    assert page.status_code == 200 and "/certify" not in page.text


def test_form_shows_only_user_level(bu_client: TestClient) -> None:
    page = bu_client.get(f"/my-certifications/{DIG_INDICATOR}")
    assert "niveau BU</div>" in page.text
    assert 'name="status"' in page.text and 'name="comment"' in page.text
    assert page.text.count('name="status"') == 1  # un seul formulaire, pas un par niveau


def test_invalid_status_is_rejected(bu_client: TestClient) -> None:
    before = _snapshot(DIG_INDICATOR)
    assert _certify(bu_client, DIG_INDICATOR, "bogus", "").status_code == 422
    assert _snapshot(DIG_INDICATOR) == before


def test_unknown_indicator(bu_client: TestClient) -> None:
    assert _certify(bu_client, "999", "pending", "").status_code == 404


def test_anonymous_cannot_certify(anonymous_client: TestClient) -> None:
    response = _certify(anonymous_client, DIG_INDICATOR, "pending", "")
    assert response.status_code == 303 and response.headers["location"].startswith("/login")


# Périmètre de visibilité ===============================================
def _visible_rows(client: TestClient, **params) -> list[str]:
    import re
    html = client.get("/my-certifications", params=params).text
    return re.findall(r'data-href="/my-certifications/(\d+)"', html)


def test_bu_sees_only_its_business_unit(bu_client: TestClient) -> None:
    ids = _visible_rows(bu_client)
    assert len(ids) == 10
    assert all(repo.get_indicator(i).business_unit.id == "DIG" for i in ids)
    assert '<span id="count-visible">10</span> / 10' in bu_client.get("/my-certifications").text


def test_bu_head_sees_only_its_business_unit(bu_head_client: TestClient) -> None:
    ids = _visible_rows(bu_head_client)
    assert ids and all(repo.get_indicator(i).business_unit.id == "INT" for i in ids)


@pytest.mark.parametrize("fixture", ["user_client", "admin_client"])
def test_cfo_and_admin_see_everything(request, fixture: str) -> None:
    client: TestClient = request.getfixturevalue(fixture)
    assert len(_visible_rows(client)) == len(repo.repoIndicators)


def test_scope_applies_to_category_page(bu_client: TestClient) -> None:
    html = bu_client.get("/my-certifications/category/OPS").text
    import re
    ids = re.findall(r'data-href="/my-certifications/(\d+)"', html)
    assert ids and all(repo.get_indicator(i).business_unit.id == "DIG" for i in ids)


def test_scope_applies_to_detail_page(bu_client: TestClient, bu_head_client: TestClient) -> None:
    assert bu_client.get(f"/my-certifications/{DIG_INDICATOR}").status_code == 200
    assert bu_client.get(f"/my-certifications/{INT_INDICATOR}").status_code == 403
    assert bu_head_client.get(f"/my-certifications/{INT_INDICATOR}").status_code == 200
    assert bu_head_client.get(f"/my-certifications/{DIG_INDICATOR}").status_code == 403


# Édition en ligne depuis la liste ======================================
def _inline_controls(client: TestClient, **params) -> tuple[int, list[str]]:
    import re
    html = client.get("/my-certifications", params=params).text
    triggers = len(re.findall(r'<select name="status" form="certify-', html))
    you = re.findall(r'<th scope="col">(Certification [^<]+?) ?<span class="badge bg-primary">you', html)
    return triggers, you


def test_inline_controls_match_role(bu_client: TestClient, bu_head_client: TestClient, user_client: TestClient) -> None:
    assert _inline_controls(bu_client) == (10, ["Certification BU"])
    assert _inline_controls(bu_head_client) == (10, ["Certification BU head"])
    assert _inline_controls(user_client) == (len(repo.repoIndicators), ["Certification CFO"])


def test_admin_has_no_inline_controls(admin_client: TestClient) -> None:
    assert _inline_controls(admin_client) == (0, [])
    html = admin_client.get("/my-certifications").text
    assert '<input type="hidden" name="comment"' not in html
    assert 'id="comment-modal"' not in html


def test_edit_modals_present_for_certifiers(bu_client: TestClient) -> None:
    html = bu_client.get("/my-certifications").text
    assert html.count('id="comment-modal"') == 1
    assert html.count('data-bs-target="#comment-modal"') == 10
    assert html.count('<select name="status" form="certify-') == 10
    assert html.count('<input type="hidden" name="comment"') == 10


def test_statuses_are_displayed_as_model_values(bu_client: TestClient) -> None:
    html = bu_client.get(f"/my-certifications/{DIG_INDICATOR}").text
    current = repo.get_indicator(DIG_INDICATOR).certification_bu
    assert f'<option value="{current}" selected>{current.replace("_", " ")}</option>' in bu_client.get("/my-certifications").text
    assert "En attente" not in html and "Réserves signif." not in html


def test_inline_certify_returns_to_filtered_list(bu_client: TestClient) -> None:
    response = bu_client.post(
        f"/my-certifications/{DIG_INDICATOR}/certify",
        params={"return_to": "/my-certifications?category=OPS"},
        data={"status": "acceptable", "comment": "depuis la liste"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/my-certifications?category=OPS&saved={DIG_INDICATOR}"

    html = bu_client.get(response.headers["location"]).text
    assert "Certification de l'indicateur" in html
    assert '<option value="acceptable" selected>acceptable</option>' in html
    assert 'value="depuis la liste"' in html
    assert repo.get_indicator(DIG_INDICATOR).comment_bu == "depuis la liste"
    # Le return_to régénéré ne doit pas propager le marqueur saved.
    assert "saved" not in html.split('action="/my-certifications/7/certify?return_to=')[1].split('"')[0]


def test_inline_certify_rejects_external_return_to(bu_client: TestClient) -> None:
    response = bu_client.post(
        f"/my-certifications/{DIG_INDICATOR}/certify",
        params={"return_to": "https://evil.com"},
        data={"status": "pending", "comment": ""},
    )
    assert response.headers["location"] == f"/my-certifications/{DIG_INDICATOR}?saved=1"
