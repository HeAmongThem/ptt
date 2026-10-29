from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from poc_trust_tower.core import repository as repo
from poc_trust_tower.core.repository import VariationFilter
from poc_trust_tower.server.auth import require_user
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


@router.get("/{indicator_id}")
def my_certifications_by_id(request: Request, indicator_id: str):
    try:
        indicator = repo.get_indicator(indicator_id)
    except repo.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"indicator with id {indicator_id} not found") from exc
    return templates.TemplateResponse(
        request,
        "indicator.html",
        {"title": indicator.nature_of_information, "indicator": indicator},
    )


@router.delete("/{indicator_id}")
async def my_certifications_certify(request: Request, indicator_id: str):
    pass
