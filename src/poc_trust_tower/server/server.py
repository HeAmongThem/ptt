from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/")
async def index():
    return {"message" : "hello"}

@app.post('/login', response_class=HTMLResponse)
async def login():
    pass

@app.post('/logout', response_class=HTMLResponse)
async def logout():
    pass