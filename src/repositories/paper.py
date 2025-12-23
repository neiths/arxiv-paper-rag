from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.paper import Paper
from src.schemas.paper import PaperCreate


class PaperRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, paper: PaperCreate) -> Paper:
        """
        Create a new paper record in the database.

        :param paper: The PaperCreate schema object containing paper details.
        :return: The created Paper object.
        """
        db_paper = Paper(**paper.model_dump())
        self.session.add(db_paper)
        self.session.commit()
        self.session.refresh(db_paper)
        return db_paper

    def get_by_arxiv_id(self, arxiv_id: str) -> Optional[Paper]:
        """
        Get a paper by its arXiv ID.

        :param arxiv_id: The arXiv ID of the paper.
        :return: The Paper object if found, else None.
        """
        return self.session.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()

    def get_by_id(self, paper_id: UUID) -> Optional[Paper]:
        """
        Get a paper by its database ID.

        :param paper_id: The UUID of the paper.
        :return: The Paper object if found, else None.
        """
        return self.session.query(Paper).filter(Paper.id == paper_id).first()

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Paper]:
        """
        Get all papers with pagination.

        :param limit: The maximum number of papers to return.
        :param offset: The number of papers to skip.
        :return: A list of Paper objects.
        """
        return self.session.query(Paper).order_by(Paper.published_date.desc()).limit(limit).offset(offset).all()

    def update(self, paper: Paper) -> Paper:
        """
        Update an existing paper record in the database.

        :param paper: The Paper object with updated details.
        :return: The updated Paper object.
        """
        self.session.add(paper)
        self.session.commit()
        self.session.refresh(paper)
        return paper

    def upsert(self, paper_create: PaperCreate) -> Paper:
        """
        Insert or update a paper record in the database.

        :param paper_create: The PaperCreate schema object containing paper details.
        :return: The created or updated Paper object.
        """
        existing_paper = self.get_by_arxiv_id(paper_create.arxiv_id)
        if existing_paper:
            for key, value in paper_create.model_dump().items():
                setattr(existing_paper, key, value)
            return self.update(existing_paper)
        else:
            return self.create(paper_create)
