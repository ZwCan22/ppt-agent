"""Real PostgreSQL concurrency, recovery, renewal and stale-worker fencing."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from integration_tests.committed_support import CommittedDatabaseTestCase


class WorkerLeaseTests(CommittedDatabaseTestCase):
    def setUp(self):
        super().setUp()
        from app.services import task_lease, task_runner
        self.lease = task_lease
        self.runner = task_runner
        for module in (task_lease, task_runner):
            replacement = patch.object(module, "engine", self.committed_engine)
            replacement.start()
            self.addCleanup(replacement.stop)

    def expire(self, task_id, **changes):
        with Session(self.committed_engine) as db:
            db.execute(update(self.Task).where(self.Task.id == task_id).values(
                lease_expires_at=func.now() - timedelta(seconds=1),
                **changes,
            ))
            db.commit()

    def test_two_workers_only_claim_once(self):
        task_id = self.create_committed_task()
        ready = Barrier(2)
        def claim():
            ready.wait(timeout=5)
            return self.lease.claim_task(task_id)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result(timeout=10) for future in
                       [pool.submit(claim), pool.submit(claim)]]
        self.assertEqual(sum(result is not None for result in results), 1)
        task = self.read_task(task_id)
        self.assertEqual(task.attempt_count, 1)
        self.assertEqual(task.status, "planning")

    def test_renewed_active_task_is_not_requeued(self):
        task_id = self.create_committed_task()
        claim = self.lease.claim_task(task_id)
        with Session(self.committed_engine) as db:
            db.execute(update(self.Task).where(self.Task.id == task_id).values(
                lease_expires_at=func.now() + timedelta(seconds=5),
            ))
            db.commit()
        before = self.read_task(task_id).lease_expires_at
        self.assertTrue(self.lease.renew_task_lease(task_id, claim.execution_token))
        self.assertGreater(self.read_task(task_id).lease_expires_at, before + timedelta(seconds=100))
        self.assertEqual(self.lease.recover_expired_tasks(), ([], []))
        self.assertEqual(self.read_task(task_id).status, "planning")

    def test_expired_task_is_requeued_and_old_result_cleared(self):
        task_id = self.create_committed_task()
        self.lease.claim_task(task_id)
        self.expire(task_id, outline_json={"old": True}, artifact_path="old/presentation.pptx")
        recovered, failed = self.lease.recover_expired_tasks()
        self.assertEqual(recovered, [task_id])
        self.assertEqual(failed, [])
        task = self.read_task(task_id)
        self.assertEqual(task.status, "queued")
        self.assertIsNone(task.execution_token)
        self.assertIsNone(task.lease_expires_at)
        self.assertIsNone(task.outline_json)
        self.assertIsNone(task.artifact_path)
        self.assertEqual(task.attempt_count, 1)

    def test_exhausted_task_fails_instead_of_requeue(self):
        task_id = self.create_committed_task(attempt_count=self.lease.MAX_ATTEMPTS - 1)
        self.lease.claim_task(task_id)
        self.expire(task_id)
        self.assertEqual(self.lease.recover_expired_tasks(), ([], [task_id]))
        self.assertEqual(self.read_task(task_id).status, "failed")
        self.assertIsNone(self.lease.claim_task(task_id))

    def test_wrong_or_expired_token_cannot_renew(self):
        task_id = self.create_committed_task()
        claim = self.lease.claim_task(task_id)
        self.assertFalse(self.lease.renew_task_lease(task_id, uuid4()))
        self.expire(task_id)
        self.assertFalse(self.lease.renew_task_lease(task_id, claim.execution_token))

    def test_expired_worker_cannot_save_result(self):
        from app.services.task_heartbeat import LeaseLostError
        task_id = self.create_committed_task()
        claim = self.lease.claim_task(task_id)
        self.expire(task_id)
        with self.assertRaises(LeaseLostError):
            self.runner._update_task(task_id, "planning", claim.execution_token, status="succeeded")
        self.assertEqual(self.read_task(task_id).status, "planning")

    def test_old_worker_cannot_overwrite_new_claim(self):
        from app.services.task_heartbeat import LeaseLostError
        task_id = self.create_committed_task()
        old = self.lease.claim_task(task_id)
        self.expire(task_id)
        self.lease.recover_expired_tasks()
        new = self.lease.claim_task(task_id)
        with self.assertRaises(LeaseLostError):
            self.runner._update_task(task_id, "planning", old.execution_token, status="succeeded")
        task = self.read_task(task_id)
        self.assertEqual(task.execution_token, new.execution_token)
        self.assertEqual(task.status, "planning")
        self.assertEqual(task.attempt_count, 2)

    def test_current_worker_can_advance_but_wrong_stage_cannot(self):
        from app.services.task_heartbeat import LeaseLostError
        task_id = self.create_committed_task()
        claim = self.lease.claim_task(task_id)
        self.runner._update_task(task_id, "planning", claim.execution_token, status="rendering")
        with self.assertRaises(LeaseLostError):
            self.runner._update_task(task_id, "planning", claim.execution_token, status="succeeded")
        self.assertEqual(self.read_task(task_id).status, "rendering")

    def test_heartbeat_marks_lease_lost_when_renewal_fails(self):
        from app.services import task_heartbeat
        called = Event()
        def lost(*args):
            called.set()
            return False
        with patch.object(task_heartbeat, "HEARTBEAT_SECONDS", 0.01), \
             patch.object(task_heartbeat, "renew_task_lease", side_effect=lost):
            with task_heartbeat.TaskHeartbeat(uuid4(), uuid4()) as heartbeat:
                self.assertTrue(called.wait(timeout=2))
                heartbeat._thread.join(timeout=2)
                with self.assertRaises(task_heartbeat.LeaseLostError):
                    heartbeat.check()
