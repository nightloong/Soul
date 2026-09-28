"""Persistent background jobs for long model distillation requests."""

from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from personaforge.api.dependencies import initialized_engine
from personaforge.db.models import DistillationJob, Event
from personaforge.db.session import database_url
from personaforge.distillation.merge import rebuild_persona
from personaforge.distillation.service import distill_person
from personaforge.providers.chat import ChatModel


def create_job(session: Session, dataset_id: str, person_id: str) -> DistillationJob:
    total = session.scalar(
        select(func.count()).select_from(Event).where(Event.dataset_id == dataset_id)
    )
    job = DistillationJob(
        dataset_id=dataset_id,
        person_id=person_id,
        status="queued",
        processed_events=0,
        total_events=total or 0,
        result={},
    )
    session.add(job)
    session.commit()
    return job


def job_view(job: DistillationJob) -> dict:
    return {
        "id": job.id,
        "person_id": job.person_id,
        "status": job.status,
        "processed_events": job.processed_events,
        "total_events": job.total_events,
        "result": job.result,
        "error": job.error,
    }


def recover_interrupted_jobs(session: Session) -> None:
    interrupted = session.scalars(
        select(DistillationJob).where(DistillationJob.status.in_(["queued", "running"]))
    )
    for job in interrupted:
        job.status = "failed"
        job.error = "InterruptedJob"
        job.completed_at = datetime.now(UTC)
    session.commit()


async def run_job(job_id: str, model: ChatModel) -> None:
    engine = initialized_engine(database_url())
    with Session(engine) as session:
        job = session.get(DistillationJob, job_id)
        if job is None or job.status != "queued":
            return
        job.status = "running"
        session.commit()

        def progress(processed: int) -> None:
            job.processed_events = processed
            session.commit()

        try:
            result = await distill_person(
                session,
                job.dataset_id,
                job.person_id,
                model,
                on_progress=progress,
            )
            rebuild_persona(session, job.person_id)
            job.result = asdict(result)
            job.status = "completed"
            job.processed_events = job.total_events
            job.completed_at = datetime.now(UTC)
            session.commit()
        except Exception as exc:
            session.rollback()
            job.status = "failed"
            job.error = type(exc).__name__
            job.completed_at = datetime.now(UTC)
            session.commit()
