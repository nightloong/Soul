"""Strict data contract for semantic extraction."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Dimension = Literal[
    "linguistic_style",
    "interaction_pattern",
    "decision_pattern",
    "preference",
    "opinion",
    "knowledge",
    "relationship_pattern",
    "episodic_memory",
    "procedural_pattern",
]

MemoryType = Literal["core", "semantic", "episodic", "procedural"]
Relation = Literal["support", "counter", "correction"]


class ExtractedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    relation: Relation
    excerpt: str = Field(min_length=1)


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension: Dimension
    name: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    confidence_hint: float = Field(ge=0, le=1)
    evidence: list[ExtractedEvidence] = Field(min_length=1)


class ExtractedMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memory_type: MemoryType
    statement: str = Field(min_length=1)
    event_ids: list[str] = Field(min_length=1)


class ExtractionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_summary: str
    claims: list[ExtractedClaim]
    memories: list[ExtractedMemory]
