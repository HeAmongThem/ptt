from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from poc_trust_tower.core import repository as repo
from poc_trust_tower.core.model import CertificationStatus
from poc_trust_tower.core.repository import VariationFilter
from poc_trust_tower.core.schemas import CertificationSchema
from poc_trust_tower.server.auth import CurrentUserDep, require_user
from poc_trust_tower.server.templating import templates

router = APIRouter(
    prefix="/my-certifications",
    include_in_schema=False,
    tags=["certifications"],
    dependencies=[Depends(require_user)],
)


@router.get("")
def my_certifications(
    request: Request,
    category: Annotated[str, Query()] = "",
    variation: Annotated[VariationFilter, Query()] = "all",
    bu: Annotated[str, Query()] = "",
    bu_head: Annotated[str, Query()] = "",
    cfo: Annotated[str, Query()] = "",
):
    filters = {
        "category": category,
        "variation": variation,
        "bu": bu,
        "bu_head": bu_head,
        "cfo": cfo,
    }
    indicators = repo.filter_indicators(repo.repoIndicators, **filters)  # type: ignore[arg-type]
    visible_ids = {i.id for i in indicators}
    return templates.TemplateResponse(
        request,
        "indicators.html",
        {
            "title": "Indicators",
            "indicators": repo.repoIndicators,
            "visible_ids": visible_ids,
            "total": len(repo.repoIndicators),
            "filters": filters,
            "categories": repo.distinct_categories(repo.repoIndicators),
            "statuses": repo.distinct_statuses(repo.repoIndicators),
        },
    )


@router.get("/category/{category}")
def my_certifications_by_category(request: Request, category: str):
    if repo.get_category(category) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"category {category} not found")
    return my_certifications(request, category=category)


def _get_indicator_or_404(indicator_id: str):
    try:
        return repo.get_indicator(indicator_id)
    except repo.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"indicator with id {indicator_id} not found") from exc


@router.get("/{indicator_id}")
def my_certifications_by_id(request: Request, indicator_id: str, user: CurrentUserDep, saved: bool = False):
    indicator = _get_indicator_or_404(indicator_id)
    fields = repo.CERTIFICATION_FIELDS.get(user.role)
    denial = repo.certification_denial(user, indicator)
    return templates.TemplateResponse(
        request,
        "indicator.html",
        {
            "title": indicator.nature_of_information,
            "indicator": indicator,
            "saved": saved,
            "can_certify": denial is None,
            "certification_denial": denial,
            # Valeurs courantes du niveau que l'utilisateur peut modifier (None pour ADMIN).
            "my_status": getattr(indicator, fields[0]) if fields else None,
            "my_comment": getattr(indicator, fields[1]) if fields else None,
            "statuses": [s.name for s in CertificationStatus],
        },
    )


@router.post("/{indicator_id}/certify")
def my_certifications_certify(indicator_id: str, user: CurrentUserDep, payload: Annotated[CertificationSchema, Form()]):
    _get_indicator_or_404(indicator_id)
    try:
        repo.certify_indicator(indicator_id, user, payload)
    except repo.ForbiddenError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return RedirectResponse(f"/my-certifications/{indicator_id}?saved=1", status_code=status.HTTP_303_SEE_OTHER)
