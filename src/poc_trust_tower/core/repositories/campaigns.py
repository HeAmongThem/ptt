"""Repo des campagnes (les liens vers les indicateurs sont dans campaign_indicators)."""

from datetime import datetime, timedelta

from poc_trust_tower.core.model import Campaign
from poc_trust_tower.core.schemas import CampaignCreateSchema

from ._base import _NOW, _add, _find, _next_id, _remove, _save

def _build_campaigns() -> list[Campaign]:
    campaigns: list[Campaign] = []
    for quarter in range(4):
        start = datetime(2026, 1 + quarter * 3, 1)
        end = datetime(2026 + (quarter == 3), (1 + (quarter + 1) * 3) % 12 or 12, 1) - timedelta(days=1)
        campaigns.append(
            Campaign(
                id=quarter + 1,
                name=f"Campagne T{quarter + 1} 2026",
                start_date=start,
                end_date=end,
                actif=start <= _NOW <= end,
            )
        )
    return campaigns


repoCampaigns: list[Campaign] = _build_campaigns()

def get_campaign(campaign_id: int) -> Campaign:
    return _find(repoCampaigns, campaign_id, "campaign")

def create_campaign(payload: CampaignCreateSchema) -> Campaign:
    from .campaign_indicators import _set_campaign_links  # import paresseux : évite un cycle

    campaign = Campaign(
        id=_next_id(repoCampaigns),
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        actif=payload.actif,
    )
    campaign = _add("repoCampaigns", campaign)
    _set_campaign_links(campaign.id, payload.indicator_ids)
    return get_campaign(campaign.id)


def update_campaign(campaign_id: int, payload: CampaignCreateSchema) -> Campaign:
    from .campaign_indicators import _set_campaign_links  # import paresseux : évite un cycle

    campaign = get_campaign(campaign_id)
    campaign.name = payload.name
    campaign.start_date = payload.start_date
    campaign.end_date = payload.end_date
    campaign.actif = payload.actif
    campaign = _save("repoCampaigns", campaign)
    _set_campaign_links(campaign.id, payload.indicator_ids)
    return get_campaign(campaign.id)


def delete_campaign(campaign_id: int) -> None:
    from .campaign_indicators import repoCampaignIndicators  # import paresseux : évite un cycle

    campaign = get_campaign(campaign_id)
    for link in [l for l in repoCampaignIndicators if l.campain_id == campaign.id]:
        _remove("repoCampaignIndicators", link)
    _remove("repoCampaigns", campaign)

def active_campaigns() -> list[Campaign]:
    """Campagnes marquées actives (drapeau `actif`), triées par date de fin."""
    return sorted((c for c in repoCampaigns if c.actif), key=lambda c: c.end_date)
