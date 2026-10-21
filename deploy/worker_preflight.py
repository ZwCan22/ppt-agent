"""Check the Worker environment without claiming tasks or calling an LLM."""
from pathlib import Path
from tempfile import TemporaryDirectory


class PreflightError(RuntimeError):
    """An actionable diagnostic written by this script, without external data."""


def check_writable_directory(directory: Path) -> None:
    root = directory.resolve()
    if not root.is_dir():
        raise PreflightError("检查目录不存在，请检查Compose挂载配置")
    with TemporaryDirectory(prefix=".worker-preflight-", dir=root) as temporary:
        target = Path(temporary).resolve()
        if not target.is_relative_to(root):
            raise PreflightError("临时检查目录超出预期范围")
        source = target / "probe.tmp"
        destination = target / "probe.txt"
        source.write_text("worker-preflight", encoding="utf-8")
        source.replace(destination)
        if destination.read_text(encoding="utf-8") != "worker-preflight":
            raise PreflightError("目录读写检查未通过")


def main() -> int:
    stage = "加载配置与依赖"
    database_engine = None
    try:
        from sqlalchemy import text
        from app.core.config import settings
        from app.db.engine import engine as database_engine
        from app.clients.dify import get_app_info

        stage = "数据库连接"
        with database_engine.connect() as connection:
            database_name, user_name = connection.execute(
                text("SELECT current_database(), current_user")
            ).one()
        if database_name != settings.db_name or user_name != settings.db_user:
            raise PreflightError("实际数据库或业务账号与配置不一致")
        print("PASS 数据库连接与业务账号", flush=True)

        stage = "Dify连接与凭证"
        info = get_app_info()
        if not isinstance(info, dict) or info.get("mode") != "workflow":
            raise PreflightError("返回的应用信息不符合Workflow类型，请核对Dify应用和API Key")
        print("PASS Dify连接、凭证与Workflow应用类型", flush=True)

        stage = "PPT目录读写"
        check_writable_directory(settings.storage_dir)
        print("PASS PPT目录的写入、改名、读取与临时文件清理", flush=True)

        stage = "日志目录读写"
        check_writable_directory(settings.log_dir)
        print("PASS 日志目录读写", flush=True)
        print("全部检查通过，可以启动Worker。", flush=True)
        return 0
    except Exception as exc:
        # Do not print settings, response bodies, connection strings or keys.
        print(f"FAIL {stage}：{type(exc).__name__}", flush=True)
        if isinstance(exc, PreflightError):
            print(str(exc), flush=True)
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if isinstance(status_code, int):
            print(f"上游HTTP状态码：{status_code}", flush=True)
        print("请先定位这项检查，再启动Worker。", flush=True)
        return 1
    finally:
        if database_engine is not None:
            database_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
