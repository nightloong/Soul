from datetime import datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from personaforge.db.models import Claim, ClaimEvidence, Conversation, Event, Evidence, Trait
from personaforge.db.repository import Repository
from personaforge.db.session import make_engine
from personaforge.distillation.merge import rebuild_persona
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.fixture
def prepared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = f"sqlite:///{(tmp_path / 'merge.db').as_posix()}"
    monkeypatch.setenv("PERSONAFORGE_DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    with Session(engine) as session:
        repository = Repository(session)
        dataset = repository.create_dataset("Synthetic")
        person = repository.create_person(dataset.id, "Alice")
        session.commit()
        yield session, dataset.id, person.id
    engine.dispose()


def add_claim(
    session: Session,
    dataset_id: str,
    person_id: str,
    event_id: str,
    conversation_id: str,
    name: str,
    statement: str,
    date: datetime,
    evidence_type: str = "direct_behavior",
) -> Claim:
    session.add(Conversation(id=conversation_id, dataset_id=dataset_id, title=conversation_id))
    session.flush()
    session.add(
        Event(
            event_id=event_id,
            dataset_id=dataset_id,
            conversation_id=conversation_id,
            speaker_person_id=person_id,
            speaker_raw_name="Alice",
            timestamp=date,
            event_type="message",
            text=statement,
            source_type="test",
            source_file="test",
            source_locator=event_id,
        )
    )
    session.flush()
    evidence = Evidence(
        source_event_id=event_id,
        person_id=person_id,
        excerpt=statement,
        evidence_type=evidence_type,
        reliability=0.75,
        observed_at=date,
    )
    claim = Claim(
        person_id=person_id,
        dimension="preference",
        key=event_id,
        name=name,
        statement=statement,
        first_seen=date,
        last_seen=date,
    )
    session.add_all([evidence, claim])
    session.flush()
    session.add(ClaimEvidence(claim_id=claim.id, evidence_id=evidence.id, relation="support"))
    session.commit()
    return claim


def test_merge_repeated_claims_into_trait(prepared) -> None:
    session, dataset_id, person_id = prepared
    first = add_claim(
        session,
        dataset_id,
        person_id,
        "e1",
        "c1",
        "Small test first",
        "先做小测试",
        datetime(2026, 1, 1),
    )
    second = add_claim(
        session,
        dataset_id,
        person_id,
        "e2",
        "c2",
        "small-test-first",
        "再次先做小测试",
        datetime(2026, 2, 1),
    )
    traits = rebuild_persona(session, person_id, datetime(2026, 3, 1))
    assert len(traits) == 1
    assert traits[0].support_count == 2
    assert traits[0].confidence == 0.75
    assert session.get(Claim, second.id).status == "superseded"
    assert session.get(Claim, second.id).superseded_by_id == first.id
    assert session.scalar(select(Trait)).status == "active"


def test_new_opposite_claim_supersedes_old(prepared) -> None:
    session, dataset_id, person_id = prepared
    old = add_claim(
        session,
        dataset_id,
        person_id,
        "e1",
        "c1",
        "coffee",
        "我喜欢咖啡",
        datetime(2024, 1, 1),
        "explicit_self_statement",
    )
    new = add_claim(
        session,
        dataset_id,
        person_id,
        "e2",
        "c2",
        "coffee",
        "现在不喝咖啡了",
        datetime(2026, 1, 1),
        "explicit_self_statement",
    )
    traits = rebuild_persona(session, person_id, datetime(2026, 2, 1))
    assert session.get(Claim, old.id).status == "superseded"
    assert session.get(Claim, old.id).superseded_by_id == new.id
    assert traits[0].statement == "现在不喝咖啡了"
