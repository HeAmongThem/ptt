import os
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from poc_trust_tower.core.repository import (
    VariationFilter,
    distinct_categories,
    distinct_statuses,
    filter_indicators,
    get_category,
    repoIndicators,
    variation_kind,
)

app = FastAPI()
app.mount("/statics", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)
templates.env.globals["variation_kind"] = variation_kind


#Errors==============================================================
def error_response(request: Request, status_code: int, detail: str | None = None):
    return templates.TemplateResponse(
        request,
        "error.html",
        {"title": f"Erreur {status_code}", "status_code": status_code, "detail": detail},
        status_code=status_code,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return error_response(request, exc.status_code, exc.detail)


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


#Loggin==============================================================
@app.get("/login", include_in_schema=False)
async def login(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.post("/login", include_in_schema=False)
async def login_post(request: Request):
    return request.form
    #return templates.TemplateResponse(request, "login.html")

@app.post("/logout", include_in_schema=False)
async def logout(request: Request):
    pass
#Loggin==============================================================

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



#Admin===============================================================
@app.get("/admin", include_in_schema=False)
async def admin(request: Request ):
    pass
#--------------------------------------------------------------------
@app.get("/admin/campaigns", include_in_schema=False)
async def admin_campaigns(request: Request ):
    pass

@app.get("/admin/campaigns/{id:int}", include_in_schema=False)
async def admin_campaigns_id(request: Request, id:int):
    pass

@app.post("/admin/campaigns/create", include_in_schema=False)
async def admin_campaigns_create(request: Request ):
    pass

@app.put("/admin/campaigns/update", include_in_schema=False)
async def admin_campaigns_update(request: Request ):
    pass

@app.delete("/admin/campaigns/delete/{id:int}", include_in_schema=False)
async def admin_campaigns_delete(request: Request, id:int):
    pass

#--------------------------------------------------------------------
@app.get("/admin/indicators/", include_in_schema=False)
async def admin_indicators(request: Request ):
    pass

@app.post("/admin/indicators/create", include_in_schema=False)
async def admin_indicators_create(request: Request ):
    pass

@app.put("/admin/indicators/update", include_in_schema=False)
async def admin_indicators_update(request: Request ):
    pass

@app.delete("/admin/indicators/delete/{id}", include_in_schema=False)
async def admin_indicators_delete(request: Request, id:int):
    pass


#--------------------------------------------------------------------
@app.get("/admin/users/", include_in_schema=False)
async def admin_users(request: Request ):
    pass

@app.get("/admin/users/{id:int}", include_in_schema=False)
async def admin_users_by_id(request: Request, id:int):
    pass

@app.post("/admin/users/create", include_in_schema=False)
async def admin_users_create(request: Request ):
    pass

@app.put("/admin/users/update", include_in_schema=False)
async def admin_users_update(request: Request ):
    pass

@app.delete("/admin/users/delete/{id}", include_in_schema=False)
async def admin_users_delete(request: Request, id:int):
    pass

#Admin===============================================================


