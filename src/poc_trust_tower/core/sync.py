"""Mode API (DEMO=false) : les repos en mémoire ne sont qu'une projection de l'API Trust Tower.

- Aucun cache : avant chaque requête HTTP, `refresh()` recharge l'ensemble des repos
  (un seul appel `fetch all`), voir le middleware dans server/server.py.
- Chaque mutation passe par `ApiStore` : commande create/update/delete envoyée à l'API
  (qui attribue les ids), puis rechargement complet pour refléter l'état côté API.
- Un échec de l'API lève `ApiError` : la requête échoue, rien n'est conservé localement.
"""

from __future__ import annotations

import logging
from dataclasses import is_dataclass
from typing import Any

from poc_trust_tower.core import bootstrap
from poc_trust_tower.core.api_client import ApiError, TrustTowerApi
from poc_trust_tower.core.repositories._base import _collection, get_store, set_store

log = logging.getLogger(__name__)


def _serialize(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    if is_dataclass(item):
        return bootstrap._plain(item)
    raise TypeError(f"item non sérialisable : {type(item).__name__}")


def _key(item: Any) -> dict[str, Any]:
    """Clé envoyée pour delete / utilisée pour retrouver l'objet après rechargement."""
    data = _serialize(item)
    if "id" in data:
        return {"id": int(data["id"])}
    return data  # ex. CampaignIndicator : (campain_id, indicateur_id)


def _lookup(repo_name: str, key: dict[str, Any]) -> Any:
    collection = _collection(repo_name)
    if isinstance(collection, dict):
        return collection
    for obj in collection:
        if all(getattr(obj, k, None) == v for k, v in key.items()):
            return obj
    raise ApiError(f"{repo_name} : item {key} introuvable après rechargement depuis l'API")


class ApiStore:
    def __init__(self, api: TrustTowerApi):
        self.api = api

    def refresh(self) -> dict[str, int]:
        """Recharge tous les repos depuis l'API ; renvoie le nombre d'éléments par repo."""
        try:
            state = bootstrap.build_state(self.api.fetch_all())
        except bootstrap.BootstrapError as exc:
            raise ApiError(str(exc)) from exc
        bootstrap.apply_state(state)
        return {k: len(v) for k, v in state.items()}

    def add(self, repo_name: str, item: Any) -> Any:
        payload = _serialize(item)
        payload.pop("id", None)  # l'id est attribué par l'API
        created = self.api.create(repo_name, payload)
        self.refresh()
        key = {"id": int(created["id"])} if created.get("id") is not None else _key(item)
        return _lookup(repo_name, key)

    def save(self, repo_name: str, item: Any) -> Any:
        self.api.update(repo_name, _serialize(item))
        self.refresh()
        return _lookup(repo_name, _key(item))

    def remove(self, repo_name: str, item: Any) -> None:
        self.api.delete(repo_name, _key(item))
        self.refresh()


def install(api: TrustTowerApi) -> ApiStore:
    store = ApiStore(api)
    set_store(store)
    log.info("Mode API : les repos sont gérés par %s", api.url)
    return store


def is_api_mode() -> bool:
    return isinstance(get_store(), ApiStore)


def refresh() -> dict[str, int] | None:
    """Recharge les repos depuis l'API en mode API ; sans effet en mode démo."""
    store = get_store()
    if isinstance(store, ApiStore):
        return store.refresh()
    return None
