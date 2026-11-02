"""Repo de l'audit trail des indicateurs : enregistrement des changements et requêtes."""

from datetime import datetime, timedelta

from poc_trust_tower.core.model import ROLE, BusinessUnit, Category, Indicator, IndicatorAudit, User

from ._base import _NOW, _add, _next_id

repoIndicatorAudits: list[IndicatorAudit] = []

# Champs suivis lors d'une mise à jour (ordre d'affichage).
AUDITED_FIELDS: tuple[str, ...] = (
    "category", "business_unit", "nature_of_information", "description_action_expected",
    "availability_date", "validation_committee", "unit", "value", "value_previous",
    "comment_analysis", "thresold_certified_without_reserves", "thresold_acceptable",
    "thresold_certified_with_significant_reserves", "thresold_not_certified",
    "certification_bu", "certification_bu_head", "certification_cfo",
    "comment_emr", "comment_bu", "comment_bu_head", "comment_cfo",
)

def _build_audit_seed() -> list[IndicatorAudit]:
    """50 entrées de démonstration : créations par l'admin, certifications par des
    utilisateurs dont le rôle et la BU correspondent à l'indicateur (la dernière
    certification d'un champ reflète le statut courant), quelques mises à jour."""
    from .indicators import _STATUSES, repoIndicators  # import paresseux : le seed dépend des autres repos
    from .users import repoUsers

    admin = repoUsers[0]
    cfo = next(u for u in repoUsers if u.role == ROLE.CFO)
    by_bu_role = {(u.business_unit.id, u.role): u for u in repoUsers if u.role in (ROLE.BU, ROLE.BU_HEAD)}
    entries: list[IndicatorAudit] = []

    def add(indicator: Indicator, actor: User, action: str, field: str, old: str, new: str, days_ago: int, hour: int) -> None:
        entries.append(
            IndicatorAudit(
                id=len(entries) + 1,
                indicator_id=indicator.id,
                user_id=actor.id,
                user_email=actor.email,
                action=action,
                field=field,
                old_value=old,
                new_value=new,
                timestamp=_NOW - timedelta(days=days_ago, hours=-hour),
            )
        )

    # 12 créations (une par indicateur de la campagne active) il y a ~55 jours.
    for n, indicator in enumerate(i for i in repoIndicators if i.id % 4 == 3):
        add(indicator, admin, "created", "", "", indicator.description_action_expected, 55 - n % 3, 9 + n % 4)

    # 30 certifications : statut puis commentaire, par niveau, sur 15 indicateurs.
    levels = [
        (ROLE.BU, "certification_bu", "comment_bu"),
        (ROLE.BU_HEAD, "certification_bu_head", "comment_bu_head"),
        (ROLE.CFO, "certification_cfo", "comment_cfo"),
    ]
    for n, indicator in enumerate(repoIndicators[:15]):
        role, status_field, comment_field = levels[n % 3]
        actor = cfo if role == ROLE.CFO else by_bu_role[(indicator.business_unit.id, role)]
        current = getattr(indicator, status_field)
        previous = _STATUSES[(_STATUSES.index(current) + 2) % len(_STATUSES)]
        days_ago, hour = 2 + (n * 3) % 40, 8 + n % 9
        add(indicator, actor, "certified", status_field, previous, current, days_ago, hour)
        add(indicator, actor, "certified", comment_field, "", getattr(indicator, comment_field), days_ago, hour)

    # 8 mises à jour par l'admin (valeurs précédentes plausibles).
    for n, indicator in enumerate(repoIndicators[20:28]):
        field = ("value", "unit", "validation_committee", "thresold_acceptable")[n % 4]
        new = _audit_repr(getattr(indicator, field))
        old = {"value": _audit_repr(round(indicator.value * 0.9, 2)), "unit": "n/a", "validation_committee": "COMEX",
               "thresold_acceptable": "70.0"}[field]
        if old == new:
            old = old + " (ancien)"
        add(indicator, admin, "updated", field, old, new, 10 + n * 4, 14 + n % 3)

    return entries

def _audit_repr(value) -> str:
    """Représentation textuelle stable d'une valeur pour l'audit."""
    if value is None:
        return ""
    if isinstance(value, (Category, BusinessUnit)):
        return value.name
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)

def _snapshot(indicator: Indicator) -> dict[str, str]:
    return {f: _audit_repr(getattr(indicator, f)) for f in AUDITED_FIELDS}


def _record_audit(indicator_id: int, actor: User | None, action: str, changes: list[tuple[str, str, str]]) -> None:
    now = datetime.now()
    for field, old, new in changes:
        _add(
            "repoIndicatorAudits",
            IndicatorAudit(
                id=_next_id(repoIndicatorAudits),
                indicator_id=indicator_id,
                user_id=actor.id if actor else None,
                user_email=actor.email if actor else "system",
                action=action,
                field=field,
                old_value=old,
                new_value=new,
                timestamp=now,
            ),
        )


def _changes(indicator: Indicator, before: dict[str, str]) -> list[tuple[str, str, str]]:
    """Différences (champ, avant, après) entre l'instantané `before` et l'état courant."""
    after = _snapshot(indicator)
    return [(f, before[f], after[f]) for f in AUDITED_FIELDS if before[f] != after[f]]


def _record_diff(indicator: Indicator, before: dict[str, str], actor: User | None, action: str) -> list[str]:
    changes = _changes(indicator, before)
    _record_audit(indicator.id, actor, action, changes)
    return [c[0] for c in changes]


def indicator_audit_trail(indicator_id: int) -> list[IndicatorAudit]:
    return sorted((a for a in repoIndicatorAudits if a.indicator_id == indicator_id), key=lambda a: (a.timestamp, a.id), reverse=True)


def indicator_source_file(indicator_id: int) -> IndicatorAudit | None:
    """Dernière entrée d'audit référençant le fichier d'import archivé (None si l'indicateur n'a pas été importé)."""
    return next((a for a in indicator_audit_trail(indicator_id) if a.field == "source_file" and a.new_value), None)


def audit_trail(indicator_id: int | None = None, user_id: int | None = None, action: str | None = None, limit: int | None = None) -> list[IndicatorAudit]:
    entries = [
        a for a in repoIndicatorAudits
        if (indicator_id is None or a.indicator_id == indicator_id)
        and (user_id is None or a.user_id == user_id)
        and (not action or a.action == action)
    ]
    entries.sort(key=lambda a: (a.timestamp, a.id), reverse=True)
    return entries[:limit] if limit else entries
