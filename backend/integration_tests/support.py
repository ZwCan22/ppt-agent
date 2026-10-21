"""Shared test database, transaction and API setup; contains no test methods."""

import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session


class TaskApiTestCase(unittest.TestCase):
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
            connect_args={
                "connect_timeout": 5,
                "options": "-c statement_timeout=10000 -c lock_timeout=5000",
            },

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
