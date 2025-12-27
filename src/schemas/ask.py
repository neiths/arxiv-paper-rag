from typing import List

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., description="Question to ask about arXiv papers")


class PaperSource(BaseModel):
    arxiv_id: str = Field(..., description="arXiv identifier of the paper")
    title: str = Field(..., description="Title of the paper")
    authors: List[str] = Field(..., description="List of authors of the paper")
    abstract_preview: str = Field(..., description="Preview of the paper abstract")


class AskResponse(BaseModel):
    answer: str = Field(..., description="Answer to the asked question")
    sources: List[PaperSource] = Field(..., description="List of source papers referenced in the answer")
