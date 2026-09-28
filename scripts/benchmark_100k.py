"""Local synthetic import and FTS5 benchmark; no private data is read."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from alembic import command
from alembic.config import Config
from personaforge.db.repository import Repository
from personaforge.db.session import make_engine
from personaforge.ingestion.pipeline import apply_file, preview_file
from personaforge.retrieval.search import search_events
from sqlalchemy.orm import Session


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "synthetic-100k.jsonl"
        with source.open("w", encoding="utf-8") as output:
            for number in range(100_000):
                output.write(
                    json.dumps(
                        {
                            "conversation_id": "performance-demo",
                            "speaker": "Alice",
                            "text": f"Synthetic event {number}: small validation first",
                        }
                    )
                    + "\n"
                )
        os.environ["PERSONAFORGE_DATABASE_URL"] = f"sqlite:///{(root / 'benchmark.db').as_posix()}"
        command.upgrade(Config("alembic.ini"), "head")
        engine = make_engine()
        with Session(engine) as session:
            repository = Repository(session)
            dataset = repository.create_dataset("Synthetic performance")
            person = repository.create_person(dataset.id, "Alice")
            session.commit()
            start = perf_counter()
            preview = preview_file(source)
            preview_seconds = perf_counter() - start
            start = perf_counter()
            imported = apply_file(session, source, dataset.id, preview.sha256, {"Alice": person.id})
            import_seconds = perf_counter() - start
            start = perf_counter()
            hits = search_events(session, "small validation", person_id=person.id, limit=20)
            search_seconds = perf_counter() - start
            print(
                json.dumps(
                    {
                        "events": imported.imported,
                        "preview_seconds": round(preview_seconds, 3),
                        "import_seconds": round(import_seconds, 3),
                        "search_seconds": round(search_seconds, 3),
                        "search_hits": len(hits),
                    },
                    indent=2,
                )
            )
        engine.dispose()


if __name__ == "__main__":
    main()
