"""Repo des business units."""

from poc_trust_tower.core.model import BusinessUnit
from poc_trust_tower.core.schemas import BusinessUnitCreateSchema

from ._base import ConflictError, _find, _name_taken, _next_id

# (slug utilisé pour les emails de démonstration, nom)
_BU_SEED = [("ret", "BU Retail"), ("corp", "BU Corporate"), ("dig", "BU Digital"), ("int", "BU International"), ("serv", "BU Services")]
repoBusinessUnits: list[BusinessUnit] = [
    BusinessUnit(id=index, name=name) for index, (_, name) in enumerate(_BU_SEED, start=1)
]

def get_business_unit(bu_id: int) -> BusinessUnit:
    return _find(repoBusinessUnits, bu_id, "business unit")

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
    from .indicators import repoIndicators  # import paresseux : évite un cycle
    from .users import repoUsers

    bu = get_business_unit(bu_id)
    if any(u.business_unit is bu for u in repoUsers):
        raise ConflictError(f"business unit {bu_id} is used by users")
    if any(i.business_unit is bu for i in repoIndicators):
        raise ConflictError(f"business unit {bu_id} is used by indicators")
    repoBusinessUnits.remove(bu)
