from fastapi import APIRouter, Query


router = APIRouter(prefix="/debug", tags=["开发验证"])


@router.get("/validate")
def validate_slide_count(
    slide_count: int = Query(default=8, ge=6, le=20),
) -> dict[str, int]:
    return {"slide_count": slide_count}


@router.get("/crash")
def simulate_internal_error() -> None:
    raise RuntimeError("教学用模拟异常")
