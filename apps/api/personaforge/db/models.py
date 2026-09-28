"""Persistent domain records. All IDs are stable external strings."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from personaforge.db.base import Base


def new_id() -> str:
    return uuid4().hex


def utc_now() -> datetime:
    return datetime.now(UTC)


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SourceFile(Base):
    __tablename__ = "source_files"
    __table_args__ = (UniqueConstraint("dataset_id", "sha256"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64))
    source_type: Mapped[str] = mapped_column(String(50))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Person(Base):
    __tablename__ = "people"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    display_name: Mapped[str] = mapped_column(String(200))


class PersonAlias(Base):
    __tablename__ = "person_aliases"
    __table_args__ = (UniqueConstraint("dataset_id", "alias"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(String(200))


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(String(300))
    channel: Mapped[str | None] = mapped_column(String(100))


class Event(Base):
    __tablename__ = "events"
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    source_file_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_files.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    speaker_person_id: Mapped[str | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL")
    )
    speaker_raw_name: Mapped[str] = mapped_column(String(200))
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_type: Mapped[str] = mapped_column(String(40))
    text: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(100))
    source_file: Mapped[str] = mapped_column(String(300))
    source_locator: Mapped[str] = mapped_column(String(300))
    reply_to_event_id: Mapped[str | None] = mapped_column(ForeignKey("events.event_id"))
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    extra: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source_event_id: Mapped[str] = mapped_column(
        ForeignKey("events.event_id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    excerpt: Mapped[str] = mapped_column(Text)
    evidence_type: Mapped[str] = mapped_column(String(50))
    reliability: Mapped[float] = mapped_column(Float)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extra: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class DistillationRun(Base):
    __tablename__ = "distillation_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    model: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    input_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class DistillationJob(Base):
    __tablename__ = "distillation_jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    processed_events: Mapped[int] = mapped_column(Integer, default=0)
    total_events: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    dimension: Mapped[str] = mapped_column(String(60))
    key: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="weak")
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("distillation_runs.id", ondelete="SET NULL")
    )
    superseded_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("claims.id", ondelete="SET NULL", name="fk_claims_superseded_by")
    )


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (UniqueConstraint("claim_id", "evidence_id", "relation"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"))
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"))
    relation: Mapped[str] = mapped_column(String(20))
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class Trait(Base):
    __tablename__ = "traits"
    __table_args__ = (
        UniqueConstraint("person_id", "dimension", "key", name="uq_traits_person_dimension_key"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    dimension: Mapped[str] = mapped_column(String(60))
    key: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float)
    support_count: Mapped[int] = mapped_column(Integer, default=0)
    counter_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="active")


class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    memory_type: Mapped[str] = mapped_column(String(30))
    statement: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_by_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("distillation_runs.id", ondelete="SET NULL")
    )


class MemoryEvidence(Base):
    __tablename__ = "memory_evidence"
    __table_args__ = (UniqueConstraint("memory_id", "event_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.event_id", ondelete="CASCADE"))


class Correction(Base):
    __tablename__ = "corrections"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[str] = mapped_column(String(64))
    feedback_type: Mapped[str] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SimulationTurn(Base):
    __tablename__ = "simulation_turns"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    user_input: Mapped[str] = mapped_column(Text)
    selected_trait_ids: Mapped[list] = mapped_column(JSON, default=list)
    selected_event_ids: Mapped[list] = mapped_column(JSON, default=list)
    selected_memory_ids: Mapped[list] = mapped_column(JSON, default=list)
    model: Mapped[str] = mapped_column(String(200))
    response: Mapped[str] = mapped_column(Text)
    feedback: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
