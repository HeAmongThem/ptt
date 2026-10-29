import re

import pytest
from fastapi.testclient import TestClient

from poc_trust_tower.core import repository as repo

INDICATOR_FORM = {
    "category_id": "1", "business_unit_id": "1", "nature_of_information": "Quantitatif",
    "description_action_expected": "Audit", "availability_date": "2026-11-01T09:00", "validation_committee": "COMEX",
    "unit": "%", "value": "80", "value_previous": "64", "thresold_certified_without_reserves": "90",
    "thresold_acceptable": "75", "thresold_certified_with_significant_reserves": "60", "thresold_not_certified": "40",
}


def _entries(indicator_id: int, action: str | None = None):
    return [a for a in repo.indicator_audit_trail(indicator_id) if action is None or a.action == action]


def test_certify_records_one_entry_per_changed_field(bu_client: TestClient) -> None:
    indicator = repo.get_indicator(7)
    before = len(repo.repoIndicatorAudits)
    new_status = "not_certified" if indicator.certification_bu != "not_certified" else "pending"
    bu_client.post("/my-certifications/7/certify", data={"status": new_status, "comment": "via audit test"})
    entries = repo.repoIndicatorAudits[before:]
    assert {(a.field, a.action) for a in entries} == {("certification_bu", "certified"), ("comment_bu", "certified")}
    status_entry = next(a for a in entries if a.field == "certification_bu")
    assert status_entry.new_value == new_status and status_entry.user_email == "bu@trust-tower.example"
    assert status_entry.user_id == next(u.id for u in repo.repoUsers if u.email == "bu@trust-tower.example")

    # Même valeurs renvoyées : aucune nouvelle entrée.
    count = len(repo.repoIndicatorAudits)
    bu_client.post("/my-certifications/7/certify", data={"status": new_status, "comment": "via audit test"})
    assert len(repo.repoIndicatorAudits) == count


def test_admin_update_records_diff(admin_client: TestClient) -> None:
    assert admin_client.post("/admin/indicators/new", data=INDICATOR_FORM).status_code == 303
    indicator_id = repo.repoIndicators[-1].id
    created = _entries(indicator_id, "created")
    assert len(created) == 1 and created[0].user_email == "admin@trust-tower.example"

    admin_client.post(f"/admin/indicators/{indicator_id}", data={**INDICATOR_FORM, "value": "90", "unit": "EUR", "category_id": "2"})
    updated = {a.field: (a.old_value, a.new_value) for a in _entries(indicator_id, "updated")}
    assert updated["value"] == ("80.0", "90.0")
    assert updated["unit"] == ("%", "EUR")
    assert updated["category"] == ("Finance", "RH")  # objets rendus par leur nom
    assert "description_action_expected" not in updated  # inchangé -> pas d'entrée

    admin_client.post(f"/admin/indicators/{indicator_id}/delete")
    deleted = _entries(indicator_id, "deleted")
    assert len(deleted) == 1 and deleted[0].old_value == "Audit"


def test_import_records_imported_entries(admin_client: TestClient) -> None:
    content = admin_client.get("/admin/indicators/import/template.csv").content
    before = len(repo.repoIndicators)
    admin_client.post("/admin/indicators/import", files={"file": ("indicateurs.csv", content)})
    indicator_id = repo.repoIndicators[-1].id
    assert len(repo.repoIndicators) == before + 1
    entries = _entries(indicator_id, "imported")
    assert len(entries) == 1 and entries[0].user_email == "admin@trust-tower.example"
    repo.delete_indicator(indicator_id)


def test_detail_page_shows_audit_trail(bu_client: TestClient) -> None:
    bu_client.post("/my-certifications/7/certify", data={"status": "acceptable", "comment": "visible dans la fiche"})
    html = bu_client.get("/my-certifications/7").text
    assert 'id="audit-trail"' in html
    assert "visible dans la fiche" in html
    assert "bu@trust-tower.example" in html.split('id="audit-trail"')[1]


def test_admin_audit_tab_and_filters(admin_client: TestClient, bu_client: TestClient) -> None:
    bu_client.post("/my-certifications/7/certify", data={"status": "pending", "comment": "filtre audit"})
    bu_id = next(u.id for u in repo.repoUsers if u.email == "bu@trust-tower.example")

    html = admin_client.get("/admin", params={"tab": "audit"}).text
    assert 'class="nav-link active" href="/admin?tab=audit"' in html
    assert f"/ {len(repo.repoIndicatorAudits)} entrée(s)" in html

    html = admin_client.get("/admin", params={"tab": "audit", "audit_indicator": 7, "audit_user": bu_id, "audit_action": "certified"}).text
    rows = re.findall(r'<td><a href="/my-certifications/(\d+)">', html)
    assert rows and set(rows) == {"7"}
    assert "filtre audit" in html
    body = html.split("<tbody>")[1]
    assert ">updated<" not in body and ">created<" not in body

    html = admin_client.get("/admin", params={"tab": "audit", "audit_indicator": 999999}).text
    assert "Aucune entrée d'audit." in html


def test_audit_tab_requires_admin(user_client: TestClient) -> None:
    assert user_client.get("/admin", params={"tab": "audit"}).status_code == 403


def test_deleted_indicator_id_is_never_reused(admin_client: TestClient) -> None:
    assert admin_client.post("/admin/indicators/new", data=INDICATOR_FORM).status_code == 303
    first_id = repo.repoIndicators[-1].id
    admin_client.post(f"/admin/indicators/{first_id}/delete")
    assert admin_client.post("/admin/indicators/new", data=INDICATOR_FORM).status_code == 303
    second_id = repo.repoIndicators[-1].id
    assert second_id > first_id
    assert [a.action for a in _entries(first_id)] == ["deleted", "created"]
    admin_client.post(f"/admin/indicators/{second_id}/delete")
