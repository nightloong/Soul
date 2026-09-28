from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from personaforge.analysis.meeting import (
    analyze_meeting,
    classify_utterance,
    derive_decision_pattern,
)
from personaforge.db.models import Claim, Conversation, Event, Evidence, Trait
from personaforge.db.repository import Repository
from personaforge.db.session import make_engine
from personaforge.ingestion.pipeline import apply_file, preview_file
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.fixture
def prepared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = f"sqlite:///{(tmp_path / 'meeting.db').as_posix()}"
    monkeypatch.setenv("PERSONAFORGE_DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    with Session(engine) as session:
        repository = Repository(session)
        dataset = repository.create_dataset("Synthetic meetings")
        alice = repository.create_person(dataset.id, "Alice")
        bob = repository.create_person(dataset.id, "Bob")
        repository.add_alias(alice, "Alice")
        repository.add_alias(bob, "Bob")
        session.commit()
        yield session, dataset.id, alice.id
    engine.dispose()


def import_meeting(session: Session, dataset_id: str, name: str) -> str:
    path = Path("examples/synthetic-meeting") / name
    result = apply_file(session, path, dataset_id, preview_file(path).sha256)
    assert result.imported > 0
    return session.scalar(select(Conversation.id).where(Conversation.title == path.stem))


def test_classification_and_evidence_backed_meeting_view(prepared) -> None:
    session, dataset_id, alice_id = prepared
    conversation_id = import_meeting(session, dataset_id, "meeting-a.txt")
    view = analyze_meeting(session, conversation_id)
    assert view["participants"] == ["Alice", "Bob"]
    assert view["speaker_distribution"] == {"Alice": 2, "Bob": 2}
    assert len(view["decisions"]) == 1
    assert view["decisions"][0]["evidence"]["source_locator"] == "line:3"
    assert view["action_items"][0]["owner"] == "Bob"
    assert view["action_items"][0]["deadline"] == "周五前"
    assert view["utterances"][0]["evidence"]["time_of_day"] == "10:31:21"
    assert "condition" in classify_utterance("如果用户愿意，就继续。")
    assert derive_decision_pattern(session, alice_id) is None
    assert session.scalar(select(Claim)) is None


def test_long_term_pattern_requires_two_meetings(prepared) -> None:
    session, dataset_id, alice_id = prepared
    import_meeting(session, dataset_id, "meeting-a.txt")
    import_meeting(session, dataset_id, "meeting-b.txt")
    claim = derive_decision_pattern(session, alice_id)
    assert claim is not None
    assert claim.dimension == "decision_pattern"
    assert claim.confidence >= 0.65
    assert session.scalar(select(Trait).where(Trait.person_id == alice_id)).support_count >= 2
    assert derive_decision_pattern(session, alice_id).id == claim.id
    events = session.scalars(
        select(Event)
        .join(Evidence, Evidence.source_event_id == Event.event_id)
        .where(Evidence.person_id == alice_id)
    )
    assert all(event.speaker_person_id == alice_id for event in events)
