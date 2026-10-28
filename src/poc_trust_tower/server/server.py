import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/statics", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)




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
@app.get("my-certifications", include_in_schema=False)
async def my_certifications(request: Request ):
    pass

@app.get("my-certifications/{category}", include_in_schema=False)
async def my_certifications_by_category(request: Request, category:str):
    pass

@app.get("my-certifications/{id}", include_in_schema=False)
async def my_certifications_by_id(request: Request, id:int):
    pass

@app.post("my-certifications/certify/{id}", include_in_schema=False)
async def my_certifications_certify(request: Request, id:int):
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

@app.delete("/admin/indicators/delete/{id:int}", include_in_schema=False)
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

@app.delete("/admin/users/delete/{id:int}", include_in_schema=False)
async def admin_users_delete(request: Request, id:int):
    pass

#Admin===============================================================


