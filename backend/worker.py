import logging
import time

from app.core.logging_config import setup_logging
from app.db.engine import engine
from app.core.worker_health import WorkerHeartbeat, heartbeat_directory
from app.services.task_lease import recover_expired_tasks
from app.services.task_runner import get_next_task_id, run_task

logger = logging.getLogger("ppt_agent.worker")


def main() -> None:
    setup_logging("worker")

    try:
        with WorkerHeartbeat(heartbeat_directory()):
            logger.info("worker_started")
            while True:
                task_id = None
                try:
                    # 先检查有没有需要恢复的任务
                    recovered_ids, failed_ids = recover_expired_tasks()

                    for recovered_id in recovered_ids:
                        logger.warning(
                            "task_requeued task_id=%s",
                            recovered_id,
                        )

                    for failed_id in failed_ids:
                        logger.warning(
                            "task_recovery_exhausted task_id=%s",
                            failed_id,
                        )

                    # 再领取排队中的任务
                    task_id = get_next_task_id()
                    if task_id is None:
                        time.sleep(2)
                        continue

                    result = run_task(task_id, user_id="local-test-user")
                    if result is None:
                        time.sleep(1)

                except Exception:
                    logger.exception(
                        "worker_iteration_failed task_id=%s", task_id
                    )
                    time.sleep(5)

    except KeyboardInterrupt:
        logger.info("worker_stopped")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
