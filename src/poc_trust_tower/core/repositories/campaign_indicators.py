"""Repo d'association campagnes <-> indicateurs : seule source de vérité des liens."""

from poc_trust_tower.core.model import Campaign, CampaignIndicator, Indicator
from poc_trust_tower.core.schemas import CampaignIndicatorCreateSchema, CampaignIndicatorsSchema

from ._base import ConflictError, NotFoundError
from .campaigns import get_campaign, repoCampaigns
from .indicators import get_indicator, repoIndicators

repoCampaignIndicators: list[CampaignIndicator] = [
    CampaignIndicator(campain_id=c.id, indicateur_id=i.id)
    for c in repoCampaigns
    for i in repoIndicators
    if i.id % 4 == c.id - 1
]


def campaign_indicator_ids(campaign_id: int) -> list[int]:
    return [l.indicateur_id for l in repoCampaignIndicators if l.campain_id == campaign_id]


def campaign_indicators(campaign: Campaign | int) -> list[Indicator]:
    campaign_id = campaign if isinstance(campaign, int) else campaign.id
    by_id = {i.id: i for i in repoIndicators}
    return [by_id[i] for i in campaign_indicator_ids(campaign_id) if i in by_id]


def campaigns_of_indicator(indicator_id: int) -> list[Campaign]:
    ids = {l.campain_id for l in repoCampaignIndicators if l.indicateur_id == indicator_id}
    return [c for c in repoCampaigns if c.id in ids]


def indicator_in_active_campaign(indicator_id: int) -> bool:
    return any(c.actif for c in campaigns_of_indicator(indicator_id))


def campaign_indicator_counts() -> dict[int, int]:
    counts: dict[int, int] = {c.id: 0 for c in repoCampaigns}
    for link in repoCampaignIndicators:
        counts[link.campain_id] = counts.get(link.campain_id, 0) + 1
    return counts

def _set_campaign_links(campaign_id: int, indicator_ids: list[int]) -> None:
    """Remplace les liens d'une campagne (doublons ignorés, ordre conservé, 404 si indicateur inconnu)."""
    indicators = [get_indicator(i) for i in dict.fromkeys(indicator_ids)]
    repoCampaignIndicators[:] = [l for l in repoCampaignIndicators if l.campain_id != campaign_id] + [
        CampaignIndicator(campain_id=campaign_id, indicateur_id=i.id) for i in indicators
    ]

def campaign_indicator_links() -> list[tuple[CampaignIndicator, Campaign, Indicator]]:
    """Liens résolus (lien, campagne, indicateur), triés par campagne puis indicateur."""
    campaigns = {c.id: c for c in repoCampaigns}
    indicators = {i.id: i for i in repoIndicators}
    resolved = [
        (link, campaigns[link.campain_id], indicators[link.indicateur_id])
        for link in repoCampaignIndicators
        if link.campain_id in campaigns and link.indicateur_id in indicators
    ]
    return sorted(resolved, key=lambda t: (t[1].id, t[2].id))


def add_campaign_indicator(payload: CampaignIndicatorCreateSchema) -> CampaignIndicator:
    campaign = get_campaign(payload.campain_id)
    indicator = get_indicator(payload.indicateur_id)
    if any(l.campain_id == campaign.id and l.indicateur_id == indicator.id for l in repoCampaignIndicators):
        raise ConflictError(f"indicator {indicator.id} is already in campaign {campaign.id}")
    link = CampaignIndicator(campain_id=campaign.id, indicateur_id=indicator.id)
    repoCampaignIndicators.append(link)
    return link


def set_campaign_indicators(campaign_id: int, payload: CampaignIndicatorsSchema) -> Campaign:
    """Remplace l'ensemble des indicateurs d'une campagne (doublons ignorés, ordre conservé)."""
    campaign = get_campaign(campaign_id)
    _set_campaign_links(campaign.id, payload.indicator_ids)
    return campaign


def remove_campaign_indicator(campaign_id: int, indicator_id: int) -> None:
    get_campaign(campaign_id)  # 404 si la campagne n'existe pas
    link = next((l for l in repoCampaignIndicators if l.campain_id == campaign_id and l.indicateur_id == indicator_id), None)
    if link is None:
        raise NotFoundError(f"indicator {indicator_id} is not in campaign {campaign_id}")
    repoCampaignIndicators.remove(link)
