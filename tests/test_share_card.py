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
