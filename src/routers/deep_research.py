import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from src.dependencies import DeepResearchDep, FacebookDep
from src.services.facebook.models import FacebookPageInfo, FacebookPostResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deep-research", tags=["Deep Research & Social Publishing"])


class DeepResearchRequest(BaseModel):
    """Request payload for running deep research on an arXiv paper or topic."""

    query: str = Field(
        ...,
        min_length=3,
        description="arXiv URL (e.g. https://arxiv.org/abs/2403.05530), paper ID, or research topic.",
        examples=[
            "https://arxiv.org/abs/2403.05530",
            "Test-time compute scaling in reasoning models",
        ],
    )
    language: Literal["en", "vi"] = Field(
        default="en",
        description="Target language for social media post ('en' for English, 'vi' for Vietnamese).",
    )
    post_style: Literal[
        "technical_deep_dive", "executive_summary", "viral_breakdown"
    ] = Field(
        default="technical_deep_dive",
        description="Tone and formatting style of the social media post.",
    )
    auto_publish: bool | None = Field(
        default=None,
        description="Whether to immediately publish to Facebook Page via Meta Graph API. Defaults to system configuration.",
    )
    model_name: str | None = Field(
        default=None,
        description="Optional model override (e.g. 'llama3.2:latest', 'gemini-1.5-flash', 'gpt-4o').",
    )


class PublishFacebookRequest(BaseModel):
    """Request payload to manually publish a drafted post to Facebook."""

    message: str = Field(..., min_length=1, description="Post text")
    link: str | None = Field(None, description="arXiv link or attachment URL")


@router.post(
    "/run",
    summary="Execute Deep Research on arXiv and publish to Facebook",
    response_description="Deep research analysis report, generated Facebook post, and publishing status.",
)
async def run_deep_research(
    payload: DeepResearchRequest,
    service: DeepResearchDep,
) -> dict[str, Any]:
    """Execute iterative Deep Research on a specific paper or broad topic.

    This endpoint:
    1. Routes between direct paper analysis (by arXiv ID/URL) and multi-paper topic discovery.
    2. Downloads and parses full PDF contents using Docling.
    3. Conducts deep technical analysis (mechanisms, benchmarks, ablations, limitations).
    4. Formats an engaging, high-retention post tailored for Facebook (in English or Vietnamese).
    5. Publishes directly to Facebook Page if configured, or preserves the draft.
    """
    try:
        result = await service.run_research(
            query=payload.query,
            language=payload.language,
            post_style=payload.post_style,
            auto_publish=payload.auto_publish,
            model_name=payload.model_name,
        )
        return result
    except Exception as e:
        logger.error(f"Error in deep research endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deep research workflow failed: {e!s}",
        ) from e


@router.post(
    "/publish-facebook",
    response_model=FacebookPostResponse,
    summary="Manually publish or re-publish a post to Facebook Page",
)
async def publish_to_facebook(
    payload: PublishFacebookRequest,
    fb_service: FacebookDep,
) -> FacebookPostResponse:
    """Manually post formatted content to Facebook Page."""
    return await fb_service.publish_paper_post(
        post_content=payload.message,
        paper_url=payload.link,
    )


@router.get(
    "/facebook/status",
    response_model=FacebookPageInfo,
    summary="Check Facebook Page connection & token status",
)
async def get_facebook_status(
    fb_service: FacebookDep,
) -> FacebookPageInfo:
    """Verify Facebook credentials and connection status."""
    return await fb_service.verify_connection()
