from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.db.engine import engine
from app.models.ppt_task import PptTask
from app.schemas.ppt import PptBrief


# 总共最多执行 3 次：首次执行 + 最多 2 次中断重试
MAX_ATTEMPTS = 3

# 领取凭证有效期为 120 秒，后续会定期续期
LEASE_SECONDS = 120


@dataclass(frozen=True)
class TaskClaim:
    brief: PptBrief
    execution_token: UUID


def claim_task(task_id: UUID) -> TaskClaim | None:
    token = uuid4()

    with Session(engine) as db:
        statement = (
            update(PptTask)
            .where(
                PptTask.id == task_id,
                PptTask.status == "queued",
                PptTask.attempt_count < MAX_ATTEMPTS,
            )
            .values(
                status="planning",
                attempt_count=PptTask.attempt_count + 1,
                execution_token=token,
                lease_expires_at=(
                    func.now() + timedelta(seconds=LEASE_SECONDS)
                ),
                error_message=None,
                outline_json=None,
                artifact_path=None,
            )
            .returning(PptTask)
        )

        task = db.execute(statement).scalar_one_or_none()
        if task is None:
            return None

        brief = PptBrief(
            topic=task.topic,
            audience=task.audience,
            slide_count=task.slide_count,
            requirements=task.requirements,
            template_id=task.template_id,
        )

        claim = TaskClaim(
            brief=brief,
            execution_token=token,
        )

        db.commit()
        return claim

def renew_task_lease(
    task_id: UUID,
    execution_token: UUID,
) -> bool:
    with Session(engine) as db:
        statement = (
            update(PptTask)
            .where(
                PptTask.id == task_id,
                PptTask.execution_token == execution_token,
                PptTask.status.in_(
                    ("planning", "rendering", "checking")
                ),
                PptTask.lease_expires_at > func.now(),
            )
            .values(
                lease_expires_at=(
                    func.now() + timedelta(seconds=LEASE_SECONDS)
                )
            )
            .returning(PptTask.id)
        )

        changed_id = db.execute(statement).scalar_one_or_none()
        db.commit()

        return changed_id is not None

def recover_expired_tasks() -> tuple[list[UUID], list[UUID]]:
    recovered_ids: list[UUID] = []
    failed_ids: list[UUID] = []

    with Session(engine) as db:
        statement = (
            select(PptTask)
            .where(
                PptTask.status.in_(
                    ("planning", "rendering", "checking")
                ),
                or_(
                    PptTask.lease_expires_at <= func.now(),
                    PptTask.lease_expires_at.is_(None),
                ),
            )
            .order_by(PptTask.created_at, PptTask.id)
            .limit(100)
            .with_for_update(skip_locked=True)
        )

        tasks = db.scalars(statement).all()

        for task in tasks:
            task.execution_token = None
            task.lease_expires_at = None
            task.outline_json = None
            task.artifact_path = None

            if task.attempt_count >= MAX_ATTEMPTS:
                task.status = "failed"
                task.error_message = "任务多次中断，已达到执行次数上限"
                failed_ids.append(task.id)
            else:
                task.status = "queued"
                task.error_message = None
                recovered_ids.append(task.id)

        db.commit()

    return recovered_ids, failed_ids