from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import PHOTO_UPLOAD_DIR, ensure_data_dirs
from app.routers import activities, pages

APP_DIR = Path(__file__).resolve().parent

ensure_data_dirs()

app = FastAPI(title="Tracks")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.mount("/uploads/photos", StaticFiles(directory=PHOTO_UPLOAD_DIR), name="photos")

templates = Jinja2Templates(directory=APP_DIR / "templates")

app.include_router(activities.router)
app.include_router(pages.router)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"request": request, "active_nav": "dashboard"},
    )
