from datetime import datetime, timedelta
from typing import Literal

from poc_trust_tower.core.model import (
    ROLE,
    BusinessUnit,
    Campaign,
    Category,
    CertificationStatus,
    Indicator,
    User,
)

VariationFilter = Literal["all", "up", "down", "stable"]

_NOW = datetime(2026, 10, 1, 9, 0, 0)

# Business units ======================================================
repoBusinessUnits: list[BusinessUnit] = [
    BusinessUnit(id="RET", name="BU Retail"),
    BusinessUnit(id="CORP", name="BU Corporate"),
    BusinessUnit(id="DIG", name="BU Digital"),
    BusinessUnit(id="INT", name="BU International"),
    BusinessUnit(id="SERV", name="BU Services"),
]

# Categories ==========================================================
repoCategories: list[Category] = [
    Category(id="FIN", name="Finance"),
    Category(id="RH", name="RH"),
    Category(id="OPS", name="Operations"),
    Category(id="RSK", name="Risques"),
    Category(id="CONF", name="Conformite"),
]

# Users ===============================================================
def _build_users() -> list[User]:
    users = [
        User(id="1", email="admin@trust-tower.example", password="admin", business_unit=repoBusinessUnits[0], role=ROLE.ADMIN),
        User(id="2", email="cfo@trust-tower.example", password="cfo", business_unit=repoBusinessUnits[0], role=ROLE.CFO),
    ]
    next_id = len(users) + 1
    for bu in repoBusinessUnits:
        slug = bu.id.lower()
        users.append(User(id=str(next_id), email=f"bu.{slug}@trust-tower.example", password="bu", business_unit=bu, role=ROLE.BU))
        users.append(User(id=str(next_id + 1), email=f"bu-head.{slug}@trust-tower.example", password="bu-head", business_unit=bu, role=ROLE.BU_HEAD))
        next_id += 2
    return users


repoUsers: list[User] = _build_users()

# Indicators ==========================================================
_NATURES = ["Quantitatif", "Qualitatif", "Reglementaire", "Pilotage"]
_COMMITTEES = ["COMEX", "Comite des risques", "Comite d'audit", "Comite financier"]
_UNITS = ["%", "EUR", "jours", "nombre", "ratio"]
_STATUSES = [s.name for s in CertificationStatus]


def _build_indicator(index: int) -> Indicator:
    value = round(50 + (index * 7) % 60 + index / 10, 2)
    value_previous = round(value - ((index % 11) - 5) * 1.5, 2)
    variation = round((value - value_previous) / value_previous * 100, 2) if value_previous else 0.0
    return Indicator(
        id=f"{index}",
        category=repoCategories[index % len(repoCategories)],
        nature_of_information=_NATURES[index % len(_NATURES)],
        description_action_expected=f"Suivi de l'indicateur {index} et plan d'action associe",
        availability_date=_NOW + timedelta(days=index % 30),
        validation_committee=_COMMITTEES[index % len(_COMMITTEES)],
        unit=_UNITS[index % len(_UNITS)],
        value=value,
        value_previous=value_previous,
        variation=variation,
        comment_analysis=f"Analyse de la tendance de l'indicateur {index}",
        thresold_certified_without_reserves=90.0,
        thresold_acceptable=75.0,
        thresold_certified_with_significant_reserves=60.0,
        thresold_not_certified=40.0,
        certification_bu=_STATUSES[index % len(_STATUSES)],
        certification_bu_head=_STATUSES[index % len(_STATUSES)],
        certification_cfo=_STATUSES[(index + 1) % len(_STATUSES)],
        comment_emr_id=f"EMR-{1000 + index}",
        comment_bu=f"Commentaire BU sur l'indicateur {index}",
        comment_bu_head=f"Commentaire du responsable BU sur l'indicateur {index}",
        comment_cfo=f"Commentaire CFO sur l'indicateur {index}",
        business_unit=repoBusinessUnits[index % len(repoBusinessUnits)],
        created_at=_NOW - timedelta(days=60 - index),
        updated_at=_NOW - timedelta(days=(index % 7)),
    )


repoIndicators: list[Indicator] = [_build_indicator(i) for i in range(1, 51)]

# Campaigns ===========================================================
def _build_campaigns() -> list[Campaign]:
    campaigns: list[Campaign] = []
    for quarter in range(4):
        start = datetime(2026, 1 + quarter * 3, 1)
        end = datetime(2026 + (quarter == 3), (1 + (quarter + 1) * 3) % 12 or 12, 1) - timedelta(days=1)
        campaigns.append(
            Campaign(
                id=str(quarter + 1),
                name=f"Campagne T{quarter + 1} 2026",
                start_date=start,
                end_date=end,
                indicators=[i for i in repoIndicators if int(i.id) % 4 == quarter],
            )
        )
    return campaigns


repoCampaigns: list[Campaign] = _build_campaigns()

# Queries =============================================================
def get_category(category_id: str) -> Category | None:
    return next((c for c in repoCategories if c.id == category_id), None)


def variation_kind(indicator: Indicator) -> VariationFilter:
    if indicator.variation > 0:
        return "up"
    if indicator.variation < 0:
        return "down"
    return "stable"


def filter_indicators(
    indicators: list[Indicator],
    *,
    category: str | None = None,
    variation: VariationFilter = "all",
    bu: str | None = None,
    bu_head: str | None = None,
    cfo: str | None = None,
) -> list[Indicator]:
    return [
        i
        for i in indicators
        if (not category or i.category.id == category)
        and (variation == "all" or variation_kind(i) == variation)
        and (not bu or i.certification_bu == bu)
        and (not bu_head or i.certification_bu_head == bu_head)
        and (not cfo or i.certification_cfo == cfo)
    ]


def distinct_categories(indicators: list[Indicator]) -> list[Category]:
    return sorted({i.category.id: i.category for i in indicators}.values(), key=lambda c: c.name)


def distinct_statuses(indicators: list[Indicator]) -> list[str]:
    return sorted(
        {i.certification_bu for i in indicators}
        | {i.certification_bu_head for i in indicators}
        | {i.certification_cfo for i in indicators}
    )
