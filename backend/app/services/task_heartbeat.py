import logging
from threading import Event, Thread
from uuid import UUID

from app.services.task_lease import renew_task_lease

logger = logging.getLogger("ppt_agent.tasks")
HEARTBEAT_SECONDS = 20


class LeaseLostError(RuntimeError):
    pass


class TaskHeartbeat:
    def __init__(self, task_id: UUID, execution_token: UUID):
        self.task_id = task_id
        self.execution_token = execution_token
        self._stop = Event()
        self._lost = Event()
        self._thread = Thread(
            target=self._run,
            name=f"heartbeat-{task_id}",
            daemon=True,
        )

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._stop.set()
        self._thread.join(timeout=10)
        if self._thread.is_alive():
            logger.warning(
                "task_heartbeat_stop_pending task_id=%s",
                self.task_id,
            )
        return False

    def check(self) -> None:
        if self._lost.is_set():
            raise LeaseLostError("任务领取凭证已失效或无法确认")

    def _run(self) -> None:
        while not self._stop.wait(HEARTBEAT_SECONDS):
            try:
                renewed = renew_task_lease(
                    self.task_id,
                    self.execution_token,
                )
            except Exception:
                self._lost.set()
                logger.exception(
                    "task_heartbeat_failed task_id=%s",
                    self.task_id,
                )
                return

            if not renewed:
                self._lost.set()
                logger.warning(
                    "task_lease_lost task_id=%s",
                    self.task_id,
                )
                return

            logger.info(
                "task_heartbeat task_id=%s",
                self.task_id,
            )