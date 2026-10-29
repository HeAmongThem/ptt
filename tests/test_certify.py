import pytest
from fastapi.testclient import TestClient

from poc_trust_tower.core import repository as repo

# Indicateur 7 -> BU Digital (id 3), indicateur 23 -> BU International (id 4) ; tous deux en campagne active (T4).
# Indicateur 8 -> BU International, en campagne inactive (T1).
DIG_INDICATOR = 7
INT_INDICATOR = 23
INACTIVE_INT_INDICATOR = 8


def _snapshot(indicator_id: int) -> dict:
    i = repo.get_indicator(indicator_id)
    return {f: getattr(i, f) for pair in repo.CERTIFICATION_FIELDS.values() for f in pair}


def _certify(client: TestClient, indicator_id: int, status: str, comment: str):
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
    assert "Your certification has been saved" in page.text
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
    assert "Your certification — BU</div>" in page.text
    assert 'name="status"' in page.text and 'name="comment"' in page.text
    assert page.text.count('name="status"') == 1  # un seul formulaire, pas un par niveau


def test_invalid_status_is_rejected(bu_client: TestClient) -> None:
    before = _snapshot(DIG_INDICATOR)
    assert _certify(bu_client, DIG_INDICATOR, "bogus", "").status_code == 422
    assert _snapshot(DIG_INDICATOR) == before


def test_unknown_indicator(bu_client: TestClient) -> None:
    assert _certify(bu_client, 999, "pending", "").status_code == 404


def test_anonymous_cannot_certify(anonymous_client: TestClient) -> None:
    response = _certify(anonymous_client, DIG_INDICATOR, "pending", "")
    assert response.status_code == 303 and response.headers["location"].startswith("/login")


# Périmètre de visibilité ===============================================
def _visible_rows(client: TestClient, **params) -> list[str]:
    import re
    html = client.get("/my-certifications", params=params).text
    return [int(i) for i in re.findall(r'data-href="/my-certifications/(\d+)"', html)]


def test_bu_sees_only_its_business_unit(bu_client: TestClient) -> None:
    ids = _visible_rows(bu_client)
    assert len(ids) == 10
    assert all(repo.get_indicator(i).business_unit.id == 3 for i in ids)
    assert '<span id="count-visible">10</span> / 10' in bu_client.get("/my-certifications").text


def test_bu_head_sees_only_its_business_unit(bu_head_client: TestClient) -> None:
    ids = _visible_rows(bu_head_client)
    assert ids and all(repo.get_indicator(i).business_unit.id == 4 for i in ids)


@pytest.mark.parametrize("fixture", ["user_client", "admin_client"])
def test_cfo_and_admin_see_everything(request, fixture: str) -> None:
    client: TestClient = request.getfixturevalue(fixture)
    assert len(_visible_rows(client)) == len(repo.repoIndicators)


def test_scope_applies_to_category_page(bu_client: TestClient) -> None:
    html = bu_client.get("/my-certifications/category/3").text
    import re
    ids = [int(i) for i in re.findall(r'data-href="/my-certifications/(\d+)"', html)]
    assert ids and all(repo.get_indicator(i).business_unit.id == 3 for i in ids)


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


def _active_count(bu_id: int | None = None) -> int:
    return len([
        i for i in repo.repoIndicators
        if repo.indicator_in_active_campaign(i.id) and (bu_id is None or i.business_unit.id == bu_id)
    ])


def test_inline_controls_match_role(bu_client: TestClient, bu_head_client: TestClient, user_client: TestClient) -> None:
    # Un select par ligne éditable ; l'en-tête "you" apparaît une fois par groupe actif.
    assert _inline_controls(bu_client) == (_active_count(3), ["Certification BU"])
    assert _inline_controls(bu_head_client) == (_active_count(4), ["Certification BU head"])
    assert _inline_controls(user_client) == (_active_count(), ["Certification CFO"])


def test_admin_has_no_inline_controls(admin_client: TestClient) -> None:
    assert _inline_controls(admin_client) == (0, [])
    html = admin_client.get("/my-certifications").text
    assert '<input type="hidden" name="comment"' not in html
    assert 'id="comment-modal"' not in html


def test_edit_modals_present_for_certifiers(bu_client: TestClient) -> None:
    html = bu_client.get("/my-certifications").text
    assert html.count('id="comment-modal"') == 1
    assert html.count('data-bs-target="#comment-modal"') == _active_count(3)
    assert html.count('<select name="status" form="certify-') == _active_count(3)
    assert html.count('<input type="hidden" name="comment"') == _active_count(3)


def test_statuses_are_displayed_as_model_values(bu_client: TestClient) -> None:
    html = bu_client.get(f"/my-certifications/{DIG_INDICATOR}").text
    current = repo.get_indicator(DIG_INDICATOR).certification_bu
    assert f'<option value="{current}" selected>{current.replace("_", " ")}</option>' in bu_client.get("/my-certifications").text
    assert "En attente" not in html and "Réserves signif." not in html


def test_inline_certify_returns_to_filtered_list(bu_client: TestClient) -> None:
    response = bu_client.post(
        f"/my-certifications/{DIG_INDICATOR}/certify",
        params={"return_to": "/my-certifications?category=3"},
        data={"status": "acceptable", "comment": "depuis la liste"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/my-certifications?category=3&saved={DIG_INDICATOR}"

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


# Campagnes inactives : lecture seule ===================================
def test_cannot_certify_indicator_of_inactive_campaign(bu_head_client: TestClient, user_client: TestClient) -> None:
    before = _snapshot(INACTIVE_INT_INDICATOR)
    response = _certify(bu_head_client, INACTIVE_INT_INDICATOR, "not_certified", "tentative")
    assert response.status_code == 403
    assert "not part of an active campaign" in response.text
    assert _certify(user_client, INACTIVE_INT_INDICATOR, "not_certified", "").status_code == 403  # même le CFO
    assert _snapshot(INACTIVE_INT_INDICATOR) == before

    page = bu_head_client.get(f"/my-certifications/{INACTIVE_INT_INDICATOR}")
    assert page.status_code == 200 and "/certify" not in page.text


def test_list_is_grouped_by_campaign(user_client: TestClient) -> None:
    import re
    html = user_client.get("/my-certifications").text
    sections = re.findall(r'<section class="campaign-group[^"]*" data-campaign-status="(\w+)" data-campaign="(\d*)">', html)
    assert [s[0] for s in sections][:1] == ["active"]  # les campagnes actives d'abord
    assert {int(s[1]) for s in sections if s[1]} == {c.id for c in repo.repoCampaigns}
    assert html.count('<span class="badge bg-success">active</span>') == len([c for c in repo.repoCampaigns if c.actif])
    assert "lecture seule" in html


def test_inactive_group_rows_are_read_only(user_client: TestClient) -> None:
    import re
    html = user_client.get("/my-certifications").text
    inactive = re.search(r'<section class="campaign-group[^"]*" data-campaign-status="inactive".*?</section>', html, re.S).group(0)
    assert '<select name="status"' not in inactive
    assert 'data-bs-target="#comment-modal"' not in inactive
    active = re.search(r'<section class="campaign-group[^"]*" data-campaign-status="active".*?</section>', html, re.S).group(0)
    assert '<select name="status"' in active


def test_campaign_filters(user_client: TestClient) -> None:
    import re
    def visible_rows(**params):
        html = user_client.get("/my-certifications", params=params).text
        return re.findall(r'<tr\s+class=""\s+role="link".*?data-campaign-status="(\w+)"\s+data-campaign="(\d*)"', html, re.S)

    active_rows = visible_rows(campaign_status="active")
    assert active_rows and all(st == "active" for st, _ in active_rows)
    inactive_rows = visible_rows(campaign_status="inactive")
    assert inactive_rows and all(st == "inactive" for st, _ in inactive_rows)
    assert len(visible_rows()) == len(active_rows) + len(inactive_rows)

    one = visible_rows(campaign=1)
    assert one and all(cid == "1" for _, cid in one)
    assert len(one) == len(repo.campaign_indicator_ids(1))
    assert user_client.get("/my-certifications", params={"campaign": "abc"}).status_code == 422
    assert user_client.get("/my-certifications", params={"campaign": ""}).status_code == 200


# Vue détails / audit sur la fiche ======================================
def test_value_cells_link_to_audit_trail(bu_client: TestClient) -> None:
    html = bu_client.get("/my-certifications").text
    assert f'href="/my-certifications/{DIG_INDICATOR}?view=audit#audit-trail"' in html
    detail = bu_client.get(f"/my-certifications/{DIG_INDICATOR}").text
    assert 'class="text-decoration-none fw-semibold js-show-audit"' in detail


def test_detail_view_menu(bu_client: TestClient) -> None:
    import re
    def visible(view):
        html = bu_client.get(f"/my-certifications/{DIG_INDICATOR}", params={"view": view} if view else {}).text
        details_hidden = re.search(r'id="view-details" class="([^"]*)"', html).group(1)
        audit_hidden = re.search(r'id="view-audit" class="([^"]*)"', html).group(1)
        active = re.search(r'class="nav-link py-1 px-3 active" href="\?view=(\w+)"', html).group(1)
        return ("d-none" not in details_hidden, "d-none" not in audit_hidden, active)

    assert visible(None) == (True, True, "both")       # défaut : les deux cartes
    assert visible("details") == (True, False, "details")
    assert visible("audit") == (False, True, "audit")
    assert bu_client.get(f"/my-certifications/{DIG_INDICATOR}", params={"view": "bogus"}).status_code == 422
