"""Worker process heartbeats shared through the existing local log volume.

This is a liveness signal, not proof of database or model availability.
"""
from dataclasses import dataclass
import json
import logging
import math
import os
from pathlib import Path
import socket
from tempfile import NamedTemporaryFile
from threading import Event, Thread
import time
from uuid import uuid4

logger = logging.getLogger("ppt_agent.worker_health")
HEARTBEAT_SECONDS = 10
HEARTBEAT_TIMEOUT_SECONDS = 45
MAX_CLOCK_SKEW_SECONDS = 5


def heartbeat_directory() -> Path:
    from app.core.config import settings

    return settings.log_dir / "worker-heartbeats"


@dataclass(frozen=True)
class WorkerStatus:
    active_workers: int
    latest_heartbeat_age_seconds: float | None


def get_worker_status(
    directory: Path,
    *,
    host_id: str | None = None,
    now: float | None = None,
) -> WorkerStatus:
    """Ignore expired, malformed and unrelated markers; never expose their data."""
    checked_at = time.time() if now is None else now
    try:
        paths = list(directory.iterdir())
    except FileNotFoundError:
        return WorkerStatus(0, None)
    ages: list[float] = []
    for path in paths:
        if path.suffix != ".json" or path.is_symlink():
            continue
        try:
            with path.open("rb") as stream:
                raw = stream.read(4097)
            if len(raw) > 4096:
                continue
            marker = json.loads(raw)
        except (OSError, ValueError):
            continue
        if not isinstance(marker, dict) or marker.get("version") != 1:
            continue
        if marker.get("status") != "running" or marker.get("instance_id") != path.stem:
            continue
        marker_host = marker.get("host_id")
        if not isinstance(marker_host, str) or not marker_host:
            continue
        if host_id is not None and marker_host != host_id:
            continue
        seen_at = marker.get("last_seen")
        if isinstance(seen_at, bool) or not isinstance(seen_at, (int, float)):
            continue
        if not math.isfinite(seen_at):
            continue
        age = checked_at - seen_at
        if age < -MAX_CLOCK_SKEW_SECONDS:
            continue
        ages.append(max(0.0, age))
    return WorkerStatus(
        active_workers=sum(age <= HEARTBEAT_TIMEOUT_SECONDS for age in ages),
        latest_heartbeat_age_seconds=round(min(ages), 1) if ages else None,
    )


class WorkerHeartbeat:
    """Publish while idle or busy; each process owns a separate marker."""

    def __init__(self, directory: Path, *, interval: float = HEARTBEAT_SECONDS):
        if interval <= 0:
            raise ValueError("Heartbeat interval must be positive")
        self.directory = directory
        self.interval = interval
        self.instance_id = uuid4().hex
        self.host_id = socket.gethostname()
        self.path = directory / f"{self.instance_id}.json"
        self._stop = Event()
        self._thread = Thread(target=self._run, name="worker-heartbeat", daemon=True)

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self._publish()
        try:
            self._thread.start()
        except BaseException:
            self.path.unlink(missing_ok=True)
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._stop.set()
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            logger.warning("worker_heartbeat_stop_pending")
            return False
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            logger.warning("worker_heartbeat_cleanup_failed")
        return False

    def _publish(self) -> None:
        payload = {
            "version": 1,
            "instance_id": self.instance_id,
            "host_id": self.host_id,
            "pid": os.getpid(),
            "status": "running",
            "last_seen": time.time(),
        }
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.directory,
                prefix=f".{self.instance_id}-", suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(payload, stream)
            # The reader sees either the old complete file or the new one.
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self._publish()
            except Exception:
                logger.exception("worker_heartbeat_write_failed")


def main() -> int:
    try:
        # Another container's heartbeat must not hide this container's failure.
        status = get_worker_status(heartbeat_directory(), host_id=socket.gethostname())
    except OSError:
        print("Worker heartbeat storage is unavailable")
        return 1
    if status.active_workers:
        print("Worker heartbeat is fresh")
        return 0
    print("No fresh Worker heartbeat for this container")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
