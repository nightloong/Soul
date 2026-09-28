"""Structured extraction with strict source and speaker validation."""

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from personaforge.db.models import (
    Claim,
    ClaimEvidence,
    DistillationRun,
    Event,
    Evidence,
    Memory,
    MemoryEvidence,
)
from personaforge.distillation.schemas import ExtractedClaim, ExtractionBatch
from personaforge.providers.chat import ChatModel

PROMPT_VERSION = "extraction/v1"
PROMPT_PATH = Path(__file__).resolve().parents[4] / "prompts/extraction/v1.md"


@dataclass
class DistillationResult:
    runs_created: int = 0
    runs_reused: int = 0
    claims_created: int = 0
    memories_created: int = 0
    claims_rejected: int = 0
    memories_rejected: int = 0


def segment_by_conversation(
    events: Iterable[Event], max_chars: int = 12000
) -> Iterator[list[Event]]:
    current_key: str | None = None
    batch: list[Event] = []
    size = 0
    for event in events:
        key = event.conversation_id or event.event_id
        entry_size = len(event.text or "") + 120
        if batch and (key != current_key or size + entry_size > max_chars):
            yield batch
            batch, size = [], 0
        current_key = key
        batch.append(event)
        size += entry_size
    if batch:
        yield batch


def valid_claim(claim: ExtractedClaim, events: dict[str, Event], person_id: str) -> bool:
    for evidence in claim.evidence:
        event = events.get(evidence.event_id)
        if event is None or event.speaker_person_id != person_id:
            return False
        if evidence.excerpt not in (event.text or ""):
            return False
    return True


async def distill_person(
    session: Session,
    dataset_id: str,
    person_id: str,
    model: ChatModel,
    *,
    max_chars: int = 12000,
    on_progress: Callable[[int], None] | None = None,
) -> DistillationResult:
    events = session.scalars(
        select(Event)
        .where(Event.dataset_id == dataset_id)
        .order_by(Event.conversation_id, Event.timestamp, Event.source_locator)
        .execution_options(yield_per=500)
    )
    result = DistillationResult()
    system = PROMPT_PATH.read_text(encoding="utf-8")
    processed = 0
    for batch in segment_by_conversation(events, max_chars):
        processed += len(batch)
        event_map = {event.event_id: event for event in batch}
        payload = {
            "target_person_id": person_id,
            "events": [
                {
                    "event_id": event.event_id,
                    "speaker_person_id": event.speaker_person_id,
                    "speaker_raw_name": event.speaker_raw_name,
                    "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                    "text": event.text,
                }
                for event in batch
            ],
        }
        user = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        input_hash = hashlib.sha256(user.encode("utf-8")).hexdigest()
        existing = session.scalar(
            select(DistillationRun).where(
                DistillationRun.dataset_id == dataset_id,
                DistillationRun.input_hash == input_hash,
                DistillationRun.prompt_version == PROMPT_VERSION,
                DistillationRun.model == model.model_name,
                DistillationRun.status == "completed",
            )
        )
        if existing:
            result.runs_reused += 1
            if on_progress:
                on_progress(processed)
            continue
        run = DistillationRun(
            dataset_id=dataset_id,
            model=model.model_name,
            provider=model.provider_name,
            prompt_version=PROMPT_VERSION,
            input_hash=input_hash,
            status="running",
        )
        session.add(run)
        session.flush()
        try:
            raw = await model.generate(system, user, ExtractionBatch.model_json_schema())
            extracted = ExtractionBatch.model_validate(raw)
            for candidate in extracted.claims:
                if not valid_claim(candidate, event_map, person_id):
                    result.claims_rejected += 1
                    continue
                claim = Claim(
                    person_id=person_id,
                    dimension=candidate.dimension,
                    key=hashlib.sha256(candidate.name.encode("utf-8")).hexdigest()[:16],
                    name=candidate.name,
                    statement=candidate.statement,
                    context=candidate.context,
                    confidence=0.0,
                    status="weak",
                    first_seen=min(
                        (
                            event_map[item.event_id].timestamp
                            for item in candidate.evidence
                            if event_map[item.event_id].timestamp
                        ),
                        default=None,
                    ),
                    last_seen=max(
                        (
                            event_map[item.event_id].timestamp
                            for item in candidate.evidence
                            if event_map[item.event_id].timestamp
                        ),
                        default=None,
                    ),
                    created_by_run_id=run.id,
                )
                session.add(claim)
                session.flush()
                for item in candidate.evidence:
                    event = event_map[item.event_id]
                    evidence = Evidence(
                        source_event_id=event.event_id,
                        person_id=person_id,
                        excerpt=item.excerpt,
                        evidence_type=(
                            "explicit_self_statement"
                            if re.search(
                                r"我.{0,20}(喜欢|不喜欢|习惯|倾向|认为|决定)", item.excerpt
                            )
                            else "direct_behavior"
                        ),
                        reliability=0.75,
                        observed_at=event.timestamp,
                    )
                    session.add(evidence)
                    session.flush()
                    session.add(
                        ClaimEvidence(
                            claim_id=claim.id,
                            evidence_id=evidence.id,
                            relation=item.relation,
                        )
                    )
                result.claims_created += 1
            for candidate in extracted.memories:
                if not all(
                    event_id in event_map and event_map[event_id].speaker_person_id == person_id
                    for event_id in candidate.event_ids
                ):
                    result.memories_rejected += 1
                    continue
                memory = Memory(
                    person_id=person_id,
                    memory_type=candidate.memory_type,
                    statement=candidate.statement,
                    confidence=0.0,
                    created_by_run_id=run.id,
                )
                session.add(memory)
                session.flush()
                for event_id in set(candidate.event_ids):
                    session.add(MemoryEvidence(memory_id=memory.id, event_id=event_id))
                result.memories_created += 1
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            session.commit()
            result.runs_created += 1
            if on_progress:
                on_progress(processed)
        except Exception as exc:
            session.rollback()
            run.status = "failed"
            run.error = type(exc).__name__
            run.completed_at = datetime.now(UTC)
            session.add(run)
            session.commit()
            raise
    return result
