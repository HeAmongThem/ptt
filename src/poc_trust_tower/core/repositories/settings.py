"""Repo des paramètres d'affichage."""
from typing import Any
from poc_trust_tower.core.schemas import SettingsSchema

from ._base import _save

DEFAULT_HOME_MESSAGE = (
    "Application POC Trust Tower. "
    "Un outil d'aide et de suivi de certification d'indicateurs."
)

DEFAULT_SETTINGS_ID = 1


def default_settings() -> dict[str, Any]:
    """Nouveau dictionnaire de paramètres avec les valeurs par défaut."""
    return {"id": DEFAULT_SETTINGS_ID, "home_message": DEFAULT_HOME_MESSAGE}


repoSettings: dict[str, Any] = default_settings()


def get_home_message() -> str:
    return repoSettings["home_message"]


def update_settings(payload: SettingsSchema) -> None:
    repoSettings["home_message"] = payload.home_message.strip()
    _save("repoSettings", repoSettings)
