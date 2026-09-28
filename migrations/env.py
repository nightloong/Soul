"""Alembic migration environment."""

from logging.config import fileConfig

import personaforge.db.models  # noqa: F401
from alembic import context
from personaforge.db.base import Base
from personaforge.db.session import database_url
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", database_url())
target_metadata = Base.metadata


def include_name(name: str | None, type_: str, _parent_names: dict) -> bool:
    return not (type_ == "table" and name is not None and name.startswith("events_fts"))


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        include_name=include_name,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, include_name=include_name
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
