from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import os

app = FastAPI(title="2D Design Studio")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Файл index.html не найден!</h1>"

