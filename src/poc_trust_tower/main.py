import logging
import socket
import threading
import time
import uvicorn
import webview
from poc_trust_tower.server.server import app

HOST = "127.0.0.1"
PORT = 8000


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
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
