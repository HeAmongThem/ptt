from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse, Response

from poc_trust_tower.core import importers
from poc_trust_tower.core import repository as repo
from poc_trust_tower.core.model import ROLE, CertificationStatus
from poc_trust_tower.core.schemas import (
    BusinessUnitCreateSchema,
    CampaignCreateSchema,
    CampaignIndicatorsSchema,
    CategoryCreateSchema,
    IndicatorCreateSchema,
    SettingsSchema,
    UserCreateSchema,
    UserUpdateSchema,
)
from poc_trust_tower.server.auth import CurrentUserDep, require_role
from poc_trust_tower.server.templating import templates

router = APIRouter(
    prefix="/admin",
    include_in_schema=False,
    dependencies=[require_role(ROLE.ADMIN)],
)

Tab = Literal["business-units", "categories", "campaigns", "users", "indicators", "campaign-indicators", "audit", "settings"]


def _redirect(tab: Tab) -> RedirectResponse:
    # 303 : après un POST, le navigateur refait un GET sur la liste.
    return RedirectResponse(url=f"/admin?tab={tab}", status_code=status.HTTP_303_SEE_OTHER)


def _run(action, *args):
    """Exécute une opération du repository en traduisant ses erreurs en HTTP."""
    try:
        return action(*args)
    except repo.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except repo.ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


def _form_context(**extra) -> dict:
    return {
        "categories": repo.repoCategories,
        "business_units": repo.repoBusinessUnits,
        "indicators": repo.repoIndicators,
        "roles": list(ROLE),
        "statuses": [s.name for s in CertificationStatus],
        **extra,
    }


@router.get("")
def admin_index(
    request: Request,
    tab: Tab = "categories",
    campaign: int | None = None,
    audit_indicator: int | None = None,
    audit_user: int | None = None,
    audit_action: str = "",
):
    # Onglet Campagnes <-> Indicateurs : campagne sélectionnée (la première par défaut).
    selected_campaign = None
    if tab == "campaign-indicators" and repo.repoCampaigns:
        selected_campaign = next((c for c in repo.repoCampaigns if c.id == campaign), repo.repoCampaigns[0])
    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "title": "Administration",
            "tab": tab,
            "business_units": repo.repoBusinessUnits,
            "categories": repo.repoCategories,
            "campaigns": repo.repoCampaigns,
            "users": repo.repoUsers,
            "indicators": repo.repoIndicators,
            "home_message": repo.get_home_message(),
            "active_campaigns": repo.active_campaigns(),
            "selected_campaign": selected_campaign,
            "selected_ids": set(repo.campaign_indicator_ids(selected_campaign.id)) if selected_campaign else set(),
            "campaign_counts": repo.campaign_indicator_counts(),
            # indicateur -> noms des autres campagnes qui le contiennent
            "other_campaigns": {
                i.id: [
                    c.name
                    for c in repo.repoCampaigns
                    if selected_campaign and c.id != selected_campaign.id and i.id in repo.campaign_indicator_ids(c.id)
                ]
                for i in repo.repoIndicators
            },
            "link_count": len(repo.repoCampaignIndicators),
            # Onglet Audit
            "audit_entries": repo.audit_trail(audit_indicator, audit_user, audit_action, limit=500) if tab == "audit" else [],
            "audit_total": len(repo.repoIndicatorAudits),
            "audit_filters": {"indicator": audit_indicator, "user": audit_user, "action": audit_action},
            "audit_actions": ["created", "imported", "updated", "certified", "deleted"],
        },
    )


# Campaign indicators =================================================
@router.post("/campaign-indicators/{campaign_id}")
def campaign_indicators_save(campaign_id: int, payload: Annotated[CampaignIndicatorsSchema, Form()]):
    _run(repo.set_campaign_indicators, campaign_id, payload)
    return RedirectResponse(
        url=f"/admin?tab=campaign-indicators&campaign={campaign_id}&saved=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# Settings ============================================================
@router.post("/settings")
def settings_update(payload: Annotated[SettingsSchema, Form()]):
    repo.update_settings(payload)
    return _redirect("settings")


# Business units ======================================================
@router.get("/business-units/new")
def business_unit_new(request: Request):
    return templates.TemplateResponse(
        request, "admin/business_unit_form.html", _form_context(title="Nouvelle business unit", item=None)
    )


@router.post("/business-units/new")
def business_unit_create(payload: Annotated[BusinessUnitCreateSchema, Form()]):
    _run(repo.create_business_unit, payload)
    return _redirect("business-units")


@router.get("/business-units/{bu_id}")
def business_unit_edit(request: Request, bu_id: int):
    item = _run(repo.get_business_unit, bu_id)
    return templates.TemplateResponse(
        request, "admin/business_unit_form.html", _form_context(title=f"Business unit {item.name}", item=item)
    )


@router.post("/business-units/{bu_id}")
def business_unit_update(bu_id: int, payload: Annotated[BusinessUnitCreateSchema, Form()]):
    _run(repo.update_business_unit, bu_id, payload)
    return _redirect("business-units")


@router.post("/business-units/{bu_id}/delete")
def business_unit_delete(bu_id: int):
    _run(repo.delete_business_unit, bu_id)
    return _redirect("business-units")


# Categories ==========================================================
@router.get("/categories/new")
def category_new(request: Request):
    return templates.TemplateResponse(
        request, "admin/category_form.html", _form_context(title="Nouvelle catégorie", item=None)
    )


@router.post("/categories/new")
def category_create(payload: Annotated[CategoryCreateSchema, Form()]):
    _run(repo.create_category, payload)
    return _redirect("categories")


@router.get("/categories/{category_id}")
def category_edit(request: Request, category_id: int):
    item = repo.get_category(category_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"category {category_id} not found")
    return templates.TemplateResponse(
        request, "admin/category_form.html", _form_context(title=f"Catégorie {item.name}", item=item)
    )


@router.post("/categories/{category_id}")
def category_update(category_id: int, payload: Annotated[CategoryCreateSchema, Form()]):
    _run(repo.update_category, category_id, payload)
    return _redirect("categories")


@router.post("/categories/{category_id}/delete")
def category_delete(category_id: int):
    _run(repo.delete_category, category_id)
    return _redirect("categories")


# Campaigns ===========================================================
@router.get("/campaigns/new")
def campaign_new(request: Request):
    return templates.TemplateResponse(
        request, "admin/campaign_form.html", _form_context(title="Nouvelle campagne", item=None, selected_ids=[])
    )


@router.post("/campaigns/new")
def campaign_create(payload: Annotated[CampaignCreateSchema, Form()]):
    _run(repo.create_campaign, payload)
    return _redirect("campaigns")


@router.get("/campaigns/{campaign_id}")
def campaign_edit(request: Request, campaign_id: int):
    item = _run(repo.get_campaign, campaign_id)
    return templates.TemplateResponse(
        request,
        "admin/campaign_form.html",
        _form_context(title=f"Campagne {item.name}", item=item, selected_ids=repo.campaign_indicator_ids(item.id)),
    )


@router.post("/campaigns/{campaign_id}")
def campaign_update(campaign_id: int, payload: Annotated[CampaignCreateSchema, Form()]):
    _run(repo.update_campaign, campaign_id, payload)
    return _redirect("campaigns")


@router.post("/campaigns/{campaign_id}/delete")
def campaign_delete(campaign_id: int):
    _run(repo.delete_campaign, campaign_id)
    return _redirect("campaigns")


# Users ===============================================================
@router.get("/users/new")
def user_new(request: Request):
    return templates.TemplateResponse(
        request, "admin/user_form.html", _form_context(title="Nouvel utilisateur", item=None)
    )


@router.post("/users/new")
def user_create(payload: Annotated[UserCreateSchema, Form()]):
    _run(repo.create_user, payload)
    return _redirect("users")


@router.get("/users/{user_id}")
def user_edit(request: Request, user_id: int):
    item = _run(repo.get_user, user_id)
    return templates.TemplateResponse(
        request, "admin/user_form.html", _form_context(title=f"Utilisateur {item.email}", item=item)
    )


@router.post("/users/{user_id}")
def user_update(user_id: int, payload: Annotated[UserUpdateSchema, Form()]):
    _run(repo.update_user, user_id, payload)
    return _redirect("users")


@router.post("/users/{user_id}/delete")
def user_delete(user_id: int):
    _run(repo.delete_user, user_id)
    return _redirect("users")


# Indicators ==========================================================
@router.get("/indicators/new")
def indicator_new(request: Request):
    return templates.TemplateResponse(
        request, "admin/indicator_form.html", _form_context(title="Nouvel indicateur", item=None)
    )


@router.post("/indicators/new")
def indicator_create(payload: Annotated[IndicatorCreateSchema, Form()], user: CurrentUserDep):
    _run(repo.create_indicator, payload, user)
    return _redirect("indicators")


# --- Import (déclaré avant /indicators/{indicator_id}) ----------------
def _import_context(**extra) -> dict:
    return {
        "title": "Importer des indicateurs",
        "columns": importers.COLUMNS,
        "required_columns": importers.REQUIRED_COLUMNS,
        "categories": repo.repoCategories,
        "business_units": repo.repoBusinessUnits,
        "statuses": [s.name for s in CertificationStatus],
        "errors": [],
        "created": [],
        "message": None,
        **extra,
    }


@router.get("/indicators/import")
def indicator_import_form(request: Request):
    return templates.TemplateResponse(request, "admin/indicator_import.html", _import_context())


@router.post("/indicators/import")
async def indicator_import(request: Request, file: Annotated[UploadFile, File()], user: CurrentUserDep):
    content = await file.read()
    filename = file.filename or ""
    try:
        created = importers.import_indicators(filename, content, actor=user)
    except importers.ImportValidationError as exc:
        return templates.TemplateResponse(
            request,
            "admin/indicator_import.html",
            _import_context(errors=exc.errors, filename=filename),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    except (importers.UnsupportedFormatError, ValueError) as exc:
        return templates.TemplateResponse(
            request,
            "admin/indicator_import.html",
            _import_context(message=str(exc), filename=filename),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return templates.TemplateResponse(
        request, "admin/indicator_import.html", _import_context(created=created, filename=filename)
    )


@router.get("/indicators/import/template.{ext}")
def indicator_import_template(ext: Literal["csv", "json", "xlsx"]):
    build, media_type = importers.TEMPLATES[ext]
    return Response(
        content=build(),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="indicators-template.{ext}"'},
    )


@router.get("/indicators/{indicator_id}")
def indicator_edit(request: Request, indicator_id: int):
    item = _run(repo.get_indicator, indicator_id)
    return templates.TemplateResponse(
        request, "admin/indicator_form.html", _form_context(title=f"Indicateur {item.id}", item=item)
    )


@router.post("/indicators/{indicator_id}")
def indicator_update(indicator_id: int, payload: Annotated[IndicatorCreateSchema, Form()], user: CurrentUserDep):
    _run(repo.update_indicator, indicator_id, payload, user)
    return _redirect("indicators")


@router.post("/indicators/{indicator_id}/delete")
def indicator_delete(indicator_id: int, user: CurrentUserDep):
    _run(repo.delete_indicator, indicator_id, user)
    return _redirect("indicators")
