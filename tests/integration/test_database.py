from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from personaforge.db.models import (
    Claim,
    ClaimEvidence,
    Conversation,
    Dataset,
    Event,
    Evidence,
    Person,
    SourceFile,
)
from personaforge.db.repository import Repository
from personaforge.db.session import make_engine
from personaforge.services.catalog import CatalogService
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    monkeypatch.setenv("PERSONAFORGE_DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = make_engine(url)
    with Session(engine) as current:
        yield current
    engine.dispose()


def test_create_dataset(session: Session) -> None:
    dataset = CatalogService(session).create_dataset("Research")
    session.commit()
    assert session.get(Dataset, dataset.id).name == "Research"


def test_person_alias_mapping(session: Session) -> None:
    repository = Repository(session)
    dataset = repository.create_dataset("Research")
    person = repository.create_person(dataset.id, "张三")
    repository.add_alias(person, "老张")
    session.commit()
    assert repository.resolve_alias(dataset.id, "老张").id == person.id
    assert repository.resolve_alias(dataset.id, "Unknown") is None


def test_event_foreign_key(session: Session) -> None:
    session.add(
        Event(
            event_id="evt_missing_dataset",
            dataset_id="missing",
            speaker_raw_name="A",
            event_type="message",
            source_type="test",
            source_file="test.txt",
            source_locator="line:1",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_evidence_requires_existing_event(session: Session) -> None:
    repository = Repository(session)
    dataset = repository.create_dataset("Research")
    person = repository.create_person(dataset.id, "A")
    session.add(
        Evidence(
            source_event_id="missing",
            person_id=person.id,
            excerpt="Example",
            evidence_type="direct_behavior",
            reliability=0.8,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_dataset_delete_cascade(session: Session) -> None:
    repository = Repository(session)
    dataset = repository.create_dataset("Research")
    person = repository.create_person(dataset.id, "A")
    source = SourceFile(dataset_id=dataset.id, filename="a.txt", sha256="a" * 64, source_type="txt")
    conversation = Conversation(dataset_id=dataset.id, title="Test")
    session.add_all([source, conversation])
    session.flush()
    event = Event(
        event_id="evt_1",
        dataset_id=dataset.id,
        source_file_id=source.id,
        conversation_id=conversation.id,
        speaker_person_id=person.id,
        speaker_raw_name="A",
        event_type="message",
        text="Example",
        source_type="txt",
        source_file="a.txt",
        source_locator="line:1",
    )
    session.add(event)
    session.flush()
    evidence = Evidence(
        source_event_id=event.event_id,
        person_id=person.id,
        excerpt="Example",
        evidence_type="direct_behavior",
        reliability=0.8,
    )
    claim = Claim(
        person_id=person.id,
        dimension="preference",
        key="example",
        name="Example",
        statement="Example",
    )
    session.add_all([evidence, claim])
    session.flush()
    session.add(ClaimEvidence(claim_id=claim.id, evidence_id=evidence.id, relation="support"))
    session.commit()
    session.delete(dataset)
    session.commit()
    for model in (Dataset, Person, SourceFile, Conversation, Event, Evidence, Claim, ClaimEvidence):
        assert session.scalar(select(model)) is None


def test_migration_upgrade_from_empty_db(session: Session) -> None:
    names = set(inspect(session.bind).get_table_names())
    assert {"datasets", "events", "evidence", "claims", "traits"} <= names
    assert session.scalar(text("PRAGMA foreign_keys")) == 1
    assert session.scalar(text("PRAGMA journal_mode")) == "wal"
