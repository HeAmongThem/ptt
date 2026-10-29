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
from poc_trust_tower.core.security import DEMO_ROUNDS, hash_password
from poc_trust_tower.core.schemas import (
    BusinessUnitCreateSchema,
    CampaignCreateSchema,
    CategoryCreateSchema,
    CertificationSchema,
    IndicatorCreateSchema,
    UserCreateSchema,
    UserUpdateSchema,
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
def _demo_hash(password: str) -> str:
    return hash_password(password, rounds=DEMO_ROUNDS)


def _build_users() -> list[User]:
    users = [
        User(id="1", email="admin@trust-tower.example", password=_demo_hash("aaa"), business_unit=repoBusinessUnits[0], role=ROLE.ADMIN),
        User(id="2", email="cfo@trust-tower.example", password=_demo_hash("aaa"), business_unit=repoBusinessUnits[1], role=ROLE.CFO),
        User(id="3", email="bu@trust-tower.example", password=_demo_hash("aaa"), business_unit=repoBusinessUnits[2], role=ROLE.BU),
        User(id="4", email="buHead@trust-tower.example", password=_demo_hash("aaa"), business_unit=repoBusinessUnits[3], role=ROLE.BU_HEAD),
    ]
    next_id = len(users) + 1
    for bu in repoBusinessUnits:
        slug = bu.id.lower()
        users.append(User(id=str(next_id), email=f"bu.{slug}@trust-tower.example", password=_demo_hash("bu"), business_unit=bu, role=ROLE.BU))
        users.append(User(id=str(next_id + 1), email=f"bu-head.{slug}@trust-tower.example", password=_demo_hash("bu-head"), business_unit=bu, role=ROLE.BU_HEAD))
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

# CRUD ================================================================
class NotFoundError(LookupError):
    pass


class ConflictError(ValueError):
    pass


class ForbiddenError(PermissionError):
    pass


def _next_id(items: list) -> str:
    numeric = [int(i.id) for i in items if i.id.isdigit()]
    return str(max(numeric, default=0) + 1)


def _find(items: list, item_id: str, label: str):
    item = next((i for i in items if i.id == item_id), None)
    if item is None:
        raise NotFoundError(f"{label} {item_id} not found")
    return item


def get_business_unit(bu_id: str) -> BusinessUnit:
    return _find(repoBusinessUnits, bu_id, "business unit")


def get_user(user_id: str) -> User:
    return _find(repoUsers, user_id, "user")


def get_indicator(indicator_id: str) -> Indicator:
    return _find(repoIndicators, indicator_id, "indicator")


def get_campaign(campaign_id: str) -> Campaign:
    return _find(repoCampaigns, campaign_id, "campaign")


# --- Business units ---------------------------------------------------
def _id_from_name(name: str, fallback: list) -> str:
    return "".join(ch for ch in name.upper() if ch.isalnum())[:10] or _next_id(fallback)


def create_business_unit(payload: BusinessUnitCreateSchema) -> BusinessUnit:
    bu_id = _id_from_name(payload.name, repoBusinessUnits)
    if any(bu.id == bu_id for bu in repoBusinessUnits):
        raise ConflictError(f"business unit {bu_id} already exists")
    bu = BusinessUnit(id=bu_id, name=payload.name)
    repoBusinessUnits.append(bu)
    return bu


def update_business_unit(bu_id: str, payload: BusinessUnitCreateSchema) -> BusinessUnit:
    bu = get_business_unit(bu_id)
    bu.name = payload.name
    return bu


def delete_business_unit(bu_id: str) -> None:
    bu = get_business_unit(bu_id)
    if any(u.business_unit is bu for u in repoUsers):
        raise ConflictError(f"business unit {bu_id} is used by users")
    if any(i.business_unit is bu for i in repoIndicators):
        raise ConflictError(f"business unit {bu_id} is used by indicators")
    repoBusinessUnits.remove(bu)


# --- Categories -------------------------------------------------------
def _category_id_from_name(name: str) -> str:
    return _id_from_name(name, repoCategories)


def create_category(payload: CategoryCreateSchema) -> Category:
    category_id = _category_id_from_name(payload.name)
    if any(c.id == category_id for c in repoCategories):
        raise ConflictError(f"category {category_id} already exists")
    category = Category(id=category_id, name=payload.name)
    repoCategories.append(category)
    return category


def update_category(category_id: str, payload: CategoryCreateSchema) -> Category:
    category = _find(repoCategories, category_id, "category")
    category.name = payload.name
    return category


def delete_category(category_id: str) -> None:
    category = _find(repoCategories, category_id, "category")
    if any(i.category is category for i in repoIndicators):
        raise ConflictError(f"category {category_id} is used by indicators")
    repoCategories.remove(category)


# --- Users ------------------------------------------------------------
def create_user(payload: UserCreateSchema) -> User:
    if any(u.email == payload.email for u in repoUsers):
        raise ConflictError(f"user {payload.email} already exists")
    user = User(
        id=_next_id(repoUsers),
        email=payload.email,
        password=hash_password(payload.password),
        business_unit=get_business_unit(payload.business_unit_id),
        role=payload.role,
    )
    repoUsers.append(user)
    return user


def update_user(user_id: str, payload: UserUpdateSchema) -> User:
    user = get_user(user_id)
    if any(u.email == payload.email and u is not user for u in repoUsers):
        raise ConflictError(f"user {payload.email} already exists")
    user.email = payload.email
    user.business_unit = get_business_unit(payload.business_unit_id)
    user.role = payload.role
    if payload.password:
        user.password = hash_password(payload.password)
    return user


def delete_user(user_id: str) -> None:
    repoUsers.remove(get_user(user_id))


# --- Indicators -------------------------------------------------------
def _compute_variation(value: float, value_previous: float) -> float:
    return round((value - value_previous) / value_previous * 100, 2) if value_previous else 0.0


def _apply_indicator_payload(indicator: Indicator, payload: IndicatorCreateSchema) -> None:
    indicator.category = _find(repoCategories, payload.category_id, "category")
    indicator.business_unit = get_business_unit(payload.business_unit_id)
    for field in (
        "nature_of_information", "description_action_expected", "availability_date",
        "validation_committee", "unit", "value", "value_previous", "comment_analysis",
        "thresold_certified_without_reserves", "thresold_acceptable",
        "thresold_certified_with_significant_reserves", "thresold_not_certified",
        "certification_bu", "certification_bu_head", "certification_cfo",
        "comment_emr_id", "comment_bu", "comment_bu_head", "comment_cfo",
    ):
        setattr(indicator, field, getattr(payload, field))
    indicator.variation = _compute_variation(payload.value, payload.value_previous)
    indicator.updated_at = datetime.now()


def create_indicator(payload: IndicatorCreateSchema) -> Indicator:
    now = datetime.now()
    indicator = Indicator(
        id=_next_id(repoIndicators),
        category=_find(repoCategories, payload.category_id, "category"),
        business_unit=get_business_unit(payload.business_unit_id),
        variation=0.0,
        created_at=now,
        updated_at=now,
        **payload.model_dump(exclude={"category_id", "business_unit_id"}),
    )
    indicator.variation = _compute_variation(indicator.value, indicator.value_previous)
    repoIndicators.append(indicator)
    return indicator


def update_indicator(indicator_id: str, payload: IndicatorCreateSchema) -> Indicator:
    indicator = get_indicator(indicator_id)
    _apply_indicator_payload(indicator, payload)
    return indicator


def delete_indicator(indicator_id: str) -> None:
    indicator = get_indicator(indicator_id)
    for campaign in repoCampaigns:
        if indicator in campaign.indicators:
            campaign.indicators.remove(indicator)
    repoIndicators.remove(indicator)


# --- Campaigns --------------------------------------------------------
def _apply_campaign_payload(campaign: Campaign, payload: CampaignCreateSchema) -> None:
    campaign.name = payload.name
    campaign.start_date = payload.start_date
    campaign.end_date = payload.end_date
    campaign.indicators = [get_indicator(i) for i in payload.indicator_ids]


def create_campaign(payload: CampaignCreateSchema) -> Campaign:
    campaign = Campaign(id=_next_id(repoCampaigns), name="", start_date=payload.start_date, end_date=payload.end_date, indicators=[])
    _apply_campaign_payload(campaign, payload)
    repoCampaigns.append(campaign)
    return campaign


def update_campaign(campaign_id: str, payload: CampaignCreateSchema) -> Campaign:
    campaign = get_campaign(campaign_id)
    _apply_campaign_payload(campaign, payload)
    return campaign


def delete_campaign(campaign_id: str) -> None:
    repoCampaigns.remove(get_campaign(campaign_id))


# Certification ========================================================
# Rôle -> (champ statut, champ commentaire) que ce rôle est autorisé à modifier.
CERTIFICATION_FIELDS: dict[ROLE, tuple[str, str]] = {
    ROLE.BU: ("certification_bu", "comment_bu"),
    ROLE.BU_HEAD: ("certification_bu_head", "comment_bu_head"),
    ROLE.CFO: ("certification_cfo", "comment_cfo"),
}


def certification_denial(user: User, indicator: Indicator) -> str | None:
    """Raison pour laquelle l'utilisateur ne peut pas certifier cet indicateur, ou None s'il le peut."""
    if user.role not in CERTIFICATION_FIELDS:
        return f"role {user.role.value} cannot certify indicators"
    if user.role in (ROLE.BU, ROLE.BU_HEAD) and indicator.business_unit is not user.business_unit:
        return f"indicator {indicator.id} belongs to {indicator.business_unit.name}, not {user.business_unit.name}"
    return None


def can_certify(user: User, indicator: Indicator) -> bool:
    return certification_denial(user, indicator) is None


def certify_indicator(indicator_id: str, user: User, payload: CertificationSchema) -> Indicator:
    indicator = get_indicator(indicator_id)
    denial = certification_denial(user, indicator)
    if denial:
        raise ForbiddenError(denial)
    status_field, comment_field = CERTIFICATION_FIELDS[user.role]
    setattr(indicator, status_field, payload.status)
    setattr(indicator, comment_field, payload.comment)
    indicator.updated_at = datetime.now()
    return indicator
