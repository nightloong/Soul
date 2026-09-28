from datetime import datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from personaforge.db.models import Claim, ClaimEvidence, Event, Evidence, Trait
from personaforge.db.repository import Repository
from personaforge.db.session import make_engine
from personaforge.distillation.merge import rebuild_persona
from personaforge.services.corrections import correct
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.fixture
def prepared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = f"sqlite:///{(tmp_path / 'correction.db').as_posix()}"
    monkeypatch.setenv("PERSONAFORGE_DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    with Session(engine) as session:
        repository = Repository(session)
        dataset = repository.create_dataset("Synthetic")
        person = repository.create_person(dataset.id, "Alice")
        event = Event(
            event_id="old-event",
            dataset_id=dataset.id,
            speaker_person_id=person.id,
            speaker_raw_name="Alice",
            timestamp=datetime(2024, 1, 1),
            event_type="message",
            text="我喜欢咖啡",
            source_type="test",
            source_file="old.txt",
            source_locator="line:1",
        )
        session.add(event)
        session.flush()
        evidence = Evidence(
            source_event_id=event.event_id,
            person_id=person.id,
            excerpt="我喜欢咖啡",
            evidence_type="explicit_self_statement",
            reliability=0.75,
            observed_at=event.timestamp,
        )
        claim = Claim(
            person_id=person.id,
            dimension="preference",
            key="coffee",
            name="coffee",
            statement="我喜欢咖啡",
            first_seen=event.timestamp,
            last_seen=event.timestamp,
        )
        session.add_all([evidence, claim])
        session.flush()
        session.add(ClaimEvidence(claim_id=claim.id, evidence_id=evidence.id, relation="support"))
        session.commit()
        rebuild_persona(session, person.id, datetime(2024, 2, 1))
        yield session, person.id, claim.id
    engine.dispose()


def test_wrong_fact_keeps_original_and_disputes_trait(prepared) -> None:
    session, person_id, claim_id = prepared
    correction = correct(session, person_id, "claim", claim_id, "wrong_fact", "这条记录不准确")
    assert correction.id
    assert session.get(Event, "old-event") is not None
    claim = session.get(Claim, claim_id)
    assert claim.status == "disputed"
    assert session.scalar(select(Trait).where(Trait.person_id == person_id)).status == "disputed"
    assert any(
        item.evidence_type == "manual_correction" for item in session.scalars(select(Evidence))
    )


def test_outdated_creates_new_claim_and_updates_trait(prepared) -> None:
    session, person_id, claim_id = prepared
    correct(session, person_id, "claim", claim_id, "outdated", "现在不喝咖啡了")
    old = session.get(Claim, claim_id)
    assert old.status == "superseded"
    assert old.superseded_by_id is not None
    assert session.get(Claim, old.superseded_by_id).statement == "现在不喝咖啡了"
    assert (
        session.scalar(select(Trait).where(Trait.person_id == person_id)).statement
        == "现在不喝咖啡了"
    )
