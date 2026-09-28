from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from personaforge.db.models import Event
from personaforge.db.repository import Repository
from personaforge.db.session import make_engine
from personaforge.ingestion.pipeline import apply_file, preview_file
from sqlalchemy import func, select
from sqlalchemy.orm import Session

SAMPLES = Path("examples/synthetic-chat")


@pytest.fixture
def session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = f"sqlite:///{(tmp_path / 'import.db').as_posix()}"
    monkeypatch.setenv("PERSONAFORGE_DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    with Session(engine) as current:
        yield current
    engine.dispose()


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("project.jsonl", 6),
        ("project.json", 2),
        ("project.csv", 2),
        ("project.txt", 2),
        ("project.md", 2),
    ],
)
def test_preview_adapters(filename: str, expected: int) -> None:
    preview = preview_file(SAMPLES / filename)
    assert preview.message_count == expected
    assert preview.person_candidates == ["Alice", "Bob"]
    assert preview.error_count == 0
    assert preview.first_timestamp is not None


def test_apply_is_idempotent_and_maps_only_known_speakers(session: Session) -> None:
    repository = Repository(session)
    dataset = repository.create_dataset("Synthetic")
    alice = repository.create_person(dataset.id, "Alice")
    repository.add_alias(alice, "Alice")
    session.commit()
    path = SAMPLES / "project.jsonl"
    preview = preview_file(path, dataset.id)
    first = apply_file(session, path, dataset.id, preview.sha256)
    second = apply_file(session, path, dataset.id, preview.sha256)
    assert (first.imported, second.imported, second.already_imported) == (6, 0, True)
    assert first.unmapped_speakers == ["Bob"]
    assert session.scalar(select(func.count()).select_from(Event)) == 6
    assert {row.speaker_person_id for row in session.scalars(select(Event))} == {alice.id, None}


def test_bad_lines_have_source_locator(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text('{"speaker":"A","text":"valid"}\nnot json\n', encoding="utf-8")
    preview = preview_file(path)
    assert preview.message_count == 1
    assert preview.error_count == 1
    assert preview.errors[0].locator == "line:2"
    assert preview.unknown_timestamp == 1


def test_apply_rejects_changed_file_and_bad_mapping(session: Session) -> None:
    repository = Repository(session)
    dataset = repository.create_dataset("Synthetic")
    session.commit()
    path = SAMPLES / "project.csv"
    with pytest.raises(ValueError, match="changed after preview"):
        apply_file(session, path, dataset.id, "wrong")
    with pytest.raises(ValueError, match="Invalid speaker mapping"):
        apply_file(session, path, dataset.id, preview_file(path).sha256, {"Alice": "missing"})
