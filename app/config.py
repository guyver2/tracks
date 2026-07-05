import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).resolve()
DATABASE_URL = os.environ.get(
    "DATABASE_URL", f"sqlite:///{DATA_DIR / 'tracks.db'}"
)

GPX_UPLOAD_DIR = DATA_DIR / "uploads" / "gpx"
PHOTO_UPLOAD_DIR = DATA_DIR / "uploads" / "photos"
ELEVATION_CACHE_DIR = DATA_DIR / "elevation_cache"
MAP_GEOJSON_CACHE_DIR = DATA_DIR / "map_cache"
PERSONAL_RECORDS_CACHE_FILE = DATA_DIR / "personal_records.json"

ELEVATION_SOURCE = os.environ.get("ELEVATION_SOURCE", "dem").lower()
OPENTOPODATA_BASE_URL = os.environ.get(
    "OPENTOPODATA_BASE_URL", "https://api.opentopodata.org"
).rstrip("/")
OPENTOPODATA_DATASET = os.environ.get("OPENTOPODATA_DATASET", "eudem25m,srtm30m")

MAX_GPX_BYTES = 10 * 1024 * 1024
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_TRACKS_PER_ACTIVITY = 10
MAX_PHOTOS_PER_ACTIVITY = 10
ACTIVITIES_PAGE_SIZE = 10

ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GPX_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PHOTO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ELEVATION_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    MAP_GEOJSON_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def elevation_enabled() -> bool:
    return ELEVATION_SOURCE == "dem"
