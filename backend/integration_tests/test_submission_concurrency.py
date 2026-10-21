from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from integration_tests.committed_support import CommittedDatabaseTestCase


class SubmissionConcurrencyTests(CommittedDatabaseTestCase):
    def test_simultaneous_retries_commit_one_task(self):
        from app.schemas.ppt import PptBrief
        from app.services.task_creation import create_task
        owner_id, key = uuid4(), uuid4()
        with Session(self.committed_engine) as db:
            db.add(self.User(id=owner_id, username=f"user_{uuid4().hex[:20]}", password_hash="not-used"))
            db.commit()
        ready = Barrier(2)
        def submit():
            with Session(self.committed_engine) as db:
                ready.wait(timeout=5)
                result, created = create_task(
                    db, PptBrief(topic="Concurrent test", audience="Test", slide_count=6),
                    owner_id=owner_id, idempotency_key=key,
                )
                return result.id, created
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit), pool.submit(submit)]
            results = [future.result(timeout=10) for future in futures]
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(created for _, created in results), [False, True])
        with Session(self.committed_engine) as db:
            count = db.scalar(select(func.count()).select_from(self.Task))
        self.assertEqual(count, 1)
