"""A private schema per test for code that commits through independent sessions."""

import re
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from integration_tests.support import TaskApiTestCase


class CommittedDatabaseTestCase(TaskApiTestCase):
    def setUp(self):
        from app.db.base import Base
        self.schema = f"test_{uuid4().hex}"
        with self.engine.begin() as connection:
            connection.execute(CreateSchema(self.schema))
        self.addCleanup(self.drop_private_schema)
        self.committed_engine = self.engine.execution_options(
            schema_translate_map={"public": self.schema},
        )
        Base.metadata.create_all(self.committed_engine)

    def drop_private_schema(self):
        if not re.fullmatch(r"test_[0-9a-f]{32}", self.schema):
            raise RuntimeError("Unexpected test schema; refusing cleanup")
        with self.engine.begin() as connection:
            connection.execute(DropSchema(self.schema, cascade=True))

    def create_committed_task(self, **changes):
        values = dict(
            id=uuid4(), topic="Worker test", audience="Tests",
            slide_count=6, status="queued",
        )
        values.update(changes)
        with Session(self.committed_engine) as db:
            db.add(self.Task(**values))
            db.commit()
        return values["id"]

    def read_task(self, task_id):
        with Session(self.committed_engine) as db:
            task = db.get(self.Task, task_id)
            db.expunge(task)
            return task
