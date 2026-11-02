"""Éléments communs aux repos : horloge de référence des données de démo, erreurs, ids, recherche,
et point d'extension de persistance (`Store`) utilisé par toutes les mutations."""

from datetime import datetime
from typing import Any, Protocol

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


# Persistance ============================================================
# Les fonctions de mutation des repos valident et construisent les objets localement puis
# passent par le store courant : en mode démo il modifie les listes en mémoire ; en mode API
# (DEMO=false) il délègue à l'API Trust Tower puis recharge les repos (voir core/sync.py).
class Store(Protocol):
    def add(self, repo_name: str, item: Any) -> Any: ...
    def save(self, repo_name: str, item: Any) -> Any: ...
    def remove(self, repo_name: str, item: Any) -> None: ...


def _collection(repo_name: str) -> Any:
    from poc_trust_tower.core import repositories  # import paresseux : évite un cycle

    return getattr(repositories, repo_name)


class LocalStore:
    """Mode démo : les repos en mémoire sont la source de vérité."""

    def add(self, repo_name: str, item: Any) -> Any:
        _collection(repo_name).append(item)
        return item

    def save(self, repo_name: str, item: Any) -> Any:
        return item  # l'objet a déjà été modifié en place

    def remove(self, repo_name: str, item: Any) -> None:
        _collection(repo_name).remove(item)


_store: Store = LocalStore()


def get_store() -> Store:
    return _store


def set_store(store: Store | None) -> None:
    """Installe le store courant (None rétablit le mode local)."""
    global _store
    _store = store if store is not None else LocalStore()


def _add(repo_name: str, item: Any) -> Any:
    """Ajoute `item` au repo ; renvoie l'objet persisté (id attribué par l'API en mode API)."""
    return _store.add(repo_name, item)


def _save(repo_name: str, item: Any) -> Any:
    """Persiste les modifications déjà appliquées à `item` ; renvoie l'objet rechargé."""
    return _store.save(repo_name, item)


def _remove(repo_name: str, item: Any) -> None:
    _store.remove(repo_name, item)
