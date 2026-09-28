"""Canonical event and API data contracts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "message",
    "meeting_utterance",
    "reaction",
    "attachment_note",
    "decision",
    "action_item",
    "correction",
]


class SourceLocator(BaseModel):
    type: str
    file: str
    locator: str


class CanonicalEvent(BaseModel):
    event_id: str
    dataset_id: str
    conversation_id: str | None = None
    source: SourceLocator
    speaker_person_id: str | None = None
    speaker_raw_name: str
    timestamp: datetime | None = None
    event_type: EventType = "message"
    text: str | None = None
    reply_to_event_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    created_at: datetime


class PersonCreate(BaseModel):
    dataset_id: str
    display_name: str = Field(min_length=1, max_length=200)


class PersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dataset_id: str
    display_name: str


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    person_id: str
    dimension: str
    name: str
    statement: str
    context: dict[str, Any]
    confidence: float
    status: str


class TraitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    person_id: str
    dimension: str
    key: str
    statement: str
    context: dict[str, Any]
    confidence: float
    support_count: int
    counter_count: int
    status: str
