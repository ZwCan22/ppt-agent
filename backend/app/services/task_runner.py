import logging
from pathlib import Path
from uuid import UUID

from pptx import Presentation
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.clients.dify import DifyOutlineError, generate_outline
from app.core.config import settings
from app.db.engine import engine
from app.models.ppt_task import PptTask
from app.renderers.pptx_renderer import render_pptx
from app.services.task_heartbeat import LeaseLostError, TaskHeartbeat
from app.services.task_lease import MAX_ATTEMPTS, claim_task

logger = logging.getLogger("ppt_agent.tasks")


def _update_task(
    task_id: UUID,
    expected_status: str,
    claim_token: UUID,
    **changes: object,
) -> None:
    with Session(engine) as db:
        statement = (
            update(PptTask)
            .where(
                PptTask.id == task_id,
                PptTask.status == expected_status,
                PptTask.execution_token == claim_token,
                PptTask.lease_expires_at > func.now(),
            )
            .values(**changes)
            .returning(PptTask.id)
        )

        changed_id = db.execute(statement).scalar_one_or_none()
        if changed_id is None:
            raise LeaseLostError("任务状态已改变或领取凭证已失效")

        db.commit()


def run_task(task_id: UUID, user_id: str) -> Path | None:
    claim = claim_task(task_id)
    if claim is None:
        return None

    brief = claim.brief
    token = claim.execution_token
    stage = "planning"

    try:
        logger.info("task_started task_id=%s", task_id)

        with TaskHeartbeat(task_id, token) as heartbeat:
            # 1. 生成大纲，并核对领取凭证
            outline = generate_outline(brief, user_id=user_id, task_id=task_id)
            heartbeat.check()
            _update_task(
                task_id,
                stage,
                token,
                status="rendering",
                outline_json=outline.model_dump(mode="json"),
            )
            stage = "rendering"

            # 2. 每次执行都使用独立文件夹
            relative_path = (
                Path(str(task_id))
                / str(token)
                / "presentation.pptx"
            )
            output_path = settings.storage_dir.resolve() / relative_path
            temporary_path = output_path.with_name("presentation.tmp.pptx")

            render_pptx(outline, temporary_path)
            heartbeat.check()
            _update_task(
                task_id,
                stage,
                token,
                status="checking",
            )
            stage = "checking"

            # 3. 检查文件和页数
            presentation = Presentation(str(temporary_path))
            if len(presentation.slides) != brief.slide_count:
                raise ValueError("PPT文件页数与需求不一致")

            heartbeat.check()
            temporary_path.replace(output_path)

        # 4. 停止心跳后，核对凭证并登记完成
        heartbeat.check()
        _update_task(
            task_id,
            stage,
            token,
            status="succeeded",
            artifact_path=relative_path.as_posix(),
            error_message=None,
            execution_token=None,
            lease_expires_at=None,
        )
        logger.info("task_succeeded task_id=%s", task_id)
        return output_path

    except LeaseLostError:
        # 当前执行没有资格再修改任务，交给恢复逻辑处理
        logger.warning(
            "task_execution_abandoned task_id=%s stage=%s",
            task_id,
            stage,
        )
        return None

    except Exception as exc:
        error_code = (
            exc.code if isinstance(exc, DifyOutlineError)
            else "TASK_EXECUTION_FAILED"
        )
        dify_run_id = (
            exc.run_id if isinstance(exc, DifyOutlineError) else None
        )
        logger.exception(
            "task_failed task_id=%s stage=%s error_code=%s dify_run_id=%s",
            task_id,
            stage,
            error_code,
            dify_run_id or "unknown",
        )
        try:
            _update_task(
                task_id,
                stage,
                token,
                status="failed",
                artifact_path=None,
                error_message="制作失败，请根据任务编号查看后台日志",
                execution_token=None,
                lease_expires_at=None,
            )
        except LeaseLostError:
            logger.warning(
                "task_failure_save_skipped task_id=%s", task_id
            )
        except Exception:
            logger.exception(
                "task_failure_save_failed task_id=%s", task_id
            )
        raise


def get_next_task_id() -> UUID | None:
    with Session(engine) as db:
        statement = (
            select(PptTask.id)
            .where(
                PptTask.status == "queued",
                PptTask.attempt_count < MAX_ATTEMPTS,
            )
            .order_by(PptTask.created_at, PptTask.id)
            .limit(1)
        )
        return db.execute(statement).scalar_one_or_none()