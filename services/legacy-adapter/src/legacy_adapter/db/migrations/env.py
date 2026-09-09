from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from legacy_adapter.db.base import Base
from legacy_adapter.models import LegacyClaim

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url")),
                      target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url")).replace("postgresql+asyncpg://", "postgresql://")
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url
    with engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool).connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
