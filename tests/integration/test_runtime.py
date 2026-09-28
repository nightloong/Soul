import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from personaforge.db.models import Event, Memory, MemoryEvidence, Trait
from personaforge.db.repository import Repository
from personaforge.db.session import make_engine
from personaforge.ingestion.pipeline import apply_file, preview_file
from personaforge.runtime.service import classify_context, explain_turn, simulate
from sqlalchemy import select
from sqlalchemy.orm import Session


class FakeModel:
    model_name = "fake-simulation"
    provider_name = "test"

    def __init__(self, response: str) -> None:
        self.response = response
        self.payload = None

    async def generate(self, system: str, user: str, response_schema: dict) -> dict:
        self.payload = user
        assert "not the real person" in system
        assert "properties" in response_schema
        return {"response": self.response}


@pytest.fixture
def prepared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = f"sqlite:///{(tmp_path / 'runtime.db').as_posix()}"
    monkeypatch.setenv("PERSONAFORGE_DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    with Session(engine) as session:
        repository = Repository(session)
        dataset = repository.create_dataset("Synthetic")
        person = repository.create_person(dataset.id, "Alice")
        repository.add_alias(person, "Alice")
        session.commit()
        path = Path("examples/synthetic-chat/project.jsonl")
        apply_file(session, path, dataset.id, preview_file(path).sha256)
        trait = Trait(
            person_id=person.id,
            dimension="decision_pattern",
            key="small_first",
            statement="先小范围验证",
            context={"topic": "work"},
            confidence=0.82,
            support_count=2,
            counter_count=0,
            status="active",
        )
        session.add(trait)
        session.flush()
        first_event_id = session.scalar(
            select(Event.event_id).where(Event.speaker_person_id == person.id)
        )
        memory = Memory(
            person_id=person.id, memory_type="episodic", statement="曾讨论小测试", confidence=0.5
        )
        session.add(memory)
        session.flush()
        session.add(MemoryEvidence(memory_id=memory.id, event_id=first_event_id))
        session.commit()
        yield session, person.id, trait.id, memory.id
    engine.dispose()


def test_context_override() -> None:
    assert classify_context("项目会议", {"relationship": "colleague"}) == {
        "channel": "meeting",
        "topic": "work",
        "relationship": "colleague",
        "scenario": "meeting",
    }


def test_simulation_records_trace_and_explanation(prepared) -> None:
    session, person_id, trait_id, memory_id = prepared
    model = FakeModel("可以先做小范围测试。")
    result = asyncio.run(simulate(session, person_id, "这个项目怎么推进？", model))
    assert result.disclaimer.startswith("AI 模拟")
    assert trait_id in result.selected_trait_ids
    assert memory_id in result.selected_memory_ids
    assert 3 <= len(result.selected_event_ids) <= 5
    explanation = explain_turn(session, result.turn_id)
    assert explanation["events"][0]["source_locator"].startswith("line:")
    assert "reasoning" not in explanation
    assert "先小范围验证" in model.payload


def test_identity_claim_is_blocked(prepared) -> None:
    session, person_id, _, _ = prepared
    result = asyncio.run(simulate(session, person_id, "你好", FakeModel("我是Alice")))
    assert "我是Alice" not in result.response
