"""Repo des paramètres d'affichage."""

from poc_trust_tower.core.schemas import SettingsSchema

DEFAULT_HOME_MESSAGE = (
    "Application POC Trust Tower. "
    "Un outil d'aide et de suivi de certification d'indicateurs."
)

repoSettings: dict[str, str] = {"home_message": DEFAULT_HOME_MESSAGE}


def get_home_message() -> str:
    return repoSettings["home_message"]


def update_settings(payload: SettingsSchema) -> None:
    repoSettings["home_message"] = payload.home_message.strip()
