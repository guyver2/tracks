import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import (
    ALLOWED_PHOTO_EXTENSIONS,
    GPX_UPLOAD_DIR,
    MAX_GPX_BYTES,
    MAX_PHOTO_BYTES,
    PHOTO_UPLOAD_DIR,
)


async def save_gpx(upload: UploadFile) -> str:
    content = await upload.read()
    if len(content) > MAX_GPX_BYTES:
        raise ValueError("GPX file exceeds 10 MB limit")
    if not (upload.filename or "").lower().endswith(".gpx"):
        raise ValueError("File must be a .gpx file")

    filename = f"{uuid.uuid4().hex}.gpx"
    path = GPX_UPLOAD_DIR / filename
    path.write_bytes(content)
    return filename


async def save_photo(upload: UploadFile) -> str:
    content = await upload.read()
    if len(content) > MAX_PHOTO_BYTES:
        raise ValueError("Photo exceeds 5 MB limit")

    ext = Path(upload.filename or "").suffix.lower()
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        raise ValueError("Photo must be JPG, PNG, or WebP")

    filename = f"{uuid.uuid4().hex}{ext}"
    path = PHOTO_UPLOAD_DIR / filename
    path.write_bytes(content)
    return filename


def delete_file(directory: Path, filename: str | None) -> None:
    if not filename:
        return
    path = directory / filename
    if path.exists():
        path.unlink()
