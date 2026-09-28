"""Human corrections preserve history and change the derived persona."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from personaforge.db.models import (
    Claim,
    ClaimEvidence,
    Correction,
    Event,
    Evidence,
    Person,
    SimulationTurn,
    Trait,
)
from personaforge.distillation.merge import rebuild_persona

FEEDBACK_TYPES = {"like", "unlike", "wrong_fact", "outdated", "wrong_context"}
TARGET_TYPES = {"claim", "trait", "simulation_turn", "event"}


def correct(
    session: Session,
    person_id: str,
    target_type: str,
    target_id: str,
    feedback_type: str,
    note: str | None = None,
) -> Correction:
    if feedback_type not in FEEDBACK_TYPES or target_type not in TARGET_TYPES:
        raise ValueError("Unsupported correction target or feedback type")
    person = session.get(Person, person_id)
    if person is None:
        raise ValueError("Person not found")
    model = {"claim": Claim, "trait": Trait, "simulation_turn": SimulationTurn, "event": Event}[
        target_type
    ]
    target = session.get(model, target_id)
    if target is None:
        raise ValueError("Correction target not found")
    if target_type == "event":
        if target.speaker_person_id != person_id:
            raise ValueError("Event does not belong to person")
    elif target.person_id != person_id:
        raise ValueError("Correction target does not belong to person")
    correction = Correction(
        person_id=person_id,
        target_type=target_type,
        target_id=target_id,
        feedback_type=feedback_type,
        note=note,
    )
    session.add(correction)
    session.flush()
    if target_type == "simulation_turn":
        target.feedback = feedback_type

    if feedback_type in {"wrong_fact", "outdated", "wrong_context"}:
        correction_event = Event(
            event_id=uuid4().hex,
            dataset_id=person.dataset_id,
            speaker_person_id=None,
            speaker_raw_name="Reviewer",
            timestamp=datetime.now(UTC),
            event_type="correction",
            text=note or feedback_type,
            source_type="manual_correction",
            source_file="manual",
            source_locator=correction.id,
        )
        session.add(correction_event)
        session.flush()
        evidence = Evidence(
            source_event_id=correction_event.event_id,
            person_id=person_id,
            excerpt=note or feedback_type,
            evidence_type="manual_correction",
            reliability=1.0,
            observed_at=correction_event.timestamp,
            extra={
                "correction_id": correction.id,
                "target_type": target_type,
                "target_id": target_id,
            },
        )
        session.add(evidence)
        session.flush()
        claim: Claim | None = None
        if target_type == "claim":
            claim = target
        elif target_type == "trait":
            claim = session.scalar(
                select(Claim).where(
                    Claim.person_id == person_id,
                    Claim.dimension == target.dimension,
                    Claim.key == target.key,
                    Claim.status != "superseded",
                )
            )
        if claim is not None:
            if feedback_type == "outdated":
                claim.status = "superseded"
                if note and note.strip():
                    replacement = Claim(
                        person_id=person_id,
                        dimension=claim.dimension,
                        key=claim.key,
                        name=claim.name,
                        statement=note.strip(),
                        context=claim.context,
                        first_seen=correction_event.timestamp,
                        last_seen=correction_event.timestamp,
                    )
                    session.add(replacement)
                    session.flush()
                    claim.superseded_by_id = replacement.id
                    session.add(
                        ClaimEvidence(
                            claim_id=replacement.id,
                            evidence_id=evidence.id,
                            relation="support",
                        )
                    )
            else:
                session.add(
                    ClaimEvidence(claim_id=claim.id, evidence_id=evidence.id, relation="correction")
                )
        if claim is not None:
            session.flush()
            rebuild_persona(session, person_id)
        else:
            session.commit()
    else:
        session.commit()
    return correction
