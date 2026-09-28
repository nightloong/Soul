"""Deterministic claim normalization, confidence, and trait materialization."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from personaforge.db.models import Claim, ClaimEvidence, Event, Evidence, Trait


class ClaimNormalizer:
    @staticmethod
    def key(name: str) -> str:
        normalized = unicodedata.normalize("NFKC", name).casefold()
        return re.sub(r"_+", "_", re.sub(r"[^\w\u4e00-\u9fff]+", "_", normalized)).strip("_")

    @staticmethod
    def similar(left: Claim, right: Claim, threshold: float = 0.82) -> bool:
        if left.dimension != right.dimension:
            return False
        left_key = ClaimNormalizer.key(left.name)
        right_key = ClaimNormalizer.key(right.name)
        return (
            left_key == right_key or SequenceMatcher(None, left_key, right_key).ratio() >= threshold
        )


@dataclass(frozen=True)
class EvidenceSignal:
    relation: str
    evidence_type: str
    reliability: float
    conversation_id: str | None
    observed_at: datetime | None


def calculate_confidence(
    signals: list[EvidenceSignal],
    as_of: datetime,
    *,
    high_level_personality: bool = False,
) -> float:
    """Pure, conservative confidence calculation independent of model hints."""
    supports = [signal for signal in signals if signal.relation == "support"]
    counters = [signal for signal in signals if signal.relation in {"counter", "correction"}]
    if not supports:
        return 0.0
    explicit = any(
        signal.evidence_type in {"explicit_self_statement", "manual_correction"}
        for signal in supports
    )
    base = 0.85 if explicit else 0.65 if len(supports) >= 2 else 0.35
    conversations = {signal.conversation_id for signal in supports if signal.conversation_id}
    days = {signal.observed_at.date() for signal in supports if signal.observed_at}
    score = base
    if len(conversations) >= 2:
        score += 0.05
    if len(days) >= 2:
        score += 0.05
    if len(supports) >= 2 and len(conversations) <= 1:
        score -= 0.05
    score -= min(0.36, 0.12 * len(counters))
    if supports:
        score += max(
            -0.05, min(0.05, (sum(s.reliability for s in supports) / len(supports) - 0.75) * 0.2)
        )
    dated = [signal.observed_at for signal in supports if signal.observed_at]
    if dated:
        latest = max(dated)
        reference = as_of
        if latest.tzinfo is None:
            reference = as_of.replace(tzinfo=None)
        elif reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        if reference - latest > timedelta(days=730):
            score -= 0.1
    if high_level_personality:
        score = min(score, 0.6)
    return round(max(0.0, min(0.99, score)), 3)


def polarity(statement: str) -> int:
    lowered = statement.casefold()
    return (
        -1
        if re.search(r"不喜欢|不再|不喝|不做|停止|不倾向|no longer|don't|do not|stopped", lowered)
        else 1
    )


def _signals(session: Session, claim_id: str) -> list[EvidenceSignal]:
    rows = session.execute(
        select(ClaimEvidence, Evidence, Event)
        .join(Evidence, ClaimEvidence.evidence_id == Evidence.id)
        .join(Event, Evidence.source_event_id == Event.event_id)
        .where(ClaimEvidence.claim_id == claim_id)
    )
    return [
        EvidenceSignal(
            link.relation,
            evidence.evidence_type,
            evidence.reliability,
            event.conversation_id,
            evidence.observed_at,
        )
        for link, evidence, event in rows
    ]


def rebuild_persona(session: Session, person_id: str, as_of: datetime | None = None) -> list[Trait]:
    """Merge equivalent claims, retain history, and rebuild the derived trait view."""
    now = as_of or datetime.now(UTC)
    claims = list(
        session.scalars(
            select(Claim)
            .where(Claim.person_id == person_id, Claim.status != "superseded")
            .order_by(Claim.first_seen, Claim.id)
        )
    )
    survivors: list[Claim] = []
    for claim in claims:
        claim.key = ClaimNormalizer.key(claim.name)
        similar = next((item for item in survivors if ClaimNormalizer.similar(item, claim)), None)
        if similar is None:
            survivors.append(claim)
            continue
        if polarity(similar.statement) != polarity(claim.statement):
            older, newer = sorted(
                (similar, claim), key=lambda item: (item.last_seen or datetime.min, item.id)
            )
            older.status = "superseded"
            older.superseded_by_id = newer.id
            survivors.remove(older)
            if newer not in survivors:
                survivors.append(newer)
            continue
        existing_links = {
            (link.evidence_id, link.relation)
            for link in session.scalars(
                select(ClaimEvidence).where(ClaimEvidence.claim_id == similar.id)
            )
        }
        for link in session.scalars(
            select(ClaimEvidence).where(ClaimEvidence.claim_id == claim.id)
        ):
            if (link.evidence_id, link.relation) not in existing_links:
                session.add(
                    ClaimEvidence(
                        claim_id=similar.id,
                        evidence_id=link.evidence_id,
                        relation=link.relation,
                        weight=link.weight,
                    )
                )
        claim.status = "superseded"
        claim.superseded_by_id = similar.id
        if claim.last_seen and (not similar.last_seen or claim.last_seen > similar.last_seen):
            similar.last_seen = claim.last_seen
    session.flush()
    traits: list[Trait] = []
    active_keys: set[tuple[str, str]] = set()
    for claim in survivors:
        signals = _signals(session, claim.id)
        confidence = calculate_confidence(
            signals,
            now,
            high_level_personality=bool(
                re.search(r"内向|冷淡|外向|introvert|cold|personality", claim.statement.casefold())
            ),
        )
        claim.confidence = confidence
        support_count = sum(signal.relation == "support" for signal in signals)
        counter_count = sum(signal.relation in {"counter", "correction"} for signal in signals)
        claim.status = (
            "disputed"
            if counter_count >= support_count and counter_count
            else "active"
            if confidence >= 0.6
            else "weak"
        )
        key = (claim.dimension, claim.key)
        active_keys.add(key)
        trait = session.scalar(
            select(Trait).where(
                Trait.person_id == person_id,
                Trait.dimension == claim.dimension,
                Trait.key == claim.key,
            )
        )
        if trait is None:
            trait = Trait(
                person_id=person_id,
                dimension=claim.dimension,
                key=claim.key,
                statement=claim.statement,
                context=claim.context,
                confidence=confidence,
                support_count=support_count,
                counter_count=counter_count,
                valid_from=claim.first_seen,
                last_observed_at=claim.last_seen,
                status=claim.status,
            )
            session.add(trait)
        else:
            trait.statement = claim.statement
            trait.context = claim.context
            trait.confidence = confidence
            trait.support_count = support_count
            trait.counter_count = counter_count
            trait.valid_from = claim.first_seen
            trait.last_observed_at = claim.last_seen
            trait.status = claim.status
        traits.append(trait)
    for trait in session.scalars(select(Trait).where(Trait.person_id == person_id)):
        if (trait.dimension, trait.key) not in active_keys:
            trait.status = "superseded"
    session.commit()
    return traits
