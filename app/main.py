from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import DATA_DIR, PHOTO_UPLOAD_DIR, ensure_data_dirs

APP_DIR = Path(__file__).resolve().parent

ensure_data_dirs()

app = FastAPI(title="Tracks")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.mount("/uploads/photos", StaticFiles(directory=PHOTO_UPLOAD_DIR), name="photos")

templates = Jinja2Templates(directory=APP_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"request": request, "active_nav": "dashboard"},
    )
