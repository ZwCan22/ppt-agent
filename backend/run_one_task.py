from uuid import UUID

from app.core.logging_config import setup_logging
from app.db.engine import engine
from app.services.task_runner import run_task


def main() -> None:
    setup_logging("worker")
    try:
        task_id = UUID(input("请输入任务编号：").strip())
        print("开始制作，请等待……")

        ppt_path = run_task(task_id, user_id="local-test-user")
        if ppt_path is None:
            print("任务不存在，或已不处于 queued 状态")
        else:
            print("制作完成，文件位置：", ppt_path)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
