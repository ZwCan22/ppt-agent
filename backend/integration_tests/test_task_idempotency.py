"""Test the real task-creation API using the shared PostgreSQL fixture."""

import unittest
from uuid import uuid4

from sqlalchemy import func, select

from integration_tests.support import TaskApiTestCase


class TaskIdempotencyTests(TaskApiTestCase):
    def setUp(self):
        super().setUp()
        self.submission_id = uuid4()
        self.headers = {"Idempotency-Key": str(self.submission_id)}
        self.brief = {
            "topic": "Reliable enterprise knowledge-base answers",
            "audience": "Product and engineering teams",
            "slide_count": 6,
            "requirements": "A short internal presentation",
            "template_id": "business_blue",
        }

    def test_repeated_submission_returns_original_task(self):
        # Act: repeat the same request with the same submission key and brief.
        first = self.client.post(
            "/api/ppt/tasks", json=self.brief, headers=self.headers,
        )
        self.assertEqual(first.status_code, 201, first.text)

        repeated = self.client.post(
            "/api/ppt/tasks", json=self.brief, headers=self.headers,
        )

        # Assert: the retry returns the original task, rather than creating one.
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(repeated.json()["id"], first.json()["id"])

        # Check the real database too: only one task belongs to this submission.
        task_count = self.db.scalar(
            select(func.count()).select_from(self.Task).where(
                self.Task.owner_id == self.current_user.id,
                self.Task.idempotency_key == self.submission_id,
            )
        )
        self.assertEqual(task_count, 1)

    def test_changed_brief_with_same_key_is_rejected(self):
        # Prepare: the first submission requests six slides.
        first = self.client.post(
            "/api/ppt/tasks",
            json=self.brief,
            headers=self.headers,
        )
        self.assertEqual(first.status_code, 201, first.text)

        # Act: reuse the submission key with a different, valid brief.
        changed_brief = {**self.brief, "slide_count": 8}
        conflict = self.client.post(
            "/api/ppt/tasks",
            json=changed_brief,
            headers=self.headers,
        )

        # Assert: reject the conflict and preserve the original task.
        self.assertEqual(conflict.status_code, 409, conflict.text)
        tasks = self.db.scalars(
            select(self.Task).where(
                self.Task.owner_id == self.current_user.id,
                self.Task.idempotency_key == self.submission_id,
            )
        ).all()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(str(tasks[0].id), first.json()["id"])
        self.assertEqual(tasks[0].slide_count, 6)


    def test_different_users_can_reuse_same_submission_key(self):
        first = self.client.post("/api/ppt/tasks", json=self.brief, headers=self.headers)
        self.assertEqual(first.status_code, 201, first.text)
        other = self.User(id=uuid4(), username=f"other_{uuid4().hex[:20]}", password_hash="not-used")
        self.db.add(other)
        self.db.flush()
        self.current_user = self.UserPublic.model_validate(other)
        second = self.client.post("/api/ppt/tasks", json=self.brief, headers=self.headers)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertNotEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(self.Task).where(
            self.Task.idempotency_key == self.submission_id,
        )), 2)

    def test_new_submission_key_creates_new_task_for_same_brief(self):
        first = self.client.post("/api/ppt/tasks", json=self.brief, headers=self.headers)
        self.assertEqual(first.status_code, 201, first.text)
        second = self.client.post("/api/ppt/tasks", json=self.brief, headers={"Idempotency-Key": str(uuid4())})
        self.assertEqual(second.status_code, 201, second.text)
        self.assertNotEqual(first.json()["id"], second.json()["id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
