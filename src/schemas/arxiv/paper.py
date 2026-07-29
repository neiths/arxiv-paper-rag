from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field


class ArxivPaper(BaseModel):
    """Schema for arXiv API response data."""

    arxiv_id: str = Field(..., description="arXiv paper ID")
    title: str = Field(..., description="Paper title")
    authors: List[str] = Field(..., description="List of author names")
    abstract: str = Field(..., description="Paper abstract")
    categories: List[str] = Field(..., description="Paper categories")
    published_date: str = Field(..., description="Date published on arXiv (ISO format)")
    pdf_url: str = Field(..., description="URL to PDF")


class PaperBase(BaseModel):
    arxiv_id: str = Field(..., description="arXiv identifier of the paper")
    title: str = Field(..., description="Title of the paper")
    authors: List[str] = Field(..., description="List of authors of the paper")
    abstract: str = Field(..., description="Abstract of the paper")
    categories: List[str] = Field(..., description="List of categories of the paper")
    published_date: datetime = Field(..., description="Publication date of the paper")
    pdf_url: str = Field(..., description="URL to the PDF of the paper")


class PaperCreate(PaperBase):
    pass


class PaperResponse(PaperBase):
    id: UUID = Field(..., description="Unique identifier of the paper in the database")
    created_at: datetime = Field(..., description="Timestamp when the paper was added to the database")
    updated_at: datetime = Field(..., description="Timestamp when the paper was last updated in the database")

    class Config:
        from_attributes = True


class PaperSearchResponse(BaseModel):
    papers: List[PaperResponse] = Field(..., description="List of papers matching the search criteria")
    total: int = Field(..., description="Total number of papers matching the search criteria")
