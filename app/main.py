from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import PHOTO_UPLOAD_DIR, ensure_data_dirs
from app.routers import activities, objectives, pages

APP_DIR = Path(__file__).resolve().parent

ensure_data_dirs()

app = FastAPI(title="Tracks")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.mount("/uploads/photos", StaticFiles(directory=PHOTO_UPLOAD_DIR), name="photos")

app.include_router(pages.router)
app.include_router(activities.router)
app.include_router(objectives.router)
