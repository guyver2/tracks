import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).resolve()
DATABASE_URL = os.environ.get(
    "DATABASE_URL", f"sqlite:///{DATA_DIR / 'tracks.db'}"
)

GPX_UPLOAD_DIR = DATA_DIR / "uploads" / "gpx"
PHOTO_UPLOAD_DIR = DATA_DIR / "uploads" / "photos"

MAX_GPX_BYTES = 10 * 1024 * 1024
MAX_PHOTO_BYTES = 5 * 1024 * 1024

ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GPX_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PHOTO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
