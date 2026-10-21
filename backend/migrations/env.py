from getpass import getpass
import logging

from alembic import context
from sqlalchemy import MetaData, create_engine, pool
from sqlalchemy.schema import BLANK_SCHEMA
from sqlalchemy.engine import URL
from app.models.user_session import UserSession
from app.core.config import settings
from app.db.base import Base
from app.models.ppt_task import PptTask  # Registers the table in Base.metadata.
from app.models.user import User


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
)

def normalize_referred_schema(table, to_schema, constraint, referred_schema):
    return BLANK_SCHEMA if referred_schema == "public" else referred_schema


# PostgreSQL reflects the default public schema as None. Compare a metadata
# copy using that same convention, without changing the runtime ORM models.
target_metadata = MetaData(naming_convention=Base.metadata.naming_convention)
for model_table in Base.metadata.sorted_tables:
    model_table.to_metadata(
        target_metadata,
        schema=None if model_table.schema == "public" else model_table.schema,
        referred_schema_fn=normalize_referred_schema,
    )


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name in (None, "public")
    return True


def run_migrations_offline() -> None:
    context.configure(
        url="postgresql+psycopg://",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="migrations",
        include_schemas=True,
        include_name=include_name,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def configure_connection(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema="migrations",
        include_schemas=True,
        include_name=include_name,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_connection = context.config.attributes.get("connection")
    if supplied_connection is not None:
        configure_connection(supplied_connection)
        return

    password = getpass(
        f"Migration: {settings.db_host}:{settings.db_port}/"
        f"{settings.db_name}; password for ppt_admin: "
    )
    if not password:
        raise RuntimeError("Migration administrator password is required")

    migration_url = URL.create(
        drivername="postgresql+psycopg",
        username="ppt_admin",
        password=password,
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )
    migration_engine = create_engine(
        migration_url,
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": 5},
        hide_parameters=True,
        echo=False,
    )
    try:
        with migration_engine.connect() as connection:
            configure_connection(connection)
    finally:
        migration_engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
