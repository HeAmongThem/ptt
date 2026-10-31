"""Éléments communs aux repos : horloge de référence des données de démo, erreurs, ids, recherche."""

from datetime import datetime

_NOW = datetime(2026, 10, 1, 9, 0, 0)

class NotFoundError(LookupError):
    pass


class ConflictError(ValueError):
    pass


class ForbiddenError(PermissionError):
    pass


# Marque haute par collection : un id supprimé n'est jamais réattribué
# (indispensable pour que l'audit trail reste rattaché au bon objet).
_HIGH_WATER_IDS: dict[int, int] = {}


def _next_id(items: list) -> int:
    key = id(items)
    current = max(max((i.id for i in items), default=0), _HIGH_WATER_IDS.get(key, 0))
    _HIGH_WATER_IDS[key] = current + 1
    return current + 1


def _find(items: list, item_id: int, label: str):
    item = next((i for i in items if i.id == item_id), None)
    if item is None:
        raise NotFoundError(f"{label} {item_id} not found")
    return item

def _name_taken(items: list, name: str, exclude=None) -> bool:
    return any(i.name.casefold() == name.casefold() and i is not exclude for i in items)
