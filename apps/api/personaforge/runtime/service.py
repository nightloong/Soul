"""Compose a small relevant persona and record each AI simulation turn."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from personaforge.db.models import Event, Memory, MemoryEvidence, Person, SimulationTurn, Trait
from personaforge.providers.chat import ChatModel
from personaforge.retrieval.persona import retrieve_traits
from personaforge.retrieval.search import search_events

DISCLAIMER = "AI 模拟，不代表真实人物当前观点。"
PROMPT_PATH = Path(__file__).resolve().parents[4] / "prompts/runtime/v1.md"


class SimulatedReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response: str = Field(min_length=1)


@dataclass
class SimulationResult:
    turn_id: str
    response: str
    disclaimer: str
    selected_trait_ids: list[str]
    selected_event_ids: list[str]
    selected_memory_ids: list[str]


def classify_context(message: str, overrides: dict | None = None) -> dict[str, str]:
    result = {
        "channel": "chat",
        "topic": "general",
        "relationship": "unspecified",
        "scenario": "conversation",
    }
    if re.search(r"会议|meeting", message, re.IGNORECASE):
        result.update(channel="meeting", scenario="meeting")
    if re.search(r"项目|方案|架构|代码|project|architecture", message, re.IGNORECASE):
        result["topic"] = "work"
    if overrides:
        for key in result:
            if key in overrides and overrides[key]:
                result[key] = str(overrides[key])[:100]
    return result


def retrieve_memories(session: Session, person_id: str, limit: int = 4) -> list[Memory]:
    return list(
        session.scalars(
            select(Memory)
            .join(MemoryEvidence, MemoryEvidence.memory_id == Memory.id)
            .where(Memory.person_id == person_id)
            .distinct()
            .order_by(Memory.confidence.desc())
            .limit(limit)
        )
    )


def retrieve_examples(
    session: Session, person: Person, message: str, limit: int = 5
) -> list[Event]:
    words = re.findall(r"[\u4e00-\u9fff]{3,}|[A-Za-z]{3,}", message)
    found: list[Event] = []
    seen: set[str] = set()
    for word in words[:3]:
        for result in search_events(
            session, word[:8], person_id=person.id, dataset_id=person.dataset_id, limit=limit
        ):
            event = session.get(Event, result.event_id)
            if event and event.event_id not in seen:
                seen.add(event.event_id)
                found.append(event)
                if len(found) >= limit:
                    return found
    if len(found) < min(3, limit):
        recent = session.scalars(
            select(Event)
            .where(Event.speaker_person_id == person.id, Event.text.is_not(None))
            .order_by(Event.timestamp.desc())
            .limit(limit)
        )
        for event in recent:
            if event.event_id not in seen:
                seen.add(event.event_id)
                found.append(event)
                if len(found) >= limit:
                    break
    return found


async def simulate(
    session: Session,
    person_id: str,
    user_input: str,
    model: ChatModel,
    *,
    context_overrides: dict | None = None,
) -> SimulationResult:
    person = session.get(Person, person_id)
    if person is None:
        raise ValueError("Person not found")
    if not user_input.strip():
        raise ValueError("Message is required")
    context = classify_context(user_input, context_overrides)
    traits = retrieve_traits(session, person_id, context=context, limit=8)
    memories = retrieve_memories(session, person_id, limit=4)
    examples = retrieve_examples(session, person, user_input, limit=5)
    payload = {
        "person_display_name": person.display_name,
        "current_context": context,
        "user_input": user_input,
        "traits": [
            {"id": item.id, "statement": item.statement, "confidence": item.confidence}
            for item in traits
        ],
        "memories": [{"id": item.id, "statement": item.statement} for item in memories],
        "historical_examples": [
            {"event_id": item.event_id, "text": (item.text or "")[:500]} for item in examples
        ],
    }
    raw = await model.generate(
        PROMPT_PATH.read_text(encoding="utf-8"),
        json.dumps(payload, ensure_ascii=False),
        SimulatedReply.model_json_schema(),
    )
    response = SimulatedReply.model_validate(raw).response.strip()
    if re.search(
        rf"我是\s*{re.escape(person.display_name)}|I am\s+{re.escape(person.display_name)}",
        response,
        re.IGNORECASE,
    ):
        response = "现有历史资料不足以可靠模拟这次回答。"
    if response in {item.text for item in examples}:
        response = "现有历史资料不足以可靠模拟这次回答。"
    turn = SimulationTurn(
        person_id=person_id,
        user_input=user_input,
        selected_trait_ids=[item.id for item in traits],
        selected_event_ids=[item.event_id for item in examples],
        selected_memory_ids=[item.id for item in memories],
        model=model.model_name,
        response=response,
    )
    session.add(turn)
    session.commit()
    return SimulationResult(
        turn_id=turn.id,
        response=response,
        disclaimer=DISCLAIMER,
        selected_trait_ids=turn.selected_trait_ids,
        selected_event_ids=turn.selected_event_ids,
        selected_memory_ids=turn.selected_memory_ids,
    )


def explain_turn(session: Session, turn_id: str) -> dict:
    turn = session.get(SimulationTurn, turn_id)
    if turn is None:
        raise ValueError("Simulation turn not found")
    return {
        "turn_id": turn.id,
        "disclaimer": DISCLAIMER,
        "traits": [
            {"id": item.id, "statement": item.statement, "confidence": item.confidence}
            for item in session.scalars(select(Trait).where(Trait.id.in_(turn.selected_trait_ids)))
        ],
        "events": [
            {
                "event_id": item.event_id,
                "text": item.text,
                "source_file": item.source_file,
                "source_locator": item.source_locator,
            }
            for item in session.scalars(
                select(Event).where(Event.event_id.in_(turn.selected_event_ids))
            )
        ],
        "memories": [
            {"id": item.id, "statement": item.statement}
            for item in session.scalars(
                select(Memory).where(Memory.id.in_(turn.selected_memory_ids))
            )
        ],
    }
