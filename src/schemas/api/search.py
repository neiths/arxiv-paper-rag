from typing import List, Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Search request model."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query across title, abstract, and authors",
    )
    size: int = Field(
        default=10, ge=1, le=50, description="Number of results to return"
    )
    from_: int = Field(
        default=0, ge=0, alias="from", description="Offset for pagination"
    )
    categories: list[str] | None = Field(
        default=None, description="Filter by categories"
    )
    latest_papers: bool = Field(
        default=False,
        description="Sort by publication date (newest first) instead of relevance",
    )


class HybridSearchRequest(BaseModel):
    """Request model for hybrid search supporting all search modes."""

    query: str = Field(
        ..., description="Search query text", min_length=1, max_length=500
    )
    size: int = Field(10, description="Number of results to return", ge=1, le=100)
    from_: int = Field(0, description="Offset for pagination", ge=0, alias="from")
    categories: list[str] | None = Field(
        None, description="Filter by arXiv categories (e.g., ['cs.AI', 'cs.LG'])"
    )
    latest_papers: bool = Field(
        False, description="Sort by publication date instead of relevance"
    )
    use_hybrid: bool = Field(
        True,
        description="Enable hybrid search (BM25 + vector) with automatic embedding generation",
    )
    min_score: float = Field(
        0.0, description="Minimum score threshold for results", ge=0.0
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "query": "machine learning neural networks",
                "size": 10,
                "categories": ["cs.AI", "cs.LG"],
                "latest_papers": False,
                "use_hybrid": True,
            }
        }


class SearchHit(BaseModel):
    """Individual search result."""

    arxiv_id: str
    title: str
    authors: str | None
    abstract: str | None
    published_date: str | None
    pdf_url: str | None
    score: float
    highlights: dict | None = None

    # Chunk-specific fields (for unified search)
    chunk_text: str | None = Field(
        None, description="Text content of the matching chunk"
    )
    chunk_id: str | None = Field(None, description="Unique identifier of the chunk")
    section_name: str | None = Field(
        None, description="Section name where the chunk was found"
    )


class SearchResponse(BaseModel):
    """Search response model."""

    query: str
    total: int
    hits: list[SearchHit]
    size: int = Field(description="Number of results requested")
    from_: int = Field(alias="from", description="Offset used for pagination")
    search_mode: str | None = Field(
        None, description="Search mode used: bm25, vector, or hybrid"
    )
    error: str | None = None

    class Config:
        populate_by_name = True
