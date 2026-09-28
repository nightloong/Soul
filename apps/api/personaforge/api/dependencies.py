"""Database dependency with automatic migration on first use."""

from collections.abc import Iterator
from functools import lru_cache

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from personaforge.db.session import database_url, make_engine


@lru_cache(maxsize=8)
def initialized_engine(url: str) -> Engine:
    command.upgrade(Config("alembic.ini"), "head")
    return make_engine(url)


def get_session() -> Iterator[Session]:
    engine = initialized_engine(database_url())
    with Session(engine) as session:
        yield session
