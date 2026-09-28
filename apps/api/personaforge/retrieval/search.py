"""FTS5 lexical retrieval with source attribution and filters."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class EventSearchResult:
    event_id: str
    dataset_id: str
    conversation_id: str | None
    person_id: str | None
    timestamp: str | None
    event_type: str
    text: str | None
    source_file: str
    source_locator: str
    lexical_score: float


def search_events(
    session: Session,
    query: str,
    *,
    person_id: str | None = None,
    dataset_id: str | None = None,
    conversation_id: str | None = None,
    event_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 20,
) -> list[EventSearchResult]:
    if not query.strip():
        return []
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    clauses: list[str] = []
    params: dict = {"limit": limit}
    for column, value in (
        ("speaker_person_id", person_id),
        ("dataset_id", dataset_id),
        ("conversation_id", conversation_id),
        ("event_type", event_type),
    ):
        if value is not None:
            clauses.append(f"e.{column} = :{column}")
            params[column] = value
    if start is not None:
        clauses.append("e.timestamp >= :start")
        params["start"] = start.isoformat(sep=" ")
    if end is not None:
        clauses.append("e.timestamp <= :end")
        params["end"] = end.isoformat(sep=" ")
    filters = " AND ".join(clauses)
    if filters:
        filters = " AND " + filters
    if len(query.strip()) >= 3:
        params["match"] = '"' + query.strip().replace('"', '""') + '"'
        sql = f"""
            SELECT e.event_id, e.dataset_id, e.conversation_id, e.speaker_person_id,
                   e.timestamp, e.event_type, e.text, e.source_file, e.source_locator,
                   bm25(events_fts) AS rank
            FROM events_fts JOIN events e ON e.event_id = events_fts.event_id
            WHERE events_fts MATCH :match {filters}
            ORDER BY rank LIMIT :limit
        """
    else:
        params["pattern"] = f"%{query.strip()}%"
        sql = f"""
            SELECT e.event_id, e.dataset_id, e.conversation_id, e.speaker_person_id,
                   e.timestamp, e.event_type, e.text, e.source_file, e.source_locator,
                   0.0 AS rank
            FROM events e WHERE e.text LIKE :pattern {filters}
            ORDER BY e.timestamp DESC LIMIT :limit
        """
    rows = session.execute(text(sql), params).mappings()
    return [
        EventSearchResult(
            event_id=row["event_id"],
            dataset_id=row["dataset_id"],
            conversation_id=row["conversation_id"],
            person_id=row["speaker_person_id"],
            timestamp=row["timestamp"],
            event_type=row["event_type"],
            text=row["text"],
            source_file=row["source_file"],
            source_locator=row["source_locator"],
            lexical_score=max(0.0, -float(row["rank"])),
        )
        for row in rows
    ]
