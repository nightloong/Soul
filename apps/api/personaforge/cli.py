"""Local administration and import commands."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from personaforge.db.repository import Repository
from personaforge.db.session import make_engine
from personaforge.distillation.merge import rebuild_persona
from personaforge.ingestion.adapters import GenericJSONLAdapter
from personaforge.ingestion.pipeline import apply_file, preview_file
from personaforge.services.catalog import CatalogService
from personaforge.services.views import claim_view, persona_view


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="personaforge")
    commands = root.add_subparsers(dest="command", required=True)
    dataset = commands.add_parser("dataset")
    dataset_commands = dataset.add_subparsers(dest="action", required=True)
    create_dataset = dataset_commands.add_parser("create")
    create_dataset.add_argument("name")
    person = commands.add_parser("person")
    person_commands = person.add_subparsers(dest="action", required=True)
    create_person = person_commands.add_parser("create")
    create_person.add_argument("name")
    create_person.add_argument("--dataset", required=True)
    add_alias = person_commands.add_parser("alias")
    add_alias.add_argument("alias")
    add_alias.add_argument("--person", required=True)
    imports = commands.add_parser("import")
    import_commands = imports.add_subparsers(dest="action", required=True)
    preview = import_commands.add_parser("preview")
    preview.add_argument("file", type=Path)
    apply = import_commands.add_parser("apply")
    apply.add_argument("file", type=Path)
    apply.add_argument("--dataset", required=True)
    apply.add_argument("--sha", help="SHA-256 returned by preview")
    apply.add_argument("--map", action="append", default=[], metavar="RAW=PERSON_ID")
    validate = commands.add_parser("validate-jsonl")
    validate.add_argument("file", type=Path)
    persona = commands.add_parser("persona")
    persona_commands = persona.add_subparsers(dest="action", required=True)
    rebuild = persona_commands.add_parser("rebuild")
    rebuild.add_argument("--person", required=True)
    export = persona_commands.add_parser("export")
    export.add_argument("--person", required=True)
    export.add_argument("--format", choices=["json"], required=True)
    return root


def print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, default=str, indent=2))


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "import" and args.action == "preview":
        print_json(asdict(preview_file(args.file)))
        return 0
    if args.command == "validate-jsonl":
        adapter = GenericJSONLAdapter()
        issues = [
            asdict(record.issue)
            for record in adapter.convert(args.file, "validate")
            if record.issue is not None
        ]
        print_json(
            {"valid": not any(issue["severity"] == "error" for issue in issues), "issues": issues}
        )
        return int(any(issue["severity"] == "error" for issue in issues))

    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine()
    try:
        with Session(engine) as session:
            repository = Repository(session)
            if args.command == "dataset":
                dataset = CatalogService(session).create_dataset(args.name)
                session.commit()
                print_json({"id": dataset.id, "name": dataset.name})
            elif args.command == "person" and args.action == "create":
                person = CatalogService(session).create_person(args.dataset, args.name)
                repository.add_alias(person, args.name)
                session.commit()
                print_json({"id": person.id, "display_name": person.display_name})
            elif args.command == "person" and args.action == "alias":
                from personaforge.db.models import Person

                person = session.get(Person, args.person)
                if person is None:
                    raise ValueError("Person not found")
                repository.add_alias(person, args.alias)
                session.commit()
                print_json({"person_id": person.id, "alias": args.alias})
            elif args.command == "import" and args.action == "apply":
                preview = preview_file(args.file, args.dataset)
                if args.sha is None:
                    print_json(asdict(preview))
                    if not sys.stdin.isatty():
                        raise ValueError(
                            "Pass --sha from a previous preview to apply non-interactively"
                        )
                    confirmed = input("Enter the SHA-256 above to apply: ").strip()
                else:
                    confirmed = args.sha
                mapping = dict(item.split("=", 1) for item in args.map)
                result = apply_file(session, args.file, args.dataset, confirmed, mapping)
                print_json(asdict(result))
            elif args.command == "persona" and args.action == "rebuild":
                print_json(
                    {"trait_ids": [item.id for item in rebuild_persona(session, args.person)]}
                )
            elif args.command == "persona" and args.action == "export":
                from sqlalchemy import select

                from personaforge.db.models import Claim

                claims = session.scalars(select(Claim).where(Claim.person_id == args.person))
                print_json(
                    {
                        "persona": persona_view(session, args.person),
                        "claims": [claim_view(session, item.id) for item in claims],
                    }
                )
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
