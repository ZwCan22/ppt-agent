"""Task query and download authorization tests using the shared API fixture."""

import unittest
from unittest.mock import patch
from uuid import uuid4

from integration_tests.support import TaskApiTestCase


class TaskAccessTests(TaskApiTestCase):
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
