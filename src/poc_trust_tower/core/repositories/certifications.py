"""Règles de certification et de visibilité des indicateurs selon le rôle."""

from datetime import datetime

from poc_trust_tower.core.model import ROLE, Indicator, User
from poc_trust_tower.core.schemas import CertificationSchema

from ._base import ForbiddenError
from .audits import _record_diff, _snapshot
from .campaign_indicators import indicator_in_active_campaign
from .indicators import get_indicator, repoIndicators

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
    if not indicator_in_active_campaign(indicator.id):
        return f"indicator {indicator.id} is not part of an active campaign"
    return None


def can_certify(user: User, indicator: Indicator) -> bool:
    return certification_denial(user, indicator) is None


def certify_indicator(indicator_id: int, user: User, payload: CertificationSchema) -> Indicator:
    indicator = get_indicator(indicator_id)
    denial = certification_denial(user, indicator)
    if denial:
        raise ForbiddenError(denial)
    status_field, comment_field = CERTIFICATION_FIELDS[user.role]
    before = _snapshot(indicator)
    setattr(indicator, status_field, payload.status)
    setattr(indicator, comment_field, payload.comment)
    if _record_diff(indicator, before, user, "certified"):
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
