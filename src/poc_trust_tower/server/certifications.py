from typing import Annotated, Literal
from urllib.parse import urlencode

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
    user: CurrentUserDep,
    category: Annotated[str, Query()] = "",
    variation: Annotated[VariationFilter, Query()] = "all",
    bu: Annotated[str, Query()] = "",
    bu_head: Annotated[str, Query()] = "",
    cfo: Annotated[str, Query()] = "",
    campaign_status: Annotated[Literal["all", "active", "inactive"], Query()] = "all",
    campaign: Annotated[str, Query()] = "",
    saved: Annotated[str, Query()] = "",
):
    # Le select "Toutes" du formulaire envoie une chaîne vide.
    try:
        category_id = int(category) if category.strip() else None
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="query.category: must be an integer") from exc
    try:
        campaign_id = int(campaign) if campaign.strip() else None
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="query.campaign: must be an integer") from exc
    filters = {
        "category": category_id,
        "variation": variation,
        "bu": bu,
        "bu_head": bu_head,
        "cfo": cfo,
    }
    scope = repo.visible_indicators(user)
    matching_ids = {i.id for i in repo.filter_indicators(scope, **filters)}  # type: ignore[arg-type]

    # Regroupement par campagne : actives d'abord, puis inactives, puis "Sans campagne".
    by_id = {i.id: i for i in scope}
    groups: list[dict] = []
    for camp in sorted(repo.repoCampaigns, key=lambda c: (not c.actif, c.start_date), reverse=False):
        members = [by_id[i] for i in repo.campaign_indicator_ids(camp.id) if i in by_id]
        if members:
            groups.append({"campaign": camp, "actif": camp.actif, "indicators": members})
    groups.sort(key=lambda g: (not g["actif"], g["campaign"].start_date if g["actif"] else -g["campaign"].start_date.timestamp()))
    linked = {l.indicateur_id for l in repo.repoCampaignIndicators}
    orphans = [i for i in scope if i.id not in linked]
    if orphans:
        groups.append({"campaign": None, "actif": False, "indicators": orphans})

    def group_visible(group: dict) -> bool:
        if campaign_status == "active" and not group["actif"]:
            return False
        if campaign_status == "inactive" and group["actif"]:
            return False
        if campaign_id is not None and (group["campaign"] is None or group["campaign"].id != campaign_id):
            return False
        return True

    # Clés (campaign_id | None, indicator_id) des lignes visibles côté serveur.
    visible_keys = {
        (g["campaign"].id if g["campaign"] else None, i.id)
        for g in groups
        if group_visible(g)
        for i in g["indicators"]
        if i.id in matching_ids
    }
    total_rows = sum(len(g["indicators"]) for g in groups)
    my_fields = repo.CERTIFICATION_FIELDS.get(user.role)
    # URL de retour après une certification en ligne (sans le marqueur `saved` courant).
    query = urlencode([(k, v) for k, v in request.query_params.multi_items() if k != "saved"])
    return_to = request.url.path + (f"?{query}" if query else "")
    return templates.TemplateResponse(
        request,
        "indicators.html",
        {
            "title": "Indicators",
            "groups": groups,
            "visible_keys": visible_keys,
            "visible_count": len(visible_keys),
            "total": total_rows,
            "filters": {**filters, "campaign_status": campaign_status, "campaign": campaign_id},
            "campaign_options": sorted(repo.repoCampaigns, key=lambda c: (not c.actif, c.start_date)),
            "categories": repo.distinct_categories(scope),
            "statuses": repo.distinct_statuses(scope),
            # Édition en ligne du niveau de certification de l'utilisateur.
            "my_status_field": my_fields[0] if my_fields else None,
            "my_comment_field": my_fields[1] if my_fields else None,
            "certifiable_ids": {i.id for i in scope if repo.can_certify(user, i)},
            "all_statuses": [st.name for st in CertificationStatus],
            "return_to": return_to,
            "saved": saved,
        },
    )


@router.get("/category/{category}")
def my_certifications_by_category(request: Request, category: int, user: CurrentUserDep):
    if repo.get_category(category) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"category {category} not found")
    return my_certifications(request, user, category=str(category))


def _get_visible_indicator(indicator_id: int, user):
    try:
        indicator = repo.get_indicator(indicator_id)
    except repo.NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"indicator with id {indicator_id} not found") from exc
    if not repo.can_view_indicator(user, indicator):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"indicator {indicator_id} belongs to {indicator.business_unit.name}, not {user.business_unit.name}",
        )
    return indicator


@router.get("/{indicator_id}")
def my_certifications_by_id(
    request: Request,
    indicator_id: int,
    user: CurrentUserDep,
    saved: bool = False,
    view: Literal["both", "details", "audit"] = "both",
):
    indicator = _get_visible_indicator(indicator_id, user)
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
            "indicator_campaigns": repo.campaigns_of_indicator(indicator.id),
            "audit_trail": repo.indicator_audit_trail(indicator.id),
            "view": view,
        },
    )


def _is_internal_path(target: str) -> bool:
    return target.startswith("/") and not target.startswith("//")


@router.post("/{indicator_id}/certify")
def my_certifications_certify(
    indicator_id: int,
    user: CurrentUserDep,
    payload: Annotated[CertificationSchema, Form()],
    return_to: Annotated[str, Query()] = "",
):
    _get_visible_indicator(indicator_id, user)
    try:
        repo.certify_indicator(indicator_id, user, payload)
    except repo.ForbiddenError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if return_to and _is_internal_path(return_to):
        # Retour sur la liste (filtres conservés) en signalant la ligne enregistrée.
        separator = "&" if "?" in return_to else "?"
        return RedirectResponse(f"{return_to}{separator}saved={indicator_id}", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(f"/my-certifications/{indicator_id}?saved=1", status_code=status.HTTP_303_SEE_OTHER)
