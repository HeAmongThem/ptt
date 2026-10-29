import os
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from poc_trust_tower.core.repository import (
    VariationFilter,
    distinct_categories,
    distinct_statuses,
    filter_indicators,
    get_category,
    repoIndicators,
)
from poc_trust_tower.server.admin import router as admin_router
from poc_trust_tower.server.auth import NotAuthenticated
from poc_trust_tower.server.auth import router as auth_router
from poc_trust_tower.server.templating import templates

# À définir en production ; la valeur par défaut ne sert qu'au développement.
SECRET_KEY = os.environ.get("TRUST_TOWER_SECRET_KEY", "dev-only-change-me")
SESSION_MAX_AGE = 8 * 60 * 60

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=SESSION_MAX_AGE, same_site="lax")
app.mount("/statics", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
app.include_router(auth_router)
app.include_router(admin_router)

#Errors==============================================================
def error_response(request: Request, status_code: int, detail: str | None = None):
    return templates.TemplateResponse(
        request,
        "error.html",
        {"title": f"Erreur {status_code}", "status_code": status_code, "detail": detail},
        status_code=status_code,
    )


@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated):
    return RedirectResponse(f"/login?next={exc.next_url}", status_code=status.HTTP_303_SEE_OTHER)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return error_response(request, exc.status_code, exc.detail)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Ex. : "query.variation: Input should be 'all', 'up', 'down' or 'stable'"
    detail = "; ".join(
        f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()
    )
    return error_response(request, status.HTTP_422_UNPROCESSABLE_CONTENT, detail)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return error_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR)
#Errors==============================================================




@app.get("/", include_in_schema=False,)
async def index(request: Request):
    datas: list[int] = [1, 2, 3, 4, 5]
    return templates.TemplateResponse(
        request, "home.html", context={"datas": datas, "title": "home"}
    )


#Certifications=======================================================
@app.get("/my-certifications", include_in_schema=False)
def my_certifications(
    request: Request,
    category: str = "",
    variation: VariationFilter = "all",
    bu: str = "",
    bu_head: str = "",
    cfo: str = "",
):
    filters = {
        "category": category,
        "variation": variation,
        "bu": bu,
        "bu_head": bu_head,
        "cfo": cfo,
    }
    indicators = filter_indicators(repoIndicators, **filters) # type: ignore
    visible_ids = {i.id for i in indicators}
    return templates.TemplateResponse(
        request,
        "indicators.html",
        {
            "title": "Indicators",
            "indicators": repoIndicators,
            "visible_ids": visible_ids,
            "total": len(repoIndicators),
            "filters": filters,
            "categories": distinct_categories(repoIndicators),
            "statuses": distinct_statuses(repoIndicators),
        },
    )

@app.get("/my-certifications/category/{category}", include_in_schema=False)
def my_certifications_by_category(request: Request, category: str):
    if get_category(category) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"category {category} not found")
    return my_certifications(request, category=category)

@app.get("/my-certifications/{id}", include_in_schema=False)
def my_certifications_by_id(request: Request, id:str):
    result = None
    for indicator in repoIndicators:
        if indicator.id == id:
            result = indicator
            break;
    if result is not None:
        return templates.TemplateResponse(
            request,
            "indicator.html",
            {"title": result.nature_of_information, "indicator": result},
        )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"indicator with id {id} not found")

        
        

@app.delete("/my-certifications/{id}", include_in_schema=False)
async def my_certifications_certify(request: Request, id:str):
    pass

#Certifications=======================================================
