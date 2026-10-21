"""Run actual Alembic revisions in a newly created, guarded test database."""

from pathlib import Path
import re
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from integration_tests.support import TaskApiTestCase


class MigrationTests(TaskApiTestCase):
    def setUp(self):
        self.database = f"test_migrate_{uuid4().hex}"
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            for role in ("ppt_admin", "ppt_app"):
                exists = connection.scalar(text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role})
                if not exists:
                    connection.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN')
            connection.exec_driver_sql(f'CREATE DATABASE "{self.database}" OWNER ppt_admin TEMPLATE template0')
        self.addCleanup(self.drop_test_database)
        self.migration_engine = create_engine(
            self.engine.url.set(database=self.database), poolclass=NullPool,
            hide_parameters=True, connect_args={"connect_timeout": 5},
        )
        self.addCleanup(self.migration_engine.dispose)
        self.backend = Path(__file__).resolve().parents[1]
        self.cfg = Config(str(self.backend / "alembic.ini"))
        self.cfg.set_main_option("script_location", str(self.backend / "migrations"))

        # Run the real bootstrap script as the migration role. Substitute only
        # the database identifier, since this database is deliberately temporary.
        bootstrap = (self.backend / "migrations/bootstrap.sql").read_text(encoding="utf-8-sig")
        bootstrap = "\n".join(line for line in bootstrap.splitlines() if not line.startswith("\\"))
        bootstrap = bootstrap.replace("ON DATABASE ppt_agent TO", f'ON DATABASE "{self.database}" TO')
        with self.migration_engine.begin() as connection:
            connection.exec_driver_sql("SET LOCAL ROLE ppt_admin")
            for statement in bootstrap.split(";"):
                if statement.strip():
                    connection.exec_driver_sql(statement)

    def drop_test_database(self):
        if not re.fullmatch(r"test_migrate_[0-9a-f]{32}", self.database):
            raise RuntimeError("Unexpected database name; refusing cleanup")
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.exec_driver_sql(f'DROP DATABASE "{self.database}"')

    def migrate(self, action, target=None):
        with self.migration_engine.begin() as connection:
            connection.exec_driver_sql("SET LOCAL ROLE ppt_admin")
            self.cfg.attributes["connection"] = connection
            try:
                if target is None:
                    action(self.cfg)
                else:
                    action(self.cfg, target)
            finally:
                self.cfg.attributes.pop("connection", None)

    def test_empty_database_upgrades_to_model_and_repeated_upgrade_is_safe(self):
        self.migrate(command.upgrade, "head")
        self.migrate(command.upgrade, "head")
        self.migrate(command.check)
        with self.migration_engine.connect() as connection:
            head = connection.scalar(text("SELECT version_num FROM migrations.alembic_version"))
            self.assertEqual(head, ScriptDirectory.from_config(self.cfg).get_current_head())
            self.assertEqual(set(inspect(connection).get_table_names(schema="public")),
                             {"ppt_tasks", "users", "user_sessions"})
            names = {item["name"] for item in inspect(connection).get_unique_constraints("ppt_tasks", schema="public")}
            self.assertIn("uq_ppt_tasks_owner_idempotency_key", names)

    def test_fresh_database_downgrade_and_reupgrade(self):
        self.migrate(command.upgrade, "head")
        self.migrate(command.downgrade, "base")
        with self.migration_engine.connect() as connection:
            self.assertEqual(inspect(connection).get_table_names(schema="public"), [])
        self.migrate(command.upgrade, "head")
        self.migrate(command.check)

    def test_business_role_has_dml_but_no_ddl_or_migration_access(self):
        self.migrate(command.upgrade, "head")
        with self.migration_engine.begin() as connection:
            for table in ("users", "user_sessions", "ppt_tasks"):
                for permission in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    self.assertTrue(connection.scalar(text(
                        "SELECT has_table_privilege('ppt_app', :table, :permission)"
                    ), {"table": f"public.{table}", "permission": permission}))
            connection.exec_driver_sql("SET LOCAL ROLE ppt_app")
            connection.exec_driver_sql("SELECT count(*) FROM public.ppt_tasks")
            for forbidden in (
                "CREATE TABLE public.forbidden_test(id integer)",
                "SELECT * FROM migrations.alembic_version",
            ):
                with self.assertRaises(DBAPIError) as caught:
                    with connection.begin_nested():
                        connection.exec_driver_sql(forbidden)
                self.assertEqual(caught.exception.orig.sqlstate, "42501")

    def test_real_foreign_key_drift_is_detected(self):
        from alembic.util.exc import AutogenerateDiffsDetected
        self.migrate(command.upgrade, "head")
        with self.migration_engine.begin() as connection:
            connection.exec_driver_sql("SET LOCAL ROLE ppt_admin")
            connection.exec_driver_sql(
                "ALTER TABLE public.ppt_tasks DROP CONSTRAINT fk_ppt_tasks_owner_id_users"
            )
        with self.assertRaises(AutogenerateDiffsDetected) as caught:
            self.migrate(command.check)
        self.assertIn("add_fk", str(caught.exception))
