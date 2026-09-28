"""Small persistence operations, shared by services and API routes."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from personaforge.db.models import Dataset, Person, PersonAlias


class Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_dataset(self, name: str) -> Dataset:
        dataset = Dataset(name=name)
        self.session.add(dataset)
        self.session.flush()
        return dataset

    def list_datasets(self) -> list[Dataset]:
        return list(self.session.scalars(select(Dataset).order_by(Dataset.created_at)))

    def get_dataset(self, dataset_id: str) -> Dataset | None:
        return self.session.get(Dataset, dataset_id)

    def create_person(self, dataset_id: str, display_name: str) -> Person:
        person = Person(dataset_id=dataset_id, display_name=display_name)
        self.session.add(person)
        self.session.flush()
        return person

    def add_alias(self, person: Person, alias: str) -> PersonAlias:
        mapping = PersonAlias(dataset_id=person.dataset_id, person_id=person.id, alias=alias)
        self.session.add(mapping)
        self.session.flush()
        return mapping

    def resolve_alias(self, dataset_id: str, alias: str) -> Person | None:
        stmt = (
            select(Person)
            .join(PersonAlias)
            .where(PersonAlias.dataset_id == dataset_id, PersonAlias.alias == alias)
        )
        return self.session.scalar(stmt)
