"""Client HTTP de l'API Trust Tower (DEMO=false) : l'API gère les repos.

Toutes les commandes sont des POST JSON sur une URL unique :
    {"command": "fetch",  "repo_name": "<repo>" | "all"}   -> liste des items | {"<repo>": [...], ...}
    {"command": "create", "repo_name": "<repo>", "item": {...}}  -> item créé (avec son id)
    {"command": "update", "repo_name": "<repo>", "item": {"id": 1, ...}}
    {"command": "delete", "repo_name": "<repo>", "item": {"id": 1}}
Une erreur est signalée par un statut HTTP 4xx/5xx avec {"error": "..."}.

Authentification (optionnelle) : `fetch_token` appelle URL_TOKEN avec {"secret": CLIENT_SECRET}
et reçoit une réponse de style OAuth ({"access_token": "...", "token_type": "Bearer"}) ;
le jeton est ensuite envoyé dans l'en-tête Authorization de chaque commande.
"""

from __future__ import annotations

from typing import Any

import httpx

HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


class ApiError(RuntimeError):
    """Échec d'un appel à l'API Trust Tower (réseau, statut HTTP, réponse illisible)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def fetch_token(token_url: str, client_secret: str, transport: httpx.BaseTransport | None = None, timeout: float = 30) -> str:
    """Demande un jeton d'accès ; renvoie la valeur à placer dans `Authorization` (ex. "Bearer xyz")."""
    if not token_url:
        raise ApiError("URL_TOKEN n'est pas définie dans le fichier .env.")
    try:
        with httpx.Client(timeout=timeout, transport=transport) as client:
            response = client.post(token_url, json={"secret": client_secret}, headers=HEADERS)
    except httpx.HTTPError as exc:
        raise ApiError(f"récupération du jeton impossible ({token_url}) : {exc}") from exc
    if response.is_error:
        raise ApiError(_error_message(response, "token", token_url), status_code=response.status_code)
    try:
        body = response.json()
    except ValueError as exc:
        raise ApiError(f"réponse du serveur de jetons non JSON ({token_url})") from exc
    token = body.get("access_token") or body.get("token") if isinstance(body, dict) else None
    if not token:
        raise ApiError(f"réponse du serveur de jetons sans access_token ({token_url})")
    token_type = str(body.get("token_type") or "Bearer") if isinstance(body, dict) else "Bearer"
    return f"{token_type} {token}"


class TrustTowerApi:
    def __init__(self, url: str, transport: httpx.BaseTransport | None = None, timeout: float = 30, token: str | None = None):
        if not url:
            raise ApiError("DEMO=false mais TRUST_TOWER_API n'est pas définie dans le fichier .env.")
        self.url = url
        self._transport = transport
        self._timeout = timeout
        self.headers = {**HEADERS, **({"Authorization": token} if token else {})}

    def command(self, command: str, repo_name: str, item: dict[str, Any] | None = None) -> Any:
        payload: dict[str, Any] = {"command": command, "repo_name": repo_name}
        if item is not None:
            payload["item"] = item
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.post(self.url, json=payload, headers=self.headers)
        except httpx.HTTPError as exc:
            raise ApiError(f"appel de l'API Trust Tower impossible ({self.url}) : {exc}") from exc
        if response.is_error:
            raise ApiError(_error_message(response, command, repo_name), status_code=response.status_code)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(f"réponse de l'API Trust Tower non JSON ({command} {repo_name})") from exc

    def fetch(self, repo_name: str) -> list[dict[str, Any]]:
        data = self.command("fetch", repo_name)
        if isinstance(data, dict) and isinstance(data.get(repo_name), list):
            data = data[repo_name]
        if not isinstance(data, list):
            raise ApiError(f"fetch {repo_name} : l'API doit renvoyer une liste JSON")
        return data

    def fetch_all(self) -> dict[str, Any]:
        data = self.command("fetch", "all")
        if not isinstance(data, dict):
            raise ApiError("la réponse de l'API Trust Tower doit être un objet JSON")
        return data

    def create(self, repo_name: str, item: dict[str, Any]) -> dict[str, Any]:
        data = self.command("create", repo_name, item)
        if isinstance(data, dict) and isinstance(data.get("item"), dict):
            data = data["item"]
        if not isinstance(data, dict):
            raise ApiError(f"create {repo_name} : l'API doit renvoyer l'item créé")
        return data

    def update(self, repo_name: str, item: dict[str, Any]) -> None:
        self.command("update", repo_name, item)

    def delete(self, repo_name: str, key: dict[str, Any]) -> None:
        self.command("delete", repo_name, key)


def _error_message(response: httpx.Response, command: str, repo_name: str) -> str:
    detail = ""
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = str(body.get("error_description") or body.get("error") or body.get("detail") or "")
    except ValueError:
        detail = response.text[:200]
    return f"API Trust Tower : {command} {repo_name} a échoué (HTTP {response.status_code})" + (f" : {detail}" if detail else "")
