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
@app.post("/login", include_in_schema=False)
async def login():
    pass

@app.post("/logout", include_in_schema=False)
async def logout():
    pass
#Loggin==============================================================

#Certifications=======================================================
@app.get("my-certifications", include_in_schema=False)
async def my_certifications():
    pass

@app.get("my-certifications/{category}", include_in_schema=False)
async def my_certifications_by_category(category:str):
    pass

@app.get("my-certifications/{id}", include_in_schema=False)
async def my_certifications_by_id(id:int):
    pass

@app.post("my-certifications/certify/{id}", include_in_schema=False)
async def my_certifications_certify(id:int):
    pass

#Certifications=======================================================



#Admin===============================================================
@app.get("/admin", include_in_schema=False)
async def admin():
    pass
#--------------------------------------------------------------------
@app.get("/admin/campaigns", include_in_schema=False)
async def admin_campaigns():
    pass

@app.get("/admin/campaigns/{id:int}", include_in_schema=False)
async def admin_campaigns_id(id:int):
    pass

@app.post("/admin/campaigns/create", include_in_schema=False)
async def admin_campaigns_create():
    pass

@app.put("/admin/campaigns/update", include_in_schema=False)
async def admin_campaigns_update():
    pass

@app.delete("/admin/campaigns/delete/{id:int}", include_in_schema=False)
async def admin_campaigns_delete(id:int):
    pass

#--------------------------------------------------------------------
@app.get("/admin/indicators/", include_in_schema=False)
async def admin_indicators():
    pass

@app.post("/admin/indicators/create", include_in_schema=False)
async def admin_indicators_create():
    pass

@app.put("/admin/indicators/update", include_in_schema=False)
async def admin_indicators_update():
    pass

@app.delete("/admin/indicators/delete/{id:int}", include_in_schema=False)
async def admin_indicators_delete(id:int):
    pass


#--------------------------------------------------------------------
@app.get("/admin/users/", include_in_schema=False)
async def admin_users():
    pass

@app.get("/admin/users/{id:int}", include_in_schema=False)
async def admin_users_by_id(id:int):
    pass

@app.post("/admin/users/create", include_in_schema=False)
async def admin_users_create():
    pass

@app.put("/admin/users/update", include_in_schema=False)
async def admin_users_update():
    pass

@app.delete("/admin/users/delete/{id:int}", include_in_schema=False)
async def admin_users_delete(id:int):
    pass

#Admin===============================================================


