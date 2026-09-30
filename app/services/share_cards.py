from pathlib import Path

from app.config import SHARE_CARD_DIR

MAX_SHARE_CARD_BYTES = 20 * 1024 * 1024


def share_card_path(activity_id: int) -> Path:
    return SHARE_CARD_DIR / f"{int(activity_id)}.jpg"


def delete_share_card(activity_id: int) -> None:
    path = share_card_path(activity_id)
    if path.is_file():
        path.unlink()


def write_share_card(activity_id: int, content: bytes) -> Path:
    if len(content) > MAX_SHARE_CARD_BYTES or not content.startswith(b"\xff\xd8\xff"):
        raise ValueError("Share card must be a JPEG")

    SHARE_CARD_DIR.mkdir(parents=True, exist_ok=True)
    path = share_card_path(activity_id)
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(content)
    temporary.replace(path)
    return path
