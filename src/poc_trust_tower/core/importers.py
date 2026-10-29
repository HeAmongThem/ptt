"""Import d'indicateurs depuis un fichier CSV, JSON ou Excel.

Les colonnes attendues sont les champs de `IndicatorCreateSchema` (les champs
optionnels peuvent être omis). Toutes les lignes sont validées avant insertion :
en cas d'erreur, rien n'est importé.
"""

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from openpyxl import Workbook, load_workbook
from pydantic import ValidationError

from poc_trust_tower.core import repository as repo
from poc_trust_tower.core.model import Indicator
from poc_trust_tower.core.schemas import IndicatorCreateSchema

SUPPORTED_EXTENSIONS = ("csv", "json", "xlsx")

COLUMNS: list[str] = list(IndicatorCreateSchema.model_fields)
REQUIRED_COLUMNS: list[str] = [
    name for name, field in IndicatorCreateSchema.model_fields.items() if field.is_required()
]

_SAMPLE_ROW: dict[str, Any] = {
    "category_id": 1,
    "business_unit_id": 1,
    "nature_of_information": "Quantitatif",
    "description_action_expected": "Suivi du chiffre d'affaires mensuel",
    "availability_date": "2026-11-01T09:00",
    "validation_committee": "COMEX",
    "unit": "EUR",
    "value": 120.5,
    "value_previous": 110.0,
    "comment_analysis": "Hausse portée par le retail",
    "thresold_certified_without_reserves": 90,
    "thresold_acceptable": 75,
    "thresold_certified_with_significant_reserves": 60,
    "thresold_not_certified": 40,
    "certification_bu": "pending",
    "certification_bu_head": "pending",
    "certification_cfo": "pending",
    "comment_emr": "",
    "comment_bu": "",
    "comment_bu_head": "",
    "comment_cfo": "",
}


@dataclass
class RowError:
    row: int
    field: str
    message: str


class ImportValidationError(ValueError):
    def __init__(self, errors: list[RowError]):
        super().__init__(f"{len(errors)} erreur(s) de validation")
        self.errors = errors


class UnsupportedFormatError(ValueError):
    pass


# Lecture ===============================================================
def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _read_csv(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
    return [dict(row) for row in csv.DictReader(io.StringIO(text), dialect=dialect)]


def _read_json(content: bytes) -> list[dict[str, Any]]:
    data = json.loads(content.decode("utf-8"))
    if isinstance(data, dict):
        data = data.get("indicators", data.get("items"))
    if not isinstance(data, list):
        raise UnsupportedFormatError("Le JSON doit être une liste d'objets (ou {\"indicators\": [...]}).")
    return data


def _read_xlsx(content: bytes) -> list[dict[str, Any]]:
    sheet = load_workbook(io.BytesIO(content), read_only=True, data_only=True).active
    assert sheet is not None
    rows = sheet.iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(rows, [])]
    result = []
    for values in rows:
        if values is None or all(v is None for v in values):
            continue
        result.append({h: v for h, v in zip(header, values) if h})
    return result


def read_rows(filename: str, content: bytes) -> list[dict[str, Any]]:
    ext = _extension(filename)
    if ext == "csv":
        return _read_csv(content)
    if ext == "json":
        return _read_json(content)
    if ext == "xlsx":
        return _read_xlsx(content)
    raise UnsupportedFormatError(
        f"Format '.{ext}' non supporté (attendu : {', '.join('.' + e for e in SUPPORTED_EXTENSIONS)})."
    )


# Validation ============================================================
def _clean(row: dict[str, Any]) -> dict[str, Any]:
    """Ignore les cellules vides pour laisser jouer les valeurs par défaut du schéma."""
    cleaned = {}
    for key, value in row.items():
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                continue
        cleaned[key.strip()] = value
    return cleaned


def parse_indicators(rows: list[dict[str, Any]]) -> list[IndicatorCreateSchema]:
    payloads: list[IndicatorCreateSchema] = []
    errors: list[RowError] = []
    for index, row in enumerate(rows, start=2):  # ligne 1 = en-têtes
        try:
            payload = IndicatorCreateSchema.model_validate(_clean(row))
        except ValidationError as exc:
            errors.extend(
                RowError(index, ".".join(str(loc) for loc in err["loc"]) or "-", err["msg"])
                for err in exc.errors()
            )
            continue
        if repo.get_category(payload.category_id) is None:
            errors.append(RowError(index, "category_id", f"catégorie inconnue : {payload.category_id}"))
        if not any(bu.id == payload.business_unit_id for bu in repo.repoBusinessUnits):
            errors.append(RowError(index, "business_unit_id", f"business unit inconnue : {payload.business_unit_id}"))
        payloads.append(payload)
    if errors:
        raise ImportValidationError(errors)
    return payloads


def prepare_import(filename: str, content: bytes) -> list[IndicatorCreateSchema]:
    """Lit et valide le fichier sans rien créer (lève en cas d'erreur)."""
    rows = read_rows(filename, content)
    if not rows:
        raise UnsupportedFormatError("Le fichier ne contient aucune ligne de données.")
    return parse_indicators(rows)


def commit_import(payloads: list[IndicatorCreateSchema], actor=None, source_url: str | None = None) -> list[Indicator]:
    """Crée les indicateurs validés ; `source_url` (fichier archivé) est tracé dans l'audit."""
    return [repo.create_indicator(p, actor=actor, action="imported", source_url=source_url) for p in payloads]


def import_indicators(filename: str, content: bytes, actor=None, source_url: str | None = None) -> list[Indicator]:
    return commit_import(prepare_import(filename, content), actor=actor, source_url=source_url)


# Modèles téléchargeables ==============================================
def template_csv() -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, delimiter=";")
    writer.writeheader()
    writer.writerow(_SAMPLE_ROW)
    return buffer.getvalue().encode("utf-8-sig")


def template_json() -> bytes:
    return json.dumps({"indicators": [_SAMPLE_ROW]}, ensure_ascii=False, indent=2).encode("utf-8")


def template_xlsx() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "indicators"
    sheet.append(COLUMNS)
    sheet.append([
        datetime.fromisoformat(v) if k == "availability_date" else v
        for k, v in _SAMPLE_ROW.items()
    ])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


TEMPLATES = {
    "csv": (template_csv, "text/csv; charset=utf-8"),
    "json": (template_json, "application/json"),
    "xlsx": (template_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
}
