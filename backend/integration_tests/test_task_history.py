from uuid import uuid4

from integration_tests.support import TaskApiTestCase


class TaskHistoryTests(TaskApiTestCase):
    def test_history_excludes_other_users_and_legacy_tasks(self):
        other = self.User(id=uuid4(), username=f"other_{uuid4().hex[:20]}", password_hash="not-used")
        self.db.add(other)
        self.db.flush()
        for owner in (other.id, None):
            self.db.add(self.Task(
                id=uuid4(), owner_id=owner, topic="Private or legacy",
                audience="Test", slide_count=6,
            ))
        self.db.flush()
        response = self.client.get("/api/ppt/tasks")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([item["id"] for item in response.json()["items"]], [str(self.own_task.id)])
        self.assertFalse(response.json()["has_more"])

    def test_pagination_returns_own_tasks_without_duplicates(self):
        extra = self.Task(id=uuid4(), owner_id=self.current_user.id,
                          topic="Second", audience="Test", slide_count=6)
        self.db.add(extra)
        self.db.flush()
        first = self.client.get("/api/ppt/tasks?limit=1&offset=0")
        second = self.client.get("/api/ppt/tasks?limit=1&offset=1")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(first.json()["has_more"])
        self.assertFalse(second.json()["has_more"])
        ids = [first.json()["items"][0]["id"], second.json()["items"][0]["id"]]
        self.assertEqual(set(ids), {str(self.own_task.id), str(extra.id)})

    def test_history_requires_login_and_valid_pagination(self):
        self.assertEqual(self.client.get("/api/ppt/tasks?limit=0").status_code, 422)
        self.assertEqual(self.client.get("/api/ppt/tasks?offset=-1").status_code, 422)
        self.app.dependency_overrides.pop(self.current_user_dependency)
        self.assertEqual(self.client.get("/api/ppt/tasks").status_code, 401)
