import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from personaforge.db.models import Claim, Event, Evidence, Memory, MemoryEvidence
from personaforge.db.repository import Repository
from personaforge.db.session import make_engine
from personaforge.distillation.service import distill_person
from sqlalchemy import func, select
from sqlalchemy.orm import Session


class FakeModel:
    model_name = "fake-structured"
    provider_name = "test"

    def __init__(self, evidence_id: str, memory_id: str) -> None:
        self.evidence_id = evidence_id
        self.memory_id = memory_id
        self.calls = 0

    async def generate(self, system: str, user: str, response_schema: dict) -> dict:
        assert "untrusted data" in system
        assert "properties" in response_schema
        self.calls += 1
        return {
            "batch_summary": "Synthetic planning exchange",
            "claims": [
                {
                    "dimension": "decision_pattern",
                    "name": "small_test_first",
                    "statement": "Prefers a small test first",
                    "context": {},
                    "confidence_hint": 0.99,
                    "evidence": [
                        {
                            "event_id": self.evidence_id,
                            "relation": "support",
                            "excerpt": "先做小测试",
                        }
                    ],
                }
            ],
            "memories": [
                {
                    "memory_type": "episodic",
                    "statement": "Discussed a small test",
                    "event_ids": [self.memory_id],
                }
            ],
        }


@pytest.fixture
def prepared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = f"sqlite:///{(tmp_path / 'distill.db').as_posix()}"
    monkeypatch.setenv("PERSONAFORGE_DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    with Session(engine) as session:
        repository = Repository(session)
        dataset = repository.create_dataset("Synthetic")
        alice = repository.create_person(dataset.id, "Alice")
        bob = repository.create_person(dataset.id, "Bob")
        for event_id, speaker in (("alice-1", alice), ("bob-1", bob)):
            session.add(
                Event(
                    event_id=event_id,
                    dataset_id=dataset.id,
                    conversation_id=None,
                    speaker_person_id=speaker.id,
                    speaker_raw_name=speaker.display_name,
                    event_type="message",
                    text="先做小测试",
                    source_type="test",
                    source_file="test.jsonl",
                    source_locator=event_id,
                )
            )
        session.commit()
        yield session, dataset.id, alice.id, bob.id
    engine.dispose()


def test_fake_event_is_rejected(prepared) -> None:
    session, dataset_id, alice_id, _ = prepared
    result = asyncio.run(distill_person(session, dataset_id, alice_id, FakeModel("fake", "fake")))
    assert result.claims_rejected == 2  # one per conversation batch
    assert session.scalar(select(func.count()).select_from(Claim)) == 0


def test_wrong_speaker_is_rejected(prepared) -> None:
    session, dataset_id, alice_id, _ = prepared
    result = asyncio.run(distill_person(session, dataset_id, alice_id, FakeModel("bob-1", "bob-1")))
    assert result.claims_created == 0
    assert session.scalar(select(func.count()).select_from(Evidence)) == 0


def test_valid_evidence_claim_memory_and_idempotency(prepared) -> None:
    session, dataset_id, alice_id, _ = prepared
    model = FakeModel("alice-1", "alice-1")
    first = asyncio.run(distill_person(session, dataset_id, alice_id, model))
    second = asyncio.run(distill_person(session, dataset_id, alice_id, model))
    assert first.claims_created == 1
    assert first.memories_created == 1
    assert second.runs_reused == 2
    assert model.calls == 2
    assert session.scalar(select(Claim)).confidence == 0.0
    assert session.scalar(select(Evidence)).source_event_id == "alice-1"
    assert session.scalar(select(Memory)).statement == "Discussed a small test"
    assert session.scalar(select(MemoryEvidence)).event_id == "alice-1"


def test_streaming_batches_report_progress(prepared) -> None:
    session, dataset_id, alice_id, _ = prepared
    progress: list[int] = []
    result = asyncio.run(
        distill_person(
            session,
            dataset_id,
            alice_id,
            FakeModel("alice-1", "alice-1"),
            max_chars=1,
            on_progress=progress.append,
        )
    )
    assert result.runs_created == 2
    assert progress == [1, 2]
