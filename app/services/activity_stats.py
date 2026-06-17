from app.config import GPX_UPLOAD_DIR
from app.db.models import Activity
from app.db.session import SessionLocal
from app.services.gpx import (
    aggregate_track_stats,
    bounds_to_json,
    parse_track,
    recompute_track_start_time,
)


def recompute_activity_elevation(activity_id: int) -> None:
    db = SessionLocal()
    try:
        activity = db.get(Activity, activity_id)
        if not activity or not activity.tracks:
            return

        track_stats = []
        for track in activity.tracks:
            path = GPX_UPLOAD_DIR / track.gpx_filename
            if not path.exists():
                continue
            try:
                stats = parse_track(
                    path,
                    track.trim_start,
                    track.trim_end,
                    gpx_filename=track.gpx_filename,
                )
                recompute_track_start_time(track, GPX_UPLOAD_DIR)
                track_stats.append(stats)
            except ValueError:
                continue

        aggregated = aggregate_track_stats(track_stats)
        if aggregated is None:
            activity.elevation_gain_m = None
        else:
            activity.elevation_gain_m = aggregated.elevation_gain_m

        db.commit()
    finally:
        db.close()
