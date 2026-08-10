from typing import Any

from pydantic import BaseModel, Field


class FacebookAgentRequest(BaseModel):
    arxiv_id: str | None = Field(
        None,
        description="arXiv ID of paper to summarize. If omitted, picks newest paper in DB.",
    )
    paper_id: str | None = Field(
        None,
        description="UUID of paper to summarize. If omitted, picks newest paper in DB.",
    )
    model: str | None = Field(
        None,
        description="Ollama model to use for summarization. Defaults to system setting.",
    )
    dry_run: bool = Field(
        True,
        description="If True, generates and formats the Facebook post without publishing to Facebook Page.",
    )


class FacebookAgentResponse(BaseModel):
    status: str = Field(
        ...,
        description="Execution status ('published', 'dry_run_success', 'failed').",
    )
    paper_id: str | None = None
    arxiv_id: str | None = None
    used_full_text: bool = False
    paper_title: str | None = None
    facebook_post: str | None = None
    facebook_post_id: str | None = None
    error: str | None = None
    paper_data: dict[str, Any] | None = None
