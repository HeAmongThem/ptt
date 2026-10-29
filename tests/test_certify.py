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

    page = bu_client.get(f"/my-certifications/{INT_INDICATOR}")
    assert "Lecture seule" in page.text
    assert "/certify" not in page.text


def test_bu_head_cannot_certify_other_business_unit(bu_head_client: TestClient) -> None:
    assert _certify(bu_head_client, DIG_INDICATOR, "pending", "").status_code == 403


def test_cfo_can_certify_any_business_unit(user_client: TestClient) -> None:
    assert _certify(user_client, INT_INDICATOR, "acceptable", "").status_code == 303
    assert repo.get_indicator(INT_INDICATOR).certification_cfo == "acceptable"


def test_admin_cannot_certify(admin_client: TestClient) -> None:
    assert _certify(admin_client, DIG_INDICATOR, "pending", "").status_code == 403
    page = admin_client.get(f"/my-certifications/{DIG_INDICATOR}")
    assert "/certify" not in page.text and "Lecture seule" not in page.text


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
