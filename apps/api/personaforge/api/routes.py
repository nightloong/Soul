"""HTTP routes delegate persistence and analysis to services."""

import os
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from personaforge.analysis.meeting import analyze_meeting, derive_decision_pattern
from personaforge.api.dependencies import get_session
from personaforge.db.models import Claim, Conversation, Dataset, DistillationJob, Person
from personaforge.db.repository import Repository
from personaforge.distillation.jobs import create_job, job_view, run_job
from personaforge.distillation.merge import rebuild_persona
from personaforge.domain.schemas import DatasetCreate, DatasetRead, PersonCreate, PersonRead
from personaforge.ingestion.pipeline import apply_file, preview_file
from personaforge.providers.chat import OpenAICompatibleChatModel
from personaforge.retrieval.search import search_events
from personaforge.runtime.service import explain_turn, simulate
from personaforge.services.catalog import CatalogService
from personaforge.services.corrections import correct
from personaforge.services.views import claim_view, list_people, persona_view, timeline_view

router = APIRouter(prefix="/api")
SessionDep = Annotated[Session, Depends(get_session)]
UPLOAD_ROOT = Path("data/private/uploads").resolve()
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


class ApplyRequest(BaseModel):
    token: str
    dataset_id: str
    sha256: str
    speaker_map: dict[str, str] = Field(default_factory=dict)


class AliasRequest(BaseModel):
    alias: str = Field(min_length=1, max_length=200)


class SimulationRequest(BaseModel):
    message: str = Field(min_length=1)
    context: dict[str, str] = Field(default_factory=dict)


class CorrectionRequest(BaseModel):
    person_id: str
    target_type: str
    target_id: str
    feedback_type: str
    note: str | None = None


def staged_file(token: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise HTTPException(400, "Invalid upload token")
    directory = UPLOAD_ROOT / token
    files = [path for path in directory.iterdir() if path.is_file()] if directory.is_dir() else []
    if len(files) != 1 or files[0].resolve().parent != directory.resolve():
        raise HTTPException(404, "Upload not found")
    return files[0]


def configured_model() -> OpenAICompatibleChatModel:
    base_url = os.getenv("PERSONAFORGE_MODEL_BASE_URL", "")
    model_name = os.getenv("PERSONAFORGE_MODEL_NAME", "")
    api_key = os.getenv("PERSONAFORGE_MODEL_API_KEY", "")
    if not base_url or not model_name or not api_key:
        raise HTTPException(503, "Configure model endpoint, name, and API key in the environment")
    return OpenAICompatibleChatModel(base_url, api_key, model_name)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/datasets", response_model=list[DatasetRead])
def datasets(session: SessionDep):
    return Repository(session).list_datasets()


@router.post("/datasets", response_model=DatasetRead)
def create_dataset(body: DatasetCreate, session: SessionDep):
    dataset = CatalogService(session).create_dataset(body.name)
    session.commit()
    return dataset


@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: str, session: SessionDep):
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "Dataset not found")
    session.delete(dataset)
    session.commit()
    return {"deleted": dataset_id}


@router.get("/people", response_model=list[PersonRead])
def people(session: SessionDep, dataset_id: str | None = None):
    return list_people(session, dataset_id)


@router.post("/people", response_model=PersonRead)
def create_person(body: PersonCreate, session: SessionDep):
    try:
        person = CatalogService(session).create_person(body.dataset_id, body.display_name)
        Repository(session).add_alias(person, body.display_name)
        session.commit()
        return person
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/people/{person_id}/aliases")
def add_alias(person_id: str, body: AliasRequest, session: SessionDep):
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(404, "Person not found")
    alias = Repository(session).add_alias(person, body.alias)
    session.commit()
    return {"id": alias.id, "alias": alias.alias, "person_id": person_id}


@router.get("/people/{person_id}/persona")
def persona(person_id: str, session: SessionDep):
    try:
        return persona_view(session, person_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/people/{person_id}/claims")
def person_claims(person_id: str, session: SessionDep):
    return list(session.scalars(select(Claim).where(Claim.person_id == person_id)))


@router.get("/claims/{claim_id}")
def claim(claim_id: str, session: SessionDep):
    try:
        return claim_view(session, claim_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/timeline")
def timeline(person_id: str, session: SessionDep, limit: int = 100):
    return timeline_view(session, person_id, limit)


@router.get("/search")
def search(
    query: str,
    session: SessionDep,
    person_id: str | None = None,
    dataset_id: str | None = None,
    conversation_id: str | None = None,
    event_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 20,
):
    return [
        asdict(item)
        for item in search_events(
            session,
            query,
            person_id=person_id,
            dataset_id=dataset_id,
            conversation_id=conversation_id,
            event_type=event_type,
            start=start,
            end=end,
            limit=limit,
        )
    ]


@router.post("/import/preview")
async def import_preview(file: Annotated[UploadFile, File()]):
    filename = Path(file.filename or "").name
    if not filename or Path(filename).suffix.lower() not in {
        ".json",
        ".jsonl",
        ".csv",
        ".txt",
        ".md",
        ".markdown",
    }:
        raise HTTPException(400, "Unsupported file type")
    token = uuid4().hex
    directory = UPLOAD_ROOT / token
    directory.mkdir(parents=True, exist_ok=False)
    destination = directory / filename
    size = 0
    try:
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "File exceeds 100 MB")
                output.write(chunk)
        return {"token": token, "preview": asdict(preview_file(destination))}
    except Exception:
        destination.unlink(missing_ok=True)
        directory.rmdir()
        raise


@router.post("/import/apply")
def import_apply(body: ApplyRequest, session: SessionDep):
    path = staged_file(body.token)
    try:
        return asdict(apply_file(session, path, body.dataset_id, body.sha256, body.speaker_map))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/people/{person_id}/distill")
async def distill(person_id: str, session: SessionDep, background_tasks: BackgroundTasks):
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(404, "Person not found")
    model = configured_model()
    job = create_job(session, person.dataset_id, person_id)
    background_tasks.add_task(run_job, job.id, model)
    return job_view(job)


@router.get("/distillation/jobs/{job_id}")
def distillation_job(job_id: str, session: SessionDep):
    job = session.get(DistillationJob, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job_view(job)


@router.post("/distillation/jobs/{job_id}/retry")
def retry_distillation_job(job_id: str, session: SessionDep, background_tasks: BackgroundTasks):
    previous = session.get(DistillationJob, job_id)
    if previous is None:
        raise HTTPException(404, "Job not found")
    if previous.status != "failed":
        raise HTTPException(409, "Only failed jobs can be retried")
    model = configured_model()
    job = create_job(session, previous.dataset_id, previous.person_id)
    background_tasks.add_task(run_job, job.id, model)
    return job_view(job)


@router.post("/people/{person_id}/rebuild")
def rebuild(person_id: str, session: SessionDep):
    if session.get(Person, person_id) is None:
        raise HTTPException(404, "Person not found")
    return {"traits": [trait.id for trait in rebuild_persona(session, person_id)]}


@router.post("/simulation/{person_id}")
async def simulation(person_id: str, body: SimulationRequest, session: SessionDep):
    try:
        return asdict(
            await simulate(
                session, person_id, body.message, configured_model(), context_overrides=body.context
            )
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/simulation/turns/{turn_id}/explain")
def simulation_explain(turn_id: str, session: SessionDep):
    try:
        return explain_turn(session, turn_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/settings")
def settings():
    return {
        "model_configured": bool(
            os.getenv("PERSONAFORGE_MODEL_BASE_URL")
            and os.getenv("PERSONAFORGE_MODEL_NAME")
            and os.getenv("PERSONAFORGE_MODEL_API_KEY")
        ),
        "model_name": os.getenv("PERSONAFORGE_MODEL_NAME"),
        "data_location": "data/private/",
    }


@router.get("/meetings")
def meetings(session: SessionDep):
    conversations = session.scalars(select(Conversation).order_by(Conversation.title))
    return [
        {"id": item.id, "title": item.title, "dataset_id": item.dataset_id}
        for item in conversations
    ]


@router.get("/meetings/{conversation_id}")
def meeting(conversation_id: str, session: SessionDep):
    try:
        return analyze_meeting(session, conversation_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/people/{person_id}/meeting-patterns")
def meeting_patterns(person_id: str, session: SessionDep):
    if session.get(Person, person_id) is None:
        raise HTTPException(404, "Person not found")
    claim = derive_decision_pattern(session, person_id)
    return {"claim_id": claim.id if claim else None, "requires_multiple_meetings": claim is None}


@router.post("/corrections")
def create_correction(body: CorrectionRequest, session: SessionDep):
    try:
        correction = correct(
            session,
            body.person_id,
            body.target_type,
            body.target_id,
            body.feedback_type,
            body.note,
        )
        return {"id": correction.id, "feedback_type": correction.feedback_type}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
