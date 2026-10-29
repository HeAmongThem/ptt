from datetime import datetime

from fastapi.testclient import TestClient

from poc_trust_tower.core import repository as repo
from poc_trust_tower.core.schemas import SettingsSchema


def test_active_campaigns_by_date() -> None:
    assert [c.name for c in repo.active_campaigns(datetime(2026, 2, 15))] == ["Campagne T1 2026"]
    assert [c.name for c in repo.active_campaigns(datetime(2026, 12, 31))] == ["Campagne T4 2026"]
    assert repo.active_campaigns(datetime(2030, 1, 1)) == []


def test_home_shows_message_and_active_campaigns(anonymous_client: TestClient) -> None:
    html = anonymous_client.get("/").text
    assert "Application POC Trust Tower." in html
    assert "suivi de certification d" in html
    for campaign in repo.active_campaigns():
        assert campaign.name in html
        assert campaign.start_date.strftime("%d/%m/%Y") in html
        assert campaign.end_date.strftime("%d/%m/%Y") in html


def test_home_message_is_configurable_from_admin(admin_client: TestClient, anonymous_client: TestClient) -> None:
    original = repo.get_home_message()
    try:
        assert 'id="f-home-message"' in admin_client.get("/admin?tab=settings").text
        response = admin_client.post("/admin/settings", data={"home_message": "  Nouveau message.  "})
        assert response.status_code == 303 and response.headers["location"] == "/admin?tab=settings"
        assert repo.get_home_message() == "Nouveau message."
        assert "Nouveau message." in anonymous_client.get("/").text
        assert admin_client.post("/admin/settings", data={"home_message": ""}).status_code == 422
    finally:
        repo.update_settings(SettingsSchema(home_message=original))


def test_home_message_requires_admin(user_client: TestClient, anonymous_client: TestClient) -> None:
    assert user_client.post("/admin/settings", data={"home_message": "x"}).status_code == 403
    assert anonymous_client.post("/admin/settings", data={"home_message": "x"}).status_code == 303
