"""Configuration de l'application, lue depuis l'environnement et le fichier .env."""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from dotenv import load_dotenv

# .env à la racine du projet (cwd) ou à côté du package ; les variables déjà définies priment.
for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[3] / ".env"):
    if candidate.is_file():
        load_dotenv(candidate, override=False)
        break


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SharePointConfig:
    use: bool
    url: str
    folder: str
    login_timeout: int

    @property
    def site_url(self) -> str:
        """https://tenant.sharepoint.com/sites/Nom (sans la bibliothèque ni la page)."""
        parts = urlsplit(self.url)
        segments = [s for s in parts.path.split("/") if s]
        if "sites" in segments:
            idx = segments.index("sites")
            site_path = "/".join(segments[: idx + 2])
        else:
            site_path = ""
        return f"{parts.scheme}://{parts.netloc}" + (f"/{site_path}" if site_path else "")

    @property
    def site_path(self) -> str:
        return urlsplit(self.site_url).path

    @property
    def library(self) -> str:
        """Nom décodé de la bibliothèque (ex. 'Shared Documents')."""
        segments = [unquote(s) for s in urlsplit(self.url).path.split("/") if s]
        if "sites" in segments and len(segments) > segments.index("sites") + 2:
            return segments[segments.index("sites") + 2]
        return "Shared Documents"

    @property
    def target_folder(self) -> str:
        """Chemin relatif au serveur du dossier cible (ex. /sites/Rgulation/Shared Documents/Régulation)."""
        folder = self.folder.strip().strip("/")
        return f"{self.site_path}/{self.library}" + (f"/{folder}" if folder else "")


def load_sharepoint_config() -> SharePointConfig:
    return SharePointConfig(
        use=_as_bool(os.environ.get("SHAREPOINT_USE"), default=False),
        url=os.environ.get("SHAREPOINT_URL", "").strip(),
        folder=os.environ.get("SHAREPOINT_FOLDER", "").strip(),
        login_timeout=int(os.environ.get("SHAREPOINT_LOGIN_TIMEOUT", "180")),
    )


@dataclass(frozen=True)
class DataConfig:
    """Source des données : jeu de démonstration intégré (DEMO=true) ou API Trust Tower.

    En mode API, si URL_TOKEN est définie, un jeton est demandé au démarrage
    (POST {"secret": CLIENT_SECRET}) et envoyé en `Authorization: Bearer` à l'API."""

    demo: bool
    api_url: str
    token_url: str = ""
    client_secret: str = ""


def load_data_config() -> DataConfig:
    return DataConfig(
        demo=_as_bool(os.environ.get("DEMO"), default=True),
        api_url=os.environ.get("TRUST_TOWER_API", "").strip(),
        token_url=os.environ.get("URL_TOKEN", "").strip(),
        client_secret=os.environ.get("CLIENT_SECRET", "").strip(),
    )
