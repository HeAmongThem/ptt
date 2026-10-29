import os
from urllib.parse import unquote

from fastapi.templating import Jinja2Templates

from poc_trust_tower.core.repository import variation_kind

def _current_user(request) -> dict:
    # Import local : auth.py importe `templates` depuis ce module.
    from poc_trust_tower.server.auth import get_current_user

    return {"current_user": get_current_user(request)}


templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates"),
    context_processors=[_current_user],
)
templates.env.globals["variation_kind"] = variation_kind
# Affichage des valeurs du modèle : "certified_without_reserves" -> "certified without reserves"
templates.env.filters["humanize"] = lambda value: str(value).replace("_", " ")
# Nom de fichier lisible à partir d'une URL (ex. lien SharePoint).
templates.env.filters["filename"] = lambda url: unquote(str(url).rstrip("/").rsplit("/", 1)[-1])
