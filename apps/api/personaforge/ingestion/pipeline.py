"""Two-step, streaming import with source-hash confirmation."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from personaforge.db.models import Conversation, Event, Person, PersonAlias, SourceFile
from personaforge.db.repository import Repository
from personaforge.ingestion.adapters import ImportIssue, adapter_for


@dataclass
class ImportPreview:
    filename: str
    sha256: str
    message_count: int = 0
    person_candidates: list[str] = field(default_factory=list)
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    unknown_timestamp: int = 0
    errors: list[ImportIssue] = field(default_factory=list)
    warnings: list[ImportIssue] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0


@dataclass
class ImportResult:
    imported: int
    already_imported: bool
    unmapped_speakers: list[str]
    source_file_id: str | None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def preview_file(path: Path, dataset_id: str = "preview") -> ImportPreview:
    if not path.is_file():
        raise FileNotFoundError(path)
    adapter = adapter_for(path)
    preview = ImportPreview(filename=path.name, sha256=file_sha256(path))
    speakers: set[str] = set()
    for record in adapter.preview(path, dataset_id):
        if record.issue is not None:
            if record.issue.severity == "warning":
                preview.warning_count += 1
                if len(preview.warnings) < 100:
                    preview.warnings.append(record.issue)
            else:
                preview.error_count += 1
                if len(preview.errors) < 100:
                    preview.errors.append(record.issue)
        if record.event is None:
            continue
        preview.message_count += 1
        speakers.add(record.event.speaker_raw_name)
        timestamp = record.event.timestamp
        if timestamp is None:
            preview.unknown_timestamp += 1
        else:
            if preview.first_timestamp is None or timestamp < preview.first_timestamp:
                preview.first_timestamp = timestamp
            if preview.last_timestamp is None or timestamp > preview.last_timestamp:
                preview.last_timestamp = timestamp
    preview.person_candidates = sorted(speakers)
    return preview


def apply_file(
    session: Session,
    path: Path,
    dataset_id: str,
    expected_sha256: str,
    speaker_map: dict[str, str] | None = None,
) -> ImportResult:
    preview = preview_file(path, dataset_id)
    if preview.sha256 != expected_sha256:
        raise ValueError("File changed after preview; preview it again")
    repository = Repository(session)
    if repository.get_dataset(dataset_id) is None:
        raise ValueError("Dataset not found")
    existing = session.scalar(
        select(SourceFile).where(
            SourceFile.dataset_id == dataset_id, SourceFile.sha256 == preview.sha256
        )
    )
    if existing is not None:
        return ImportResult(0, True, [], existing.id)

    explicit = speaker_map or {}
    for raw_name, person_id in explicit.items():
        person = session.get(Person, person_id)
        if person is None or person.dataset_id != dataset_id:
            raise ValueError(f"Invalid speaker mapping for {raw_name}: {person_id}")
    aliases = {
        alias: person_id
        for alias, person_id in session.execute(
            select(PersonAlias.alias, PersonAlias.person_id).where(
                PersonAlias.dataset_id == dataset_id
            )
        )
    }
    aliases.update(explicit)
    source = SourceFile(
        dataset_id=dataset_id,
        filename=path.name,
        sha256=preview.sha256,
        source_type=adapter_for(path).source_type,
    )
    session.add(source)
    session.flush()
    conversations: dict[str, str] = {}
    unknown: set[str] = set()
    count = 0
    for record in adapter_for(path).convert(path, dataset_id):
        event = record.event
        if event is None:
            continue
        raw_conversation = event.conversation_id or path.stem
        conversation_id = conversations.get(raw_conversation)
        if conversation_id is None:
            conversation_id = uuid5(
                NAMESPACE_URL, f"{dataset_id}:{preview.sha256}:conversation:{raw_conversation}"
            ).hex
            session.add(
                Conversation(
                    id=conversation_id,
                    dataset_id=dataset_id,
                    title=raw_conversation,
                    channel=event.context.get("channel"),
                )
            )
            session.flush()
            conversations[raw_conversation] = conversation_id
        person_id = aliases.get(event.speaker_raw_name)
        if person_id is None:
            unknown.add(event.speaker_raw_name)
        event_id = uuid5(NAMESPACE_URL, f"{dataset_id}:{preview.sha256}:{event.source.locator}").hex
        session.add(
            Event(
                event_id=event_id,
                dataset_id=dataset_id,
                source_file_id=source.id,
                conversation_id=conversation_id,
                speaker_person_id=person_id,
                speaker_raw_name=event.speaker_raw_name,
                timestamp=event.timestamp,
                event_type=event.event_type,
                text=event.text,
                source_type=event.source.type,
                source_file=event.source.file,
                source_locator=event.source.locator,
                context=event.context,
                extra=event.metadata,
            )
        )
        count += 1
        if count % 500 == 0:
            session.flush()
    if file_sha256(path) != preview.sha256:
        session.rollback()
        raise ValueError("File changed during import; preview it again")
    session.commit()
    return ImportResult(count, False, sorted(unknown), source.id)
