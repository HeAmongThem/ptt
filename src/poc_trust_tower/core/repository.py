from datetime import datetime, timedelta
from typing import Literal

from poc_trust_tower.core.model import (
    ROLE,
    BusinessUnit,
    Campaign,
    CampaignIndicator,
    Category,
    CertificationStatus,
    Indicator,
    User,
)
from poc_trust_tower.core.security import DEMO_ROUNDS, hash_password
from poc_trust_tower.core.schemas import (
    BusinessUnitCreateSchema,
    CampaignCreateSchema,
    CampaignIndicatorCreateSchema,
    CampaignIndicatorsSchema,
    CategoryCreateSchema,
    CertificationSchema,
    IndicatorCreateSchema,
    SettingsSchema,
    UserCreateSchema,
    UserUpdateSchema,
)

VariationFilter = Literal["all", "up", "down", "stable"]

_NOW = datetime(2026, 10, 1, 9, 0, 0)

# Business units ======================================================
# (slug utilisé pour les emails de démonstration, nom)
_BU_SEED = [("ret", "BU Retail"), ("corp", "BU Corporate"), ("dig", "BU Digital"), ("int", "BU International"), ("serv", "BU Services")]
repoBusinessUnits: list[BusinessUnit] = [
    BusinessUnit(id=index, name=name) for index, (_, name) in enumerate(_BU_SEED, start=1)
]

# Categories ==========================================================
repoCategories: list[Category] = [
    Category(id=index, name=name)
    for index, name in enumerate(["Finance", "RH", "Operations", "Risques", "Conformite"], start=1)
]

# Users ===============================================================
def _demo_hash(password: str) -> str:
    return hash_password(password, rounds=DEMO_ROUNDS)


def _build_users() -> list[User]:
    users = [
        User(id=1, email="admin@trust-tower.example", password=_demo_hash("aaa"), business_unit=repoBusinessUnits[0], role=ROLE.ADMIN),
        User(id=2, email="cfo@trust-tower.example", password=_demo_hash("aaa"), business_unit=repoBusinessUnits[1], role=ROLE.CFO),
        User(id=3, email="bu@trust-tower.example", password=_demo_hash("aaa"), business_unit=repoBusinessUnits[2], role=ROLE.BU),
        User(id=4, email="buHead@trust-tower.example", password=_demo_hash("aaa"), business_unit=repoBusinessUnits[3], role=ROLE.BU_HEAD),
    ]
    next_id = len(users) + 1
    for (slug, _), bu in zip(_BU_SEED, repoBusinessUnits):
        users.append(User(id=next_id, email=f"bu.{slug}@trust-tower.example", password=_demo_hash("bu"), business_unit=bu, role=ROLE.BU))
        users.append(User(id=next_id + 1, email=f"bu-head.{slug}@trust-tower.example", password=_demo_hash("bu-head"), business_unit=bu, role=ROLE.BU_HEAD))
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
        id=index,
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
        comment_emr=f"EMR-{1000 + index}",
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
                id=quarter + 1,
                name=f"Campagne T{quarter + 1} 2026",
                start_date=start,
                end_date=end,
                actif=start <= _NOW <= end,
            )
        )
    return campaigns


repoCampaigns: list[Campaign] = _build_campaigns()

# Campaign indicators (table d'association, seule source des liens) =====
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


def campaign_indicator_counts() -> dict[int, int]:
    counts: dict[int, int] = {c.id: 0 for c in repoCampaigns}
    for link in repoCampaignIndicators:
        counts[link.campain_id] = counts.get(link.campain_id, 0) + 1
    return counts

# Queries =============================================================
def get_category(category_id: int) -> Category | None:
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
    category: int | None = None,
    variation: VariationFilter = "all",
    bu: str | None = None,
    bu_head: str | None = None,
    cfo: str | None = None,
) -> list[Indicator]:
    return [
        i
        for i in indicators
        if (category is None or i.category.id == category)
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


def _next_id(items: list) -> int:
    return max((i.id for i in items), default=0) + 1


def _find(items: list, item_id: int, label: str):
    item = next((i for i in items if i.id == item_id), None)
    if item is None:
        raise NotFoundError(f"{label} {item_id} not found")
    return item


def get_business_unit(bu_id: int) -> BusinessUnit:
    return _find(repoBusinessUnits, bu_id, "business unit")


def get_user(user_id: int) -> User:
    return _find(repoUsers, user_id, "user")


def get_indicator(indicator_id: int) -> Indicator:
    return _find(repoIndicators, indicator_id, "indicator")


def get_campaign(campaign_id: int) -> Campaign:
    return _find(repoCampaigns, campaign_id, "campaign")


# --- Business units ---------------------------------------------------
def _name_taken(items: list, name: str, exclude=None) -> bool:
    return any(i.name.casefold() == name.casefold() and i is not exclude for i in items)


def create_business_unit(payload: BusinessUnitCreateSchema) -> BusinessUnit:
    if _name_taken(repoBusinessUnits, payload.name):
        raise ConflictError(f"business unit '{payload.name}' already exists")
    bu = BusinessUnit(id=_next_id(repoBusinessUnits), name=payload.name)
    repoBusinessUnits.append(bu)
    return bu


def update_business_unit(bu_id: int, payload: BusinessUnitCreateSchema) -> BusinessUnit:
    bu = get_business_unit(bu_id)
    if _name_taken(repoBusinessUnits, payload.name, exclude=bu):
        raise ConflictError(f"business unit '{payload.name}' already exists")
    bu.name = payload.name
    return bu


def delete_business_unit(bu_id: int) -> None:
    bu = get_business_unit(bu_id)
    if any(u.business_unit is bu for u in repoUsers):
        raise ConflictError(f"business unit {bu_id} is used by users")
    if any(i.business_unit is bu for i in repoIndicators):
        raise ConflictError(f"business unit {bu_id} is used by indicators")
    repoBusinessUnits.remove(bu)


# --- Categories -------------------------------------------------------
def create_category(payload: CategoryCreateSchema) -> Category:
    if _name_taken(repoCategories, payload.name):
        raise ConflictError(f"category '{payload.name}' already exists")
    category = Category(id=_next_id(repoCategories), name=payload.name)
    repoCategories.append(category)
    return category


def update_category(category_id: int, payload: CategoryCreateSchema) -> Category:
    category = _find(repoCategories, category_id, "category")
    if _name_taken(repoCategories, payload.name, exclude=category):
        raise ConflictError(f"category '{payload.name}' already exists")
    category.name = payload.name
    return category


def delete_category(category_id: int) -> None:
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


def update_user(user_id: int, payload: UserUpdateSchema) -> User:
    user = get_user(user_id)
    if any(u.email == payload.email and u is not user for u in repoUsers):
        raise ConflictError(f"user {payload.email} already exists")
    user.email = payload.email
    user.business_unit = get_business_unit(payload.business_unit_id)
    user.role = payload.role
    if payload.password:
        user.password = hash_password(payload.password)
    return user


def delete_user(user_id: int) -> None:
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
        "comment_emr", "comment_bu", "comment_bu_head", "comment_cfo",
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


def update_indicator(indicator_id: int, payload: IndicatorCreateSchema) -> Indicator:
    indicator = get_indicator(indicator_id)
    _apply_indicator_payload(indicator, payload)
    return indicator


def delete_indicator(indicator_id: int) -> None:
    indicator = get_indicator(indicator_id)
    repoCampaignIndicators[:] = [l for l in repoCampaignIndicators if l.indicateur_id != indicator.id]
    repoIndicators.remove(indicator)


# --- Campaigns --------------------------------------------------------
def _set_campaign_links(campaign_id: int, indicator_ids: list[int]) -> None:
    """Remplace les liens d'une campagne (doublons ignorés, ordre conservé, 404 si indicateur inconnu)."""
    indicators = [get_indicator(i) for i in dict.fromkeys(indicator_ids)]
    repoCampaignIndicators[:] = [l for l in repoCampaignIndicators if l.campain_id != campaign_id] + [
        CampaignIndicator(campain_id=campaign_id, indicateur_id=i.id) for i in indicators
    ]


def _apply_campaign_payload(campaign: Campaign, payload: CampaignCreateSchema) -> None:
    campaign.name = payload.name
    campaign.start_date = payload.start_date
    campaign.end_date = payload.end_date
    campaign.actif = payload.actif
    _set_campaign_links(campaign.id, payload.indicator_ids)


def create_campaign(payload: CampaignCreateSchema) -> Campaign:
    campaign = Campaign(
        id=_next_id(repoCampaigns),
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        actif=payload.actif,
    )
    repoCampaigns.append(campaign)
    _set_campaign_links(campaign.id, payload.indicator_ids)
    return campaign


def update_campaign(campaign_id: int, payload: CampaignCreateSchema) -> Campaign:
    campaign = get_campaign(campaign_id)
    _apply_campaign_payload(campaign, payload)
    return campaign


def delete_campaign(campaign_id: int) -> None:
    campaign = get_campaign(campaign_id)
    repoCampaignIndicators[:] = [l for l in repoCampaignIndicators if l.campain_id != campaign.id]
    repoCampaigns.remove(campaign)


# --- Campaign indicators ----------------------------------------------
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
    campaign = get_campaign(campaign_id)
    link = next((l for l in repoCampaignIndicators if l.campain_id == campaign_id and l.indicateur_id == indicator_id), None)
    if link is None:
        raise NotFoundError(f"indicator {indicator_id} is not in campaign {campaign_id}")
    repoCampaignIndicators.remove(link)


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


def certify_indicator(indicator_id: int, user: User, payload: CertificationSchema) -> Indicator:
    indicator = get_indicator(indicator_id)
    denial = certification_denial(user, indicator)
    if denial:
        raise ForbiddenError(denial)
    status_field, comment_field = CERTIFICATION_FIELDS[user.role]
    setattr(indicator, status_field, payload.status)
    setattr(indicator, comment_field, payload.comment)
    indicator.updated_at = datetime.now()
    return indicator


# Périmètre de visibilité ==============================================
def can_view_indicator(user: User, indicator: Indicator) -> bool:
    """BU et BU_HEAD ne voient que leur business unit ; CFO et ADMIN voient tout."""
    if user.role in (ROLE.BU, ROLE.BU_HEAD):
        return indicator.business_unit is user.business_unit
    return True


def visible_indicators(user: User) -> list[Indicator]:
    return [i for i in repoIndicators if can_view_indicator(user, i)]


# Settings ==============================================================
DEFAULT_HOME_MESSAGE = (
    "Application POC Trust Tower. "
    "Un outil d'aide et de suivi de certification d'indicateurs."
)

repoSettings: dict[str, str] = {"home_message": DEFAULT_HOME_MESSAGE}


def get_home_message() -> str:
    return repoSettings["home_message"]


def update_settings(payload: SettingsSchema) -> None:
    repoSettings["home_message"] = payload.home_message.strip()


# Campagnes actives =====================================================
def active_campaigns() -> list[Campaign]:
    """Campagnes marquées actives (drapeau `actif`), triées par date de fin."""
    return sorted((c for c in repoCampaigns if c.actif), key=lambda c: c.end_date)
