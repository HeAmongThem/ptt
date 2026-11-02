"""Intégration SharePoint : connexion interactive (Playwright) et dépôt de fichiers (API REST).

Flux :
1. `login_interactive()` ouvre une fenêtre Chromium sur l'URL SharePoint ; l'utilisateur
   s'authentifie (SSO / MFA). Dès que la page SharePoint est chargée avec les cookies de
   session (FedAuth / rtFa), la fenêtre se ferme et les cookies sont conservés.
2. `SharePointSession.upload()` dépose un fichier via l'API REST en réutilisant ces cookies.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

from poc_trust_tower.core.config import SharePointConfig

log = logging.getLogger(__name__)

AUTH_COOKIES = ("FedAuth", "rtFa")
LOGIN_HOSTS = ("login.microsoftonline.com", "login.live.com", "login.microsoft.com")


class SharePointError(Exception):
    pass


class SharePointAuthError(SharePointError):
    pass


class SharePointUploadError(SharePointError):
    pass


@dataclass
class SharePointSession:
    site_url: str
    cookies: dict[str, str]
    target_folder: str
    transport: httpx.BaseTransport | None = field(default=None, repr=False)

    @property
    def host(self) -> str:
        return urlsplit(self.site_url).netloc

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.site_url,
            cookies=self.cookies,
            headers={"Accept": "application/json;odata=verbose"},
            timeout=60,
            transport=self.transport,
        )

    def _digest(self, client: httpx.Client) -> str:
        response = client.post("/_api/contextinfo")
        if response.status_code in (401, 403):
            raise SharePointAuthError("Session SharePoint expirée ou refusée (contextinfo).")
        response.raise_for_status()
        return response.json()["d"]["GetContextWebInformation"]["FormDigestValue"]

    def ensure_folder(self, client: httpx.Client, digest: str) -> None:
        """Crée le dossier cible s'il n'existe pas (SharePoint tolère la recréation)."""
        response = client.post(
            "/_api/web/folders",
            headers={"X-RequestDigest": digest, "Content-Type": "application/json;odata=verbose"},
            json={"__metadata": {"type": "SP.Folder"}, "ServerRelativeUrl": self.target_folder},
        )
        if response.status_code not in (200, 201) and "exist" not in response.text.lower():
            response.raise_for_status()

    def upload(self, filename: str, content: bytes) -> str:
        """Dépose `content` sous `filename` dans le dossier cible et renvoie l'URL du fichier."""
        try:
            with self._client() as client:
                digest = self._digest(client)
                self.ensure_folder(client, digest)
                endpoint = (
                    f"/_api/web/GetFolderByServerRelativeUrl('{quote(self.target_folder)}')"
                    f"/Files/add(url='{quote(filename)}',overwrite=true)"
                )
                response = client.post(
                    endpoint,
                    headers={"X-RequestDigest": digest, "Content-Type": "application/octet-stream"},
                    content=content,
                )
                if response.status_code in (401, 403):
                    raise SharePointAuthError("Session SharePoint expirée ou refusée (upload).")
                response.raise_for_status()
                server_relative = response.json()["d"]["ServerRelativeUrl"]
        except SharePointError:
            raise
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise SharePointUploadError(f"Dépôt SharePoint impossible : {exc}") from exc
        return f"https://{self.host}{quote(server_relative)}"


# Connexion interactive ==================================================
def _default_browsers_path() -> Path:
    """Dossier où `playwright install` dépose les navigateurs (même logique que Playwright)."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "ms-playwright"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "ms-playwright"


def configure_browsers_path() -> None:
    """Dans un binaire PyInstaller, Playwright force PLAYWRIGHT_BROWSERS_PATH=0 (navigateurs attendus
    dans le paquet). On le pointe vers le cache utilisateur standard, où `playwright install chromium`
    les installe, sauf si la variable est déjà définie."""
    if getattr(sys, "frozen", False) and not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_default_browsers_path())


def _is_authenticated(page_url: str, cookies: dict[str, str], site_host: str) -> bool:
    host = urlsplit(page_url).netloc
    if host in LOGIN_HOSTS or host != site_host:
        return False
    return all(name in cookies for name in AUTH_COOKIES)


def login_interactive(config: SharePointConfig) -> SharePointSession:
    """Ouvre une fenêtre de connexion et renvoie une session authentifiée.

    Lève SharePointAuthError si l'utilisateur ferme la fenêtre, si le délai expire
    ou si Playwright / Chromium ne sont pas disponibles.
    """
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - dépendance déclarée
        raise SharePointAuthError("Playwright n'est pas installé.") from exc

    site_host = urlsplit(config.site_url).netloc
    deadline = time.monotonic() + config.login_timeout
    configure_browsers_path()
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=False)
            except PlaywrightError as exc:
                raise SharePointAuthError(
                    "Chromium indisponible pour Playwright : exécutez `playwright install chromium` "
                    f"(`uv run playwright install chromium` depuis les sources). Détail : {_first_line(exc)}"
                ) from exc
            context = browser.new_context()
            page = context.new_page()
            page.goto(config.url, wait_until="domcontentloaded")
            while time.monotonic() < deadline:
                if page.is_closed():
                    raise SharePointAuthError("La fenêtre de connexion SharePoint a été fermée avant l'authentification.")
                cookies = {c["name"]: c["value"] for c in context.cookies() if site_host.endswith(c["domain"].lstrip("."))} # pyright: ignore[reportTypedDictNotRequiredAccess]
                if _is_authenticated(page.url, cookies, site_host):
                    log.info("Connexion SharePoint établie (%s)", page.url)
                    browser.close()
                    return SharePointSession(config.site_url, cookies, config.target_folder)
                page.wait_for_timeout(500)
            browser.close()
    except PlaywrightError as exc:
        raise SharePointAuthError(f"Erreur du navigateur pendant la connexion SharePoint : {exc}") from exc
    raise SharePointAuthError(
        f"Authentification SharePoint non réalisée dans le délai de {config.login_timeout} s."
    )


def _first_line(exc: BaseException) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else repr(exc)


# État partagé de l'application =========================================
_current: SharePointSession | None = None
_last_error: str | None = None


def set_session(session: SharePointSession | None, error: str | None = None) -> None:
    global _current, _last_error
    _current, _last_error = session, error


def current_session() -> SharePointSession | None:
    return _current


def last_error() -> str | None:
    return _last_error
