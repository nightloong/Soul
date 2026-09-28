"""Local PersonaForge API application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session

from personaforge.api.dependencies import initialized_engine
from personaforge.api.routes import router
from personaforge.db.session import database_url
from personaforge.distillation.jobs import recover_interrupted_jobs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    engine = initialized_engine(database_url())
    with Session(engine) as session:
        recover_interrupted_jobs(session)
    yield


app = FastAPI(title="PersonaForge", lifespan=lifespan)
app.include_router(router)
