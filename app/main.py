from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import PHOTO_UPLOAD_DIR, ensure_data_dirs
from app.routers import activities, objectives, pages
from app.services.elevation_worker import get_worker

APP_DIR = Path(__file__).resolve().parent

ensure_data_dirs()


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_worker().start()
    yield
    get_worker().stop()


app = FastAPI(title="Tracks", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.mount("/uploads/photos", StaticFiles(directory=PHOTO_UPLOAD_DIR), name="photos")

app.include_router(pages.router)
app.include_router(activities.router)
app.include_router(objectives.router)
