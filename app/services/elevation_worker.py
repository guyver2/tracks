import logging
import queue
import threading
from dataclasses import dataclass

from app.config import ELEVATION_CACHE_DIR, GPX_UPLOAD_DIR, elevation_enabled
from app.db.models import ActivityTrack
from app.db.session import SessionLocal
from app.services.elevation import (
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    STATUS_READY,
    get_elevation_cache_state,
    populate_elevation_cache,
    track_elevation_status,
)
from app.services.gpx import _load_gpx_points

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ElevationJob:
    gpx_filename: str
    activity_id: int


class ElevationWorker:
    def __init__(self) -> None:
        self._queue: queue.Queue[ElevationJob | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._inflight: set[str] = set()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="elevation-worker", daemon=True)
        self._thread.start()
        self.recover_incomplete_jobs()

    def stop(self) -> None:
        self._stop_event.set()
        self._queue.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def enqueue(self, gpx_filename: str, activity_id: int) -> None:
        if not elevation_enabled():
            return
        with self._lock:
            if gpx_filename in self._inflight:
                return
            self._inflight.add(gpx_filename)
        self._queue.put(ElevationJob(gpx_filename=gpx_filename, activity_id=activity_id))

    def cancel(self, gpx_filename: str) -> None:
        with self._lock:
            self._inflight.discard(gpx_filename)

    def recover_incomplete_jobs(self) -> None:
        if not elevation_enabled():
            return

        seen: set[str] = set()

        for sidecar in ELEVATION_CACHE_DIR.glob("*.json"):
            state = None
            try:
                import json

                with sidecar.open("r", encoding="utf-8") as f:
                    state = json.load(f)
            except (OSError, json.JSONDecodeError):
                state = None

            if not isinstance(state, dict):
                continue

            status = state.get("status")
            gpx_filename = f"{sidecar.stem}.gpx"
            activity_id = state.get("activity_id")
            if status not in {STATUS_PENDING, STATUS_PROCESSING, STATUS_FAILED}:
                continue
            if not isinstance(activity_id, int):
                continue
            if gpx_filename in seen:
                continue
            seen.add(gpx_filename)
            self.enqueue(gpx_filename, activity_id)

        db = SessionLocal()
        try:
            tracks = db.query(ActivityTrack).all()
            for track in tracks:
                if track.gpx_filename in seen:
                    continue
                path = GPX_UPLOAD_DIR / track.gpx_filename
                if not path.exists():
                    continue
                try:
                    point_count = len(_load_gpx_points(path))
                except ValueError:
                    continue
                status = track_elevation_status(track.gpx_filename, point_count)
                if status == STATUS_READY:
                    continue
                seen.add(track.gpx_filename)
                self.enqueue(track.gpx_filename, track.activity_id)
        finally:
            db.close()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                job = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if job is None:
                break

            try:
                self._process_job(job)
            finally:
                with self._lock:
                    self._inflight.discard(job.gpx_filename)
                self._queue.task_done()

    def _process_job(self, job: ElevationJob) -> None:
        path = GPX_UPLOAD_DIR / job.gpx_filename
        if not path.exists():
            logger.warning("Skipping elevation job; GPX missing: %s", job.gpx_filename)
            return

        try:
            points = _load_gpx_points(path)
        except ValueError as exc:
            logger.warning("Skipping elevation job; invalid GPX %s: %s", job.gpx_filename, exc)
            return

        coords = [(lat, lon) for lat, lon, _, _ in points]
        populate_elevation_cache(job.gpx_filename, coords, job.activity_id)

        from app.services.activity_stats import recompute_activity_elevation

        recompute_activity_elevation(job.activity_id)


_worker: ElevationWorker | None = None


def get_worker() -> ElevationWorker:
    global _worker
    if _worker is None:
        _worker = ElevationWorker()
    return _worker
