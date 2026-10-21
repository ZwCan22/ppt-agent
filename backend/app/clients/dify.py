import logging
import re
from uuid import UUID

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.outline import PptOutline
from app.schemas.ppt import PptBrief

logger = logging.getLogger("ppt_agent.dify")


class DifyOutlineError(RuntimeError):
    """Keep a stable error code and the upstream workflow run ID."""

    def __init__(self, code: str, message: str, run_id: str | None = None):
        self.code = code
        self.run_id = run_id
        super().__init__(f"{code}: {message}")


def _run_id(payload: dict, data: dict) -> str | None:
    for value in (payload.get("workflow_run_id"), data.get("id")):
        if isinstance(value, str):
            try:
                return str(UUID(value))
            except ValueError:
                pass
    return None


def _safe_error(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "Dify未提供具体原因，请查看对应运行记录"
    # Do not dump the response body; retain a bounded, single-line error only.
    value = value.replace(settings.dify_api_key.get_secret_value(), "[REDACTED]")
    value = re.sub(r"(?i)\bBearer\s+[^\s\"'<>]+", "Bearer [REDACTED]", value)
    value = re.sub(r"\b(?:app|sk)-[A-Za-z0-9_-]+", "[REDACTED]", value)
    value = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", value)
    value = " ".join(value.split())
    return value if len(value) <= 600 else value[:600] + "…[已截断]"


def get_app_info() -> dict:
    base_url = str(settings.dify_base_url).rstrip("/")
    headers = {
        "Authorization": f"Bearer {settings.dify_api_key.get_secret_value()}"
    }
    with httpx.Client(timeout=10.0, trust_env=False) as client:
        response = client.get(f"{base_url}/info", headers=headers)
        response.raise_for_status()
    return response.json()


def generate_outline(
    brief: PptBrief,
    user_id: str,
    *,
    task_id: UUID | None = None,
) -> PptOutline:
    base_url = str(settings.dify_base_url).rstrip("/")
    headers = {
        "Authorization": f"Bearer {settings.dify_api_key.get_secret_value()}"
    }
    body = {
        "inputs": {
            "topic": brief.topic,
            "audience": brief.audience,
            "slide_count": str(brief.slide_count),
            "requirements": brief.requirements,
        },
        "response_mode": "blocking",
        "user": user_id,
    }
    logger.info("dify_outline_started task_id=%s", task_id or "unknown")
    timeout = httpx.Timeout(settings.dify_timeout_seconds, connect=5.0)
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.post(
                f"{base_url}/workflows/run", headers=headers, json=body
            )
    except httpx.TimeoutException:
        raise DifyOutlineError(
            "DIFY_TIMEOUT", "等待Dify响应超时，不能据此断定Dify内部运行已经停止"
        ) from None
    except httpx.RequestError:
        raise DifyOutlineError(
            "DIFY_CONNECTION_ERROR", "连接Dify失败，请检查服务和网络"
        ) from None

    if not response.is_success:
        raise DifyOutlineError(
            "DIFY_HTTP_ERROR", f"Dify返回HTTP {response.status_code}，请检查服务及凭证"
        )
    try:
        payload = response.json()
    except ValueError:
        raise DifyOutlineError(
            "DIFY_INVALID_RESPONSE", "Dify返回内容不是有效JSON"
        ) from None

    if not isinstance(payload, dict):
        raise DifyOutlineError("DIFY_INVALID_RESPONSE", "Dify返回的JSON不是对象")
    data = payload.get("data")
    run_id = _run_id(payload, data if isinstance(data, dict) else {})
    if not isinstance(data, dict):
        raise DifyOutlineError("DIFY_INVALID_RESPONSE", "Dify返回缺少data对象", run_id)

    logger.info(
        "dify_outline_response task_id=%s dify_run_id=%s",
        task_id or "unknown", run_id or "unknown",
    )
    if data.get("status") != "succeeded":
        raise DifyOutlineError(
            "DIFY_WORKFLOW_FAILED", _safe_error(data.get("error")), run_id
        )
    outputs = data.get("outputs")
    if not isinstance(outputs, dict) or "outline" not in outputs:
        raise DifyOutlineError(
            "DIFY_OUTPUT_MISSING", "Dify缺少outline输出，请检查结束节点并重新发布", run_id
        )
    try:
        outline = PptOutline.model_validate(outputs["outline"])
    except ValidationError as exc:
        # ValidationError.__str__ includes input values; log field/type only.
        errors = exc.errors(include_input=False, include_context=False, include_url=False)
        summary = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'outline'}:{error['type']}"
            for error in errors[:3]
        )
        raise DifyOutlineError(
            "DIFY_OUTLINE_INVALID", f"大纲结构校验失败：{_safe_error(summary)}", run_id
        ) from None

    if len(outline.slides) != brief.slide_count:
        raise DifyOutlineError(
            "DIFY_OUTLINE_INVALID",
            f"大纲页数不符：需要{brief.slide_count}页，实际{len(outline.slides)}页", run_id,
        )
    for index, slide in enumerate(outline.slides):
        expected = (
            "cover" if index == 0
            else "closing" if index == brief.slide_count - 1
            else "content"
        )
        if slide.kind != expected:
            raise DifyOutlineError(
                "DIFY_OUTLINE_INVALID", f"第{index + 1}页类型应为{expected}", run_id
            )
    logger.info(
        "dify_outline_succeeded task_id=%s dify_run_id=%s slide_count=%s",
        task_id or "unknown", run_id or "unknown", len(outline.slides),
    )
    return outline
