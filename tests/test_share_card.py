import json
from datetime import date, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Activity, ActivityTrack, ActivityType
from app.db.session import get_db
from app.main import app
from app.routers.activities import _activity_start_time_from_tracks


def test_activity_start_time_from_tracks_returns_earliest():
    earlier = datetime(2024, 6, 1, 8, 10, 0)
    later = datetime(2024, 6, 1, 9, 0, 0)
    tracks = [
        ActivityTrack(
            gpx_filename="a.gpx",
            track_start_time=later,
        ),
        ActivityTrack(
            gpx_filename="b.gpx",
            track_start_time=earlier,
        ),
    ]

    assert _activity_start_time_from_tracks(tracks) == earlier


def test_activity_start_time_from_tracks_returns_none_when_missing():
    tracks = [
        ActivityTrack(gpx_filename="a.gpx", track_start_time=None),
        ActivityTrack(gpx_filename="b.gpx", track_start_time=None),
    ]

    assert _activity_start_time_from_tracks(tracks) is None


def test_activity_start_time_from_tracks_empty_list():
    assert _activity_start_time_from_tracks([]) is None


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_activity_detail_includes_share_card_markup(client, db):
    activity = Activity(
        name="Alpine loop",
        activity_type=ActivityType.hike,
        date=date(2024, 6, 1),
        place="Chamonix",
        distance_km=12.5,
        duration_sec=7200,
        elevation_gain_m=850.0,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)

    with patch("app.routers.activities.get_personal_records", return_value=[]):
        response = client.get(f"/activities/{activity.id}")

    assert response.status_code == 200
    body = response.text
    assert 'id="share-card-data"' in body
    assert 'id="share-card-trigger"' in body
    assert "/static/js/share_card.js" in body
    assert "Share card" in body

    start = body.index('id="share-card-data">') + len('id="share-card-data">')
    payload = json.loads(body[start:body.index("</script>", start)])
    assert payload["name"] == "Alpine loop"
    assert payload["date"] == "2024-06-01"
    assert payload["distanceKm"] == 12.5
    assert payload["durationSec"] == 7200
    assert payload["elevationGainM"] == 850.0
    assert payload["geojsonUrl"] is None
    assert payload["elevationUrl"] is None
    assert payload["hasMap"] is False
    assert "mapboxToken" in payload
    assert "mapboxStyle" in payload
    assert payload["shareCardUrl"] == f"/activities/{activity.id}/share-card"
    assert 'id="share-card-viewer"' in body
    assert "mapbox-gl.js" not in body


JPEG = b"\xff\xd8\xff\xd9"


def _activity(db):
    activity = Activity(
        name="Alpine loop",
        activity_type=ActivityType.hike,
        date=date(2024, 6, 1),
        place="Chamonix",
        distance_km=12.5,
        duration_sec=7200,
        elevation_gain_m=850.0,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def test_share_card_is_saved_once_and_reused(client, db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.share_cards.SHARE_CARD_DIR", tmp_path)
    activity = _activity(db)

    missing = client.get(f"/activities/{activity.id}/share-card")
    assert missing.status_code == 404
    assert missing.headers["cache-control"] == "no-store"
    assert client.head(f"/activities/{activity.id}/share-card").status_code == 404

    created = client.post(
        f"/activities/{activity.id}/share-card",
        files={"file": ("card.jpg", JPEG, "image/jpeg")},
    )
    assert created.status_code == 200
    assert created.json()["url"] == f"/activities/{activity.id}/share-card"
    assert (tmp_path / f"{activity.id}.jpg").read_bytes() == JPEG

    again = client.post(
        f"/activities/{activity.id}/share-card",
        files={"file": ("card.jpg", b"\xff\xd8\xff\x00\xd9", "image/jpeg")},
    )
    assert again.status_code == 200
    assert (tmp_path / f"{activity.id}.jpg").read_bytes() == JPEG

    stored = client.get(f"/activities/{activity.id}/share-card")
    assert stored.status_code == 200
    assert stored.headers["content-type"].startswith("image/jpeg")
    assert "inline" in stored.headers["content-disposition"]
    assert stored.content == JPEG
    assert client.head(f"/activities/{activity.id}/share-card").status_code == 200


def test_share_card_rejects_non_jpeg(client, db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.share_cards.SHARE_CARD_DIR", tmp_path)
    activity = _activity(db)

    response = client.post(
        f"/activities/{activity.id}/share-card",
        files={"file": ("card.png", b"not-a-jpeg", "image/png")},
    )
    assert response.status_code == 400
    assert not (tmp_path / f"{activity.id}.jpg").exists()


def test_activity_update_and_delete_remove_share_card(client, db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.share_cards.SHARE_CARD_DIR", tmp_path)
    activity = _activity(db)
    path = tmp_path / f"{activity.id}.jpg"
    path.write_bytes(JPEG)

    with patch("app.routers.activities._refresh_personal_records"):
        updated = client.post(
            f"/activities/{activity.id}",
            data={
                "name": "Alpine loop",
                "activity_type": "hike",
                "date": "2024-06-02",
            },
            follow_redirects=False,
        )
    assert updated.status_code == 303
    assert not path.exists()

    path.write_bytes(JPEG)
    with patch("app.routers.activities._refresh_personal_records"):
        deleted = client.post(f"/activities/{activity.id}/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert not path.exists()
