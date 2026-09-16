from typing import Any, Literal

from typing_extensions import TypedDict


class DeepResearchState(TypedDict, total=False):
    """State schema for the Deep Research & Facebook Publisher Agent."""

    # Input specifications
    input_query: str
    mode: Literal["direct_paper", "topic_research"]
    language: str  # "en" or "vi"
    post_style: Literal["technical_deep_dive", "executive_summary", "viral_breakdown"]
    model_name: str | None
    auto_publish: bool

    # Planning & Search
    sub_questions: list[str]
    search_queries: list[str]
    paper_ids: list[str]

    # Retrieved Paper Data
    target_papers: list[dict[str, Any]]
    paper_full_texts: dict[str, str]

    # Deep Research & Synthesis
    analysis_notes: dict[str, Any]
    synthesis_report: str

    # Social Output & Publishing
    facebook_post: str
    facebook_post_id: str | None
    facebook_post_url: str | None
    published_to_facebook: bool

    # Observability & Metadata
    logs: list[str]
    error: str | None
