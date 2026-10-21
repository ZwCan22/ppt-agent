import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.ppt_task import PptTask
from app.schemas.ppt import PptBrief, PptTaskCreated

logger = logging.getLogger("ppt_agent.tasks")


class SubmissionConflictError(ValueError):
    """A submission key was reused with different normalized requirements."""


def create_task(
    db: Session,
    brief: PptBrief,
    *,
    owner_id: UUID,
    idempotency_key: UUID | None = None,
) -> tuple[PptTaskCreated, bool]:
    """Commit one task, or return the task already saved for this submission."""
    values = brief.model_dump()
    if idempotency_key is None:
        task = PptTask(**values, owner_id=owner_id)
        db.add(task)
        db.flush()
        created = True
    else:
        # The unique constraint arbitrates simultaneous requests in PostgreSQL.
        # DO NOTHING leaves an existing task's status and results untouched.
        statement = (
            insert(PptTask)
            .values(**values, owner_id=owner_id, idempotency_key=idempotency_key)
            .on_conflict_do_nothing(
                index_elements=[PptTask.owner_id, PptTask.idempotency_key],
            )
            .returning(PptTask)
        )
        task = db.scalars(statement).one_or_none()
        created = task is not None
        if task is None:
            task = db.scalar(
                select(PptTask)
                .where(
                    PptTask.owner_id == owner_id,
                    PptTask.idempotency_key == idempotency_key,
                )
                .execution_options(populate_existing=True)
            )
            if task is None:
                raise RuntimeError("重复提交的任务暂时无法读取，请使用原编号重试")
            # The original brief is stored in these immutable task columns.
            if any(getattr(task, name) != value for name, value in values.items()):
                db.rollback()
                raise SubmissionConflictError("提交编号对应的需求与本次不一致")

    result = PptTaskCreated.model_validate(task)
    # Never report success or log task_created before the commit succeeds.
    db.commit()
    logger.info(
        "%s task_id=%s owner_id=%s submission_id=%s",
        "task_created" if created else "task_reused",
        result.id, owner_id, idempotency_key or "none",
    )
    return result, created
