from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import Base  # noqa
from app import models  # noqa — registers all model metadata with Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic runs synchronously; swap asyncpg → psycopg2 so engine_from_config works.
db_url = os.environ.get("DATABASE_URL", "postgresql+psycopg2://cue:cue@db:5432/cue")
db_url = db_url.replace("+asyncpg", "+psycopg2")
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
