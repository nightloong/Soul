"""SQLite engine and session factory."""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def database_url() -> str:
    configured = os.getenv("PERSONAFORGE_DATABASE_URL")
    if configured:
        return configured
    path = Path("data/private/personaforge.db").resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def make_engine(url: str | None = None) -> Engine:
    engine = create_engine(url or database_url())
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def configure_sqlite(dbapi_connection: object, _connection_record: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            if url != "sqlite:///:memory:":
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
