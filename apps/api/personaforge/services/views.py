"""Read models for persona, claims, timelines, and evidence context."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from personaforge.analysis.statistics import analyze_person
from personaforge.db.models import Claim, ClaimEvidence, Event, Evidence, Person, Trait


def list_people(session: Session, dataset_id: str | None = None) -> list[Person]:
    statement = select(Person).order_by(Person.display_name)
    if dataset_id:
        statement = statement.where(Person.dataset_id == dataset_id)
    return list(session.scalars(statement))


def persona_view(session: Session, person_id: str) -> dict:
    person = session.get(Person, person_id)
    if person is None:
        raise ValueError("Person not found")
    traits = list(session.scalars(select(Trait).where(Trait.person_id == person_id)))
    events = session.scalars(
        select(Event)
        .where(Event.dataset_id == person.dataset_id)
        .order_by(Event.conversation_id, Event.timestamp, Event.source_locator)
    )
    return {
        "person": {
            "id": person.id,
            "display_name": person.display_name,
            "dataset_id": person.dataset_id,
        },
        "traits": [
            {
                "id": trait.id,
                "dimension": trait.dimension,
                "key": trait.key,
                "statement": trait.statement,
                "context": trait.context,
                "confidence": trait.confidence,
                "support_count": trait.support_count,
                "counter_count": trait.counter_count,
                "first_seen": trait.valid_from,
                "last_seen": trait.last_observed_at,
                "status": trait.status,
            }
            for trait in traits
        ],
        "statistics": analyze_person(events, person_id).to_dict(),
    }


def claim_view(session: Session, claim_id: str) -> dict:
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise ValueError("Claim not found")
    rows = session.execute(
        select(ClaimEvidence, Evidence, Event)
        .join(Evidence, ClaimEvidence.evidence_id == Evidence.id)
        .join(Event, Evidence.source_event_id == Event.event_id)
        .where(ClaimEvidence.claim_id == claim_id)
    )
    evidence = []
    for link, item, event in rows:
        conversation = list(
            session.scalars(
                select(Event)
                .where(Event.conversation_id == event.conversation_id)
                .order_by(Event.timestamp, Event.source_locator)
            )
        )
        index = next(
            i for i, candidate in enumerate(conversation) if candidate.event_id == event.event_id
        )
        evidence.append(
            {
                "id": item.id,
                "relation": link.relation,
                "excerpt": item.excerpt,
                "event_id": event.event_id,
                "timestamp": event.timestamp,
                "source_file": event.source_file,
                "source_locator": event.source_locator,
                "context": [
                    {
                        "event_id": candidate.event_id,
                        "speaker": candidate.speaker_raw_name,
                        "text": candidate.text,
                        "timestamp": candidate.timestamp,
                        "is_evidence": candidate.event_id == event.event_id,
                    }
                    for candidate in conversation[max(0, index - 5) : index + 6]
                ],
            }
        )
    return {
        "id": claim.id,
        "person_id": claim.person_id,
        "dimension": claim.dimension,
        "name": claim.name,
        "statement": claim.statement,
        "context": claim.context,
        "confidence": claim.confidence,
        "status": claim.status,
        "first_seen": claim.first_seen,
        "last_seen": claim.last_seen,
        "superseded_by_id": claim.superseded_by_id,
        "evidence": evidence,
    }


def timeline_view(session: Session, person_id: str, limit: int = 100) -> list[dict]:
    events = session.scalars(
        select(Event)
        .where(Event.speaker_person_id == person_id)
        .order_by(Event.timestamp.desc())
        .limit(min(limit, 500))
    )
    return [
        {
            "event_id": event.event_id,
            "conversation_id": event.conversation_id,
            "timestamp": event.timestamp,
            "text": event.text,
            "source_file": event.source_file,
            "source_locator": event.source_locator,
            "event_type": event.event_type,
        }
        for event in events
    ]
