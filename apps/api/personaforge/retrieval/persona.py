"""Context-aware trait selection without requiring embeddings."""

from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from personaforge.db.models import Trait


class EmbeddingRetriever(Protocol):
    def search(self, text: str, person_id: str, limit: int) -> list[tuple[str, float]]: ...


def retrieve_traits(
    session: Session,
    person_id: str,
    *,
    dimension: str | None = None,
    context: dict | None = None,
    min_confidence: float = 0.6,
    at: datetime | None = None,
    limit: int = 8,
) -> list[Trait]:
    statement = select(Trait).where(
        Trait.person_id == person_id,
        Trait.status == "active",
        Trait.confidence >= min_confidence,
    )
    if dimension is not None:
        statement = statement.where(Trait.dimension == dimension)
    candidates = list(session.scalars(statement))

    def score(trait: Trait) -> float:
        value = trait.confidence
        if context:
            for key, expected in context.items():
                actual = trait.context.get(key)
                if actual == expected or isinstance(actual, list) and expected in actual:
                    value += 0.1
        if at and trait.last_observed_at and trait.last_observed_at <= at:
            value += 0.05
        return value

    return sorted(candidates, key=score, reverse=True)[:limit]
