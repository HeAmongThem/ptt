from typing import Annotated, Literal

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from poc_trust_tower.core import repository as repo
from poc_trust_tower.core.model import ROLE, CertificationStatus
from poc_trust_tower.core.schemas import (
    CampaignCreateSchema,
    CategoryCreateSchema,
    IndicatorCreateSchema,
    UserCreateSchema,
    UserUpdateSchema,
)
from poc_trust_tower.server.templating import templates

router = APIRouter(prefix="/admin", include_in_schema=False)

Tab = Literal["categories", "campaigns", "users", "indicators"]


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
def admin_index(request: Request, tab: Tab = "categories"):
    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "title": "Administration",
            "tab": tab,
            "categories": repo.repoCategories,
            "campaigns": repo.repoCampaigns,
            "users": repo.repoUsers,
            "indicators": repo.repoIndicators,
        },
    )


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
def category_edit(request: Request, category_id: str):
    item = repo.get_category(category_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"category {category_id} not found")
    return templates.TemplateResponse(
        request, "admin/category_form.html", _form_context(title=f"Catégorie {item.name}", item=item)
    )


@router.post("/categories/{category_id}")
def category_update(category_id: str, payload: Annotated[CategoryCreateSchema, Form()]):
    _run(repo.update_category, category_id, payload)
    return _redirect("categories")


@router.post("/categories/{category_id}/delete")
def category_delete(category_id: str):
    _run(repo.delete_category, category_id)
    return _redirect("categories")


# Campaigns ===========================================================
@router.get("/campaigns/new")
def campaign_new(request: Request):
    return templates.TemplateResponse(
        request, "admin/campaign_form.html", _form_context(title="Nouvelle campagne", item=None)
    )


@router.post("/campaigns/new")
def campaign_create(payload: Annotated[CampaignCreateSchema, Form()]):
    _run(repo.create_campaign, payload)
    return _redirect("campaigns")


@router.get("/campaigns/{campaign_id}")
def campaign_edit(request: Request, campaign_id: str):
    item = _run(repo.get_campaign, campaign_id)
    return templates.TemplateResponse(
        request, "admin/campaign_form.html", _form_context(title=f"Campagne {item.name}", item=item)
    )


@router.post("/campaigns/{campaign_id}")
def campaign_update(campaign_id: str, payload: Annotated[CampaignCreateSchema, Form()]):
    _run(repo.update_campaign, campaign_id, payload)
    return _redirect("campaigns")


@router.post("/campaigns/{campaign_id}/delete")
def campaign_delete(campaign_id: str):
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
def user_edit(request: Request, user_id: str):
    item = _run(repo.get_user, user_id)
    return templates.TemplateResponse(
        request, "admin/user_form.html", _form_context(title=f"Utilisateur {item.email}", item=item)
    )


@router.post("/users/{user_id}")
def user_update(user_id: str, payload: Annotated[UserUpdateSchema, Form()]):
    _run(repo.update_user, user_id, payload)
    return _redirect("users")


@router.post("/users/{user_id}/delete")
def user_delete(user_id: str):
    _run(repo.delete_user, user_id)
    return _redirect("users")


# Indicators ==========================================================
@router.get("/indicators/new")
def indicator_new(request: Request):
    return templates.TemplateResponse(
        request, "admin/indicator_form.html", _form_context(title="Nouvel indicateur", item=None)
    )


@router.post("/indicators/new")
def indicator_create(payload: Annotated[IndicatorCreateSchema, Form()]):
    _run(repo.create_indicator, payload)
    return _redirect("indicators")


@router.get("/indicators/{indicator_id}")
def indicator_edit(request: Request, indicator_id: str):
    item = _run(repo.get_indicator, indicator_id)
    return templates.TemplateResponse(
        request, "admin/indicator_form.html", _form_context(title=f"Indicateur {item.id}", item=item)
    )


@router.post("/indicators/{indicator_id}")
def indicator_update(indicator_id: str, payload: Annotated[IndicatorCreateSchema, Form()]):
    _run(repo.update_indicator, indicator_id, payload)
    return _redirect("indicators")


@router.post("/indicators/{indicator_id}/delete")
def indicator_delete(indicator_id: str):
    _run(repo.delete_indicator, indicator_id)
    return _redirect("indicators")
