import os

from dotenv import load_dotenv

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import text

from alembic import context

from backend.app.db.database import Base
from backend.app.models import (
    User,
    UserProfile,
    RoleRequest,
    Policy,
    Scheme,
    EligibilityRule,
    SearchHistory,
    Notification,
    Feedback,
    Report,
    AuditLog,
)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # knowledge_chunks stores pgvector embeddings, and CREATE EXTENSION is
    # per-database: a brand-new database never has `vector`, even when the
    # development one does (it is not in template1). Running it before any
    # migration is what makes `alembic upgrade head` work on an empty
    # database. It deliberately lives in env.py rather than inside an
    # already-applied migration, which must never be edited.
    #
    # It runs on its own short transaction: leaving the migration connection
    # already inside a transaction would stop MigrationContext from owning
    # one, and migrations that use autocommit_block() (ALTER TYPE ... ADD
    # VALUE) assert on exactly that.
    with connectable.begin() as bootstrap:
        bootstrap.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
