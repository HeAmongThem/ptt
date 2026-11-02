"""Initialisation des repos depuis l'API Trust Tower (mode DEMO=false).

L'API est appelée en POST avec {"command": "fetch", "repo_name": "all"} et renvoie :
{
    "repoBusinessUnits": [...], "repoCategories": [...], "repoUsers": [...],
    "repoIndicators": [...], "repoCampaigns": [...], "repoCampaignIndicators": [...],
    "repoIndicatorAudits": [...], "repoSettings": {"id": 1, "home_message": "..."}
}
Les références (business unit, catégorie) sont acceptées sous forme d'id
(`business_unit_id`, `category_id`), d'id direct (`business_unit`: 3) ou d'objet imbriqué.
Les écritures (create/update/delete) passent ensuite par core/sync.py.
"""

from __future__ import annotations

import logging
from dataclasses import is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import httpx

from poc_trust_tower.core import repository as repo
from poc_trust_tower.core.api_client import ApiError, TrustTowerApi, fetch_token
from poc_trust_tower.core.model import (
    ROLE,
    BusinessUnit,
    Campaign,
    CampaignIndicator,
    Category,
    Indicator,
    IndicatorAudit,
    User,
)
from poc_trust_tower.core.security import hash_password

log = logging.getLogger(__name__)

REPO_KEYS = (
    "repoBusinessUnits", "repoCategories", "repoUsers", "repoIndicators",
    "repoCampaigns", "repoCampaignIndicators", "repoIndicatorAudits", "repoSettings",
)


class BootstrapError(RuntimeError):
    pass


# Sérialisation (repos -> JSON) ==========================================
def _plain(value: Any, *, nested: bool = False) -> Any:
    """Valeur JSON ; les BusinessUnit / Category imbriquées sont réduites à leur id."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if nested and isinstance(value, (BusinessUnit, Category)):
        return value.id
    if is_dataclass(value):
        return {k: _plain(v, nested=True) for k, v in vars(value).items()}
    if isinstance(value, list):
        return [_plain(v, nested=nested) for v in value]
    return value


def serialize_state() -> dict[str, Any]:
    """État courant des repos au format attendu de l'API (références par id)."""
    return {
        "repoBusinessUnits": _plain(repo.repoBusinessUnits),
        "repoCategories": _plain(repo.repoCategories),
        "repoUsers": _plain(repo.repoUsers),
        "repoIndicators": _plain(repo.repoIndicators),
        "repoCampaigns": _plain(repo.repoCampaigns),
        "repoCampaignIndicators": _plain(repo.repoCampaignIndicators),
        "repoIndicatorAudits": _plain(repo.repoIndicatorAudits),
        "repoSettings": dict(repo.repoSettings),
    }


# Désérialisation (JSON -> dataclasses) ==================================
def _ref_id(row: dict, name: str) -> int:
    """Id d'une référence : `<name>_id`, `<name>` (int) ou `<name>` (objet avec id)."""
    for key in (f"{name}_id", name):
        if key in row and row[key] is not None:
            value = row[key]
            return int(value["id"] if isinstance(value, dict) else value)
    raise BootstrapError(f"référence '{name}' manquante dans {row}")


def _dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value in (None, ""):
        raise BootstrapError("date manquante")
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def _role(value: Any) -> ROLE:
    """Rôle tolérant aux variations d'écriture : espaces parasites, casse, tirets ('bu head' -> BU_HEAD)."""
    raw = str(value or "")
    # Comparaison sur les seules lettres : 'BU_HE   AD', 'bu head', 'BU-HEAD' -> BU_HEAD.
    letters = "".join(ch for ch in raw.upper() if ch.isalpha())
    for role in ROLE:
        if letters == role.value.replace("_", ""):
            return role
    raise BootstrapError(f"rôle inconnu {raw!r} (attendu : {', '.join(r.value for r in ROLE)})")


def _looks_hashed(password: str) -> bool:
    return password.startswith(("$2a$", "$2b$", "$2y$"))


def _build_settings(row: Any) -> dict[str, Any]:
    """Paramètres d'affichage : `id` entier (défaut 1) et `home_message` texte (défaut du repo)."""
    if isinstance(row, list):
        row = row[0] if row else {}
    if not isinstance(row, dict):
        raise BootstrapError(f"repoSettings doit être un objet, reçu {type(row).__name__}")
    settings = repo.default_settings()
    if row.get("id") is not None:
        settings["id"] = int(row["id"])
    message = str(row.get("home_message") or "").strip()
    if message:
        settings["home_message"] = message
    return settings


def build_state(payload: dict[str, Any]) -> dict[str, Any]:
    """Transforme la réponse JSON en objets du domaine (sans toucher aux repos)."""
    missing = [k for k in REPO_KEYS if k not in payload]
    if missing:
        raise BootstrapError(f"réponse API incomplète, clés manquantes : {', '.join(missing)}")
    try:
        business_units = [BusinessUnit(id=int(r["id"]), name=str(r["name"])) for r in payload["repoBusinessUnits"]]
        categories = [Category(id=int(r["id"]), name=str(r["name"])) for r in payload["repoCategories"]]
        bu_by_id = {b.id: b for b in business_units}
        cat_by_id = {c.id: c for c in categories}

        def bu(row: dict) -> BusinessUnit:
            ref = _ref_id(row, "business_unit")
            if ref not in bu_by_id:
                raise BootstrapError(f"business unit {ref} inconnue")
            return bu_by_id[ref]

        def cat(row: dict) -> Category:
            ref = _ref_id(row, "category")
            if ref not in cat_by_id:
                raise BootstrapError(f"catégorie {ref} inconnue")
            return cat_by_id[ref]

        users = []
        for r in payload["repoUsers"]:
            try:
                users.append(
                    User(
                        id=int(r["id"]),
                        email=str(r["email"]).strip(),
                        password=r["password"] if _looks_hashed(str(r.get("password", ""))) else hash_password(str(r.get("password", ""))),
                        business_unit=bu(r),
                        role=_role(r.get("role")),
                    )
                )
            except BootstrapError as exc:
                raise BootstrapError(f"repoUsers, utilisateur {r.get('id')} ({r.get('email')}) : {exc}") from exc
        
        indicator_fields = [f for f in Indicator.__dataclass_fields__ if f not in ("id", "category", "business_unit")]        
        indicators = []
        for r in payload["repoIndicators"]:
            kwargs = {}
            for f in indicator_fields:
                value = r.get(f, "" if f.startswith(("comment", "certification", "nature", "description", "validation", "unit")) else None)
                if f in ("availability_date", "created_at", "updated_at"):
                    value = _dt(value)
                elif f in ("value", "value_previous", "variation") or f.startswith("thresold_"):
                    value = float(value if value is not None else 0)
                kwargs[f] = value
            indicators.append(Indicator(id=int(r["id"]), category=cat(r), business_unit=bu(r), **kwargs))
        
        campaigns = [
            Campaign(id=int(r["id"]), name=str(r["name"]), start_date=_dt(r["start_date"]), end_date=_dt(r["end_date"]), actif=bool(r.get("actif", False)))
            for r in payload["repoCampaigns"]
        ]
        
        links = [
            CampaignIndicator(campain_id=int(r.get("campain_id", r.get("campaign_id"))), indicateur_id=int(r.get("indicateur_id", r.get("indicator_id"))))
            for r in payload["repoCampaignIndicators"]
        ]
        
        audits = [
            IndicatorAudit(
                id=int(r["id"]), indicator_id=int(r["indicator_id"]),
                user_id=int(r["user_id"]) if r.get("user_id") is not None else None,
                user_email=str(r.get("user_email", "")), action=str(r["action"]), field=str(r.get("field", "")),
                old_value=str(r.get("old_value", "")), new_value=str(r.get("new_value", "")), timestamp=_dt(r["timestamp"]),
            )
            for r in payload["repoIndicatorAudits"]
        ]
        
        settings = _build_settings(payload["repoSettings"] or {})
    except BootstrapError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise BootstrapError(f"réponse API invalide : {exc!r}") from exc
    return {
        "repoBusinessUnits": business_units, "repoCategories": categories, "repoUsers": users,
        "repoIndicators": indicators, "repoCampaigns": campaigns, "repoCampaignIndicators": links,
        "repoIndicatorAudits": audits, "repoSettings": settings,
    }


def apply_state(state: dict[str, Any]) -> None:
    """Remplace le contenu des repos en place (les références importées ailleurs restent valides)."""
    for key in REPO_KEYS:
        target = getattr(repo, key)
        if isinstance(target, dict):
            target.clear()
            target.update({**repo.default_settings(), **state[key]})
        else:
            target[:] = state[key]
    repo._HIGH_WATER_IDS.clear()


# Chargement depuis l'API ================================================
def fetch_state(api_url: str, transport: httpx.BaseTransport | None = None, timeout: float = 30, token: str | None = None) -> dict[str, Any]:
    try:
        return TrustTowerApi(api_url, transport=transport, timeout=timeout, token=token).fetch_all()
    except ApiError as exc:
        raise BootstrapError(str(exc)) from exc


def load_from_api(api_url: str, transport: httpx.BaseTransport | None = None, token: str | None = None) -> dict[str, int]:
    """Charge l'état depuis l'API et l'applique ; renvoie le nombre d'éléments par repo."""
    state = build_state(fetch_state(api_url, transport=transport, token=token))
    apply_state(state)
    counts = {k: len(v) for k, v in state.items()}
    log.info("Données chargées depuis %s : %s", api_url, counts)
    return counts


_initialized = False


def acquire_token(config) -> str | None:
    """Jeton d'accès à l'API si URL_TOKEN est définie ; bloque le démarrage si le serveur de jetons refuse."""
    if not config.token_url:
        log.info("URL_TOKEN non définie : appels à l'API Trust Tower sans jeton.")
        return None
    try:
        token = fetch_token(config.token_url, config.client_secret)
    except ApiError as exc:
        raise BootstrapError(f"authentification auprès de l'API Trust Tower refusée : {exc}") from exc
    log.info("Jeton d'accès à l'API Trust Tower obtenu depuis %s.", config.token_url)
    return token


def initialize(force: bool = False) -> dict[str, int] | None:
    """Charge les données depuis l'API si DEMO=false (une seule fois) et active le mode API
    (toutes les lectures/écritures passent ensuite par l'API). Renvoie None en mode démo."""
    global _initialized
    from poc_trust_tower.core import sync
    from poc_trust_tower.core.config import load_data_config

    config = load_data_config()
    if config.demo:
        repo.set_store(None)
        log.info("DEMO=true : jeu de données de démonstration.")
        return None
    if _initialized and not force:
        return None
    token = acquire_token(config)
    counts = load_from_api(config.api_url, token=token)
    sync.install(TrustTowerApi(config.api_url, token=token))
    _initialized = True
    return counts
