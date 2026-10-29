import os

from fastapi.templating import Jinja2Templates

from poc_trust_tower.core.repository import variation_kind

STATUS_LABELS = {
    "pending": "En attente",
    "certified_without_reserves": "Certifié",
    "acceptable": "Acceptable",
    "certified_with_significant_reserves": "Réserves signif.",
    "not_certified": "Non certifié",
}

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)
templates.env.globals["variation_kind"] = variation_kind
templates.env.filters["status_label"] = lambda value: STATUS_LABELS.get(value, value)
