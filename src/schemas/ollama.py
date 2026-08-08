"""Pydantic models for Ollama structured outputs."""

from typing import List, Optional

from pydantic import BaseModel, Field


class RAGResponse(BaseModel):
    """Structured response model for RAG queries."""

    answer: str = Field(
        description="Comprehensive answer based on the provided paper excerpts"
    )
    sources: list[str] = Field(
        default_factory=list,
        description="List of PDF URLs from papers used in the answer",
    )
    confidence: str | None = Field(
        default=None,
        description="Confidence level: high, medium, or low based on excerpt relevance",
    )
    citations: list[str] | None = Field(
        default=None,
        description="Specific arXiv IDs or paper titles referenced in the answer",
    )
