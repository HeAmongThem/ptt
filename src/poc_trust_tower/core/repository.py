from datetime import datetime, timedelta
from typing import Literal

from poc_trust_tower.core.model import Indicator

VariationFilter = Literal["all", "up", "down", "stable"]

_CATEGORIES = ["Finance", "RH", "Operations", "Risques", "Conformite"]
_NATURES = ["Quantitatif", "Qualitatif", "Reglementaire", "Pilotage"]
_COMMITTEES = ["COMEX", "Comite des risques", "Comite d'audit", "Comite financier"]
_UNITS = ["%", "EUR", "jours", "nombre", "ratio"]
_BUS = ["BU Retail", "BU Corporate", "BU Digital", "BU International", "BU Services"]
_STATUSES = ["Certifie", "Certifie avec reserves", "Non certifie", "En attente"]


def _build_indicator(index: int) -> Indicator:
    now = datetime(2026, 10, 1, 9, 0, 0)
    value = round(50 + (index * 7) % 60 + index / 10, 2)
    value_previous = round(value - ((index % 11) - 5) * 1.5, 2)
    variation = round((value - value_previous) / value_previous * 100, 2) if value_previous else 0.0
    return Indicator(
        id=f"{index}",
        category=_CATEGORIES[index % len(_CATEGORIES)],
        nature_of_information=_NATURES[index % len(_NATURES)],
        description_action_expected=f"Suivi de l'indicateur {index} et plan d'action associe",
        availability_date=now + timedelta(days=index % 30),
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
        created_at=now - timedelta(days=60 - index),
        updated_at=now - timedelta(days=(index % 7)),
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
    category: str | None = None,
    variation: VariationFilter = "all",
    bu: str | None = None,
    bu_head: str | None = None,
    cfo: str | None = None,
) -> list[Indicator]:
    return [
        i
        for i in indicators
        if (not category or i.category == category)
        and (variation == "all" or variation_kind(i) == variation)
        and (not bu or i.certification_bu == bu)
        and (not bu_head or i.certification_bu_head == bu_head)
        and (not cfo or i.certification_cfo == cfo)
    ]


def distinct_categories(indicators: list[Indicator]) -> list[str]:
    return sorted({i.category for i in indicators})


def distinct_statuses(indicators: list[Indicator]) -> list[str]:
    return sorted(
        {i.certification_bu for i in indicators}
        | {i.certification_bu_head for i in indicators}
        | {i.certification_cfo for i in indicators}
    )
