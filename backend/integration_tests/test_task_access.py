"""Exercise the real task API and SQL against the dedicated test database.

Run this suite in its own Python process. Authentication is overridden with a
known user here; these tests do not verify passwords or session cookies.
"""

import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session


class TaskAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Environment variables take priority over the project's .env values.
        # Only the dedicated test connection is allowed in this process.
        environment = patch.dict(os.environ, {
            "PPT_APP_ENV": "test",
            "PPT_DB_HOST": "127.0.0.1",
            "PPT_DB_PORT": "15433",
            "PPT_DB_NAME": "ppt_agent_test",
            "PPT_DB_USER": "ppt_test",
            "PPT_DB_PASSWORD": "ppt_test_local_only",
            "PPT_DIFY_BASE_URL": "http://dify.test/v1",
            "PPT_DIFY_API_KEY": "app-integration-test-only",
        })
        environment.start()
        cls.addClassCleanup(environment.stop)

        from app.core.config import settings

        actual = (
            settings.app_env, settings.db_host, settings.db_port,
            settings.db_name, settings.db_user,
            settings.db_password.get_secret_value(),
        )
        expected = (
            "test", "127.0.0.1", 15433, "ppt_agent_test",
            "ppt_test", "ppt_test_local_only",
        )
        if actual != expected:
            raise RuntimeError(
                "Refusing to run: test configuration does not match. "
                "Run this integration suite in a fresh Python process."
            )

        from app.api.ppt import router, get_current_user, get_db
        from app.db.base import Base
        from app.models.ppt_task import PptTask
        from app.models.user import User
        from app.models.user_session import UserSession
        from app.schemas.user import UserPublic

        cls.router = router
        cls.current_user_dependency = staticmethod(get_current_user)
        cls.database_dependency = staticmethod(get_db)
        cls.Task = PptTask
        cls.User = User
        cls.UserPublic = UserPublic

        # Fixed address: never derive a writable connection from business settings.
        url = URL.create(
            "postgresql+psycopg",
            username="ppt_test",
            password="ppt_test_local_only",
            host="127.0.0.1",
            port=15433,
            database="ppt_agent_test",
        )
        cls.engine = create_engine(
            url, hide_parameters=True,
            connect_args={"connect_timeout": 5},
        )
        cls.addClassCleanup(cls.engine.dispose)

        with cls.engine.begin() as connection:
            identity = connection.execute(text(
                "SELECT current_database(), current_user"
            )).one()
            if tuple(identity) != ("ppt_agent_test", "ppt_test"):
                raise RuntimeError("Refusing to write to an unexpected database")

            # Create only test tables. Migration execution is a separate check.
            Base.metadata.create_all(connection, tables=[
                User.__table__, UserSession.__table__, PptTask.__table__,
            ])

    def setUp(self):
        # Each test owns a transaction. Cleanup runs even if an assertion fails.
        connection = self.engine.connect()
        self.addCleanup(connection.close)
        transaction = connection.begin()
        self.addCleanup(lambda: transaction.rollback() if transaction.is_active else None)
        self.db = Session(bind=connection, join_transaction_mode="create_savepoint")
        self.addCleanup(self.db.close)

        user = self.User(
            id=uuid4(),
            username=f"test_{uuid4().hex[:20]}",
            password_hash="not-used-by-this-test",
        )
        self.db.add(user)
        self.db.flush()
        self.current_user = self.UserPublic.model_validate(user)

        self.own_task = self.Task(
            id=uuid4(),
            owner_id=user.id,
            topic="My test presentation",
            audience="Test audience",
            slide_count=6,
            status="queued",
        )
        self.db.add(self.own_task)
        self.db.flush()

        def test_database():
            yield self.db

        def test_current_user():
            return self.current_user

        self.app = FastAPI()
        self.app.include_router(self.router, prefix="/api")
        self.app.dependency_overrides[self.database_dependency] = test_database
        self.app.dependency_overrides[self.current_user_dependency] = test_current_user
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_owner_can_read_own_task(self):
        # Arrange: setUp has inserted a task owned by the current test user.

        # Act: send an HTTP request through the real task router.
        response = self.client.get(f"/api/ppt/tasks/{self.own_task.id}")

        # Assert: both the HTTP status and returned task must be correct.
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["id"], str(self.own_task.id))
        self.assertEqual(response.json()["topic"], "My test presentation")

    def test_user_cannot_read_another_users_task(self):
        # 准备：创建另一个用户。
        other_user = self.User(
            id=uuid4(),
            username=f"other_{uuid4().hex[:20]}",
            password_hash="not-used-by-this-test",
        )
        self.db.add(other_user)
        self.db.flush()

        # 准备：创建属于另一个用户的任务。
        other_task = self.Task(
            id=uuid4(),
            owner_id=other_user.id,
            topic="Another user's presentation",
            audience="Test audience",
            slide_count=6,
            status="queued",
        )
        self.db.add(other_task)
        self.db.flush()

        # 执行：当前登录用户保持不变，尝试查询别人的任务。
        response = self.client.get(
            f"/api/ppt/tasks/{other_task.id}"
        )

        # 检查：接口不得返回这条任务。
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(response.json()["detail"], "任务不存在")

    def test_anonymous_user_cannot_read_task(self):
        # 准备：撤销模拟登录用户，让真实登录检查生效。
        self.app.dependency_overrides.pop(
            self.current_user_dependency
        )

        # 执行：没有携带登录凭证，直接查询任务。
        response = self.client.get(
            f"/api/ppt/tasks/{self.own_task.id}"
        )

        # 检查：接口必须拒绝未登录的请求。
        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(
            response.headers.get("Cache-Control"),
            "no-store",
        )

    def test_only_owner_can_download_completed_ppt(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from app.api.ppt import settings

        # 准备：创建另一个用户 B。
        other_user = self.User(
            id=uuid4(),
            username=f"other_{uuid4().hex[:20]}",
            password_hash="not-used-by-this-test",
        )
        self.db.add(other_user)
        self.db.flush()

        # 准备：创建属于 B 的已完成任务。
        other_task = self.Task(
            id=uuid4(),
            owner_id=other_user.id,
            topic="Private presentation",
            audience="Test audience",
            slide_count=6,
            status="succeeded",
            artifact_path="presentation.pptx",
        )
        self.db.add(other_task)
        self.db.flush()

        with TemporaryDirectory() as directory:
            storage = Path(directory)
            file_content = b"test-download-content"
            (storage / "presentation.pptx").write_bytes(file_content)

            # 临时让下载接口从测试目录读取文件。
            with patch.object(settings, "storage_dir", storage):
                url = f"/api/ppt/tasks/{other_task.id}/download"

                # 当前用户 A：不能下载 B 的文件。
                denied = self.client.get(url)
                self.assertEqual(denied.status_code, 404, denied.text)
                self.assertEqual(denied.json()["detail"], "任务不存在")

                # 切换到文件所有者 B：应当可以下载。
                self.current_user = self.UserPublic.model_validate(
                    other_user
                )
                allowed = self.client.get(url)
                self.assertEqual(allowed.status_code, 200, allowed.text)
                self.assertEqual(allowed.content, file_content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
