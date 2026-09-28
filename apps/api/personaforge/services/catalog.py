from sqlalchemy.orm import Session

from personaforge.db.models import Dataset, Person
from personaforge.db.repository import Repository


class CatalogService:
    def __init__(self, session: Session) -> None:
        self.repository = Repository(session)

    def create_dataset(self, name: str) -> Dataset:
        if not name.strip():
            raise ValueError("Dataset name is required")
        return self.repository.create_dataset(name.strip())

    def create_person(self, dataset_id: str, display_name: str) -> Person:
        if self.repository.get_dataset(dataset_id) is None:
            raise ValueError("Dataset not found")
        return self.repository.create_person(dataset_id, display_name)
