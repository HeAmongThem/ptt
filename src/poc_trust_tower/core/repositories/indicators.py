"""Repo des indicateurs : données de démonstration, requêtes de filtrage et CRUD."""

from datetime import datetime, timedelta
from typing import Literal

from poc_trust_tower.core.model import Category, CertificationStatus, Indicator, User
from poc_trust_tower.core.schemas import IndicatorCreateSchema

from ._base import _NOW, _find, _next_id
from .audits import _record_audit, _record_diff, _snapshot
from .business_units import get_business_unit, repoBusinessUnits
from .categories import repoCategories

VariationFilter = Literal["all", "up", "down", "stable"]

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

def get_indicator(indicator_id: int) -> Indicator:
    return _find(repoIndicators, indicator_id, "indicator")

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


def create_indicator(
    payload: IndicatorCreateSchema,
    actor: User | None = None,
    action: str = "created",
    source_url: str | None = None,
) -> Indicator:
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
    changes = [("", "", indicator.description_action_expected)]
    if source_url:
        # Lien vers le fichier source archivé (ex. dépôt SharePoint du fichier d'import).
        changes.append(("source_file", "", source_url))
    _record_audit(indicator.id, actor, action, changes)
    return indicator


def update_indicator(indicator_id: int, payload: IndicatorCreateSchema, actor: User | None = None) -> Indicator:
    indicator = get_indicator(indicator_id)
    before = _snapshot(indicator)
    _apply_indicator_payload(indicator, payload)
    _record_diff(indicator, before, actor, "updated")
    return indicator


def delete_indicator(indicator_id: int, actor: User | None = None) -> None:
    from .campaign_indicators import repoCampaignIndicators  # import paresseux : évite un cycle

    indicator = get_indicator(indicator_id)
    repoCampaignIndicators[:] = [l for l in repoCampaignIndicators if l.indicateur_id != indicator.id]
    repoIndicators.remove(indicator)
    _record_audit(indicator.id, actor, "deleted", [("", indicator.description_action_expected, "")])
