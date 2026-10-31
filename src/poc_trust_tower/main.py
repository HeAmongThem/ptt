import html
import logging
import socket
import sys
import threading
import time
import uvicorn
import webview
import os
from pathlib import Path
from dotenv import load_dotenv
from poc_trust_tower.core import bootstrap, sharepoint
from poc_trust_tower.core.config import load_sharepoint_config
from poc_trust_tower.server.server import app

HOST = "127.0.0.1"
PORT = 8000


def connect_sharepoint() -> None:
    """Si SHAREPOINT_USE est vrai, exige une connexion SharePoint avant de lancer l'application."""
    config = load_sharepoint_config()
    if not config.use:
        logging.info("SharePoint désactivé (SHAREPOINT_USE != true).")
        return
    if not config.url:
        fail_and_exit("SHAREPOINT_USE est actif mais SHAREPOINT_URL n'est pas définie dans le fichier .env.")
    logging.info("Connexion à SharePoint : %s", config.url)
    try:
        sharepoint.set_session(sharepoint.login_interactive(config))
    except sharepoint.SharePointAuthError as exc:
        sharepoint.set_session(None, str(exc))
        fail_and_exit(f"Connexion à SharePoint impossible : {exc}")


def load_data() -> None:
    """Initialise les données (API Trust Tower si DEMO=false) ; bloque le démarrage en cas d'échec."""
    try:
        counts = bootstrap.initialize()
    except bootstrap.BootstrapError as exc:
        fail_and_exit(f"Initialisation des données impossible : {exc}")
    else:
        if counts:
            logging.info("Données initialisées depuis l'API Trust Tower : %s", counts)


def fail_and_exit(message: str) -> None:
    """Affiche le message d'erreur dans une fenêtre puis arrête l'application."""
    logging.error(message)
    body = f"""<!doctype html><html lang="fr"><body style="font-family: system-ui; padding: 2rem; color: #842029; background: #f8d7da">
    <h1 style="font-size: 1.25rem">Trust Tower ne peut pas démarrer</h1>
    <p>{html.escape(message)}</p>
    <p style="color: #333">Vérifiez la configuration du fichier .env (DEMO, TRUST_TOWER_API, SHAREPOINT_*), puis relancez l'application.</p>
    </body></html>"""
    webview.create_window("Trust Tower — erreur", html=body, width=640, height=320)
    webview.start()
    sys.exit(1)

def app_load_env() -> None: 
    # .env à la racine du projet (cwd) ou à côté du package ; les variables déjà définies priment.
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[3] / ".env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            break

def main() -> None:
    app_load_env()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    load_data()
    connect_sharepoint()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=HOST,
            port=PORT,
            timeout_graceful_shutdown=5,
        )
    )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((HOST, PORT))
        thread = threading.Thread(
            target=server.run,
            kwargs={"sockets": [listener]},
            daemon=True,
        )
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                if not thread.is_alive():
                    raise RuntimeError("Le serveur FastAPI n'a pas pu demarrer.")
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "Le serveur FastAPI n'est pas pret apres 10 secondes."
                    )
                time.sleep(0.05)

            webview.create_window("Trust Tower", f"http://localhost:{PORT}/")
            webview.start()
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("Le serveur FastAPI ne s'est pas arrete.")


if __name__ == "__main__":
    main()
