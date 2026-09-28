from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from personaforge.db.repository import Repository
from personaforge.db.session import make_engine
from personaforge.ingestion.pipeline import apply_file, preview_file
from personaforge.retrieval.search import search_events
from sqlalchemy import text
from sqlalchemy.orm import Session


@pytest.fixture
def imported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = f"sqlite:///{(tmp_path / 'search.db').as_posix()}"
    monkeypatch.setenv("PERSONAFORGE_DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    with Session(engine) as session:
        repository = Repository(session)
        dataset = repository.create_dataset("Synthetic")
        alice = repository.create_person(dataset.id, "Alice")
        bob = repository.create_person(dataset.id, "Bob")
        repository.add_alias(alice, "Alice")
        repository.add_alias(bob, "Bob")
        session.commit()
        path = Path("examples/synthetic-chat/project.jsonl")
        apply_file(session, path, dataset.id, preview_file(path).sha256)
        yield session, dataset, alice, bob
    engine.dispose()


def test_unique_keyword_and_attribution(imported) -> None:
    session, dataset, alice, _ = imported
    results = search_events(session, "小范围验证", dataset_id=dataset.id)
    assert len(results) == 1
    assert results[0].person_id == alice.id
    assert results[0].event_id
    assert results[0].source_locator == "line:4"


def test_person_filter_and_no_embedding(imported) -> None:
    session, dataset, alice, bob = imported
    assert search_events(session, "先做", person_id=alice.id, dataset_id=dataset.id)
    assert search_events(session, "先做", person_id=bob.id, dataset_id=dataset.id) == []


def test_dataset_delete_removes_fts_rows(imported) -> None:
    session, dataset, _, _ = imported
    session.delete(dataset)
    session.commit()
    assert session.scalar(text("SELECT count(*) FROM events_fts")) == 0
    assert search_events(session, "小范围验证") == []
