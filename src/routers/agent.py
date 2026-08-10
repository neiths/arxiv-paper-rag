import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from src.dependencies import FacebookDep, SessionDep, SettingsDep
from src.schemas.agent import FacebookAgentRequest, FacebookAgentResponse
from src.services.agent.facebook_publisher import FacebookPublisherAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["LangGraph Agent"])


@router.post(
    "/publish-facebook",
    response_model=FacebookAgentResponse,
    status_code=status.HTTP_200_OK,
    summary="Run LangGraph Agent to summarize paper and post to Facebook Page",
)
async def publish_paper_to_facebook(
    request: FacebookAgentRequest,
    session: SessionDep,
    settings: SettingsDep,
    facebook_client: FacebookDep,
) -> FacebookAgentResponse:
    """
    Executes the LangGraph Facebook Publisher agent.

    Workflow steps:
    1. **Fetch Paper**: Retrieves paper by arXiv ID, UUID, or gets the newest paper in PostgreSQL DB.
    2. **Summarize Paper**: Uses LLM (Ollama) to extract key features, methodology, and applications into an engaging post summary.
    3. **Format Post**: Prepares markdown text and appends paper link and hashtags for Facebook.
    4. **Publish**: Posts directly to Facebook Page via Graph API (or performs a dry run if requested/unconfigured).
    """
    try:
        agent = FacebookPublisherAgent(
            session=session,
            settings=settings,
            facebook_client=facebook_client,
        )
        final_state = await agent.run(
            arxiv_id=request.arxiv_id,
            paper_id=request.paper_id,
            dry_run=request.dry_run,
            model_name=request.model,
        )

        paper_data = final_state.get("paper_data", {})
        paper_title = paper_data.get("title") if paper_data else None

        return FacebookAgentResponse(
            status=final_state.get("status", "unknown"),
            paper_id=final_state.get("paper_id"),
            arxiv_id=final_state.get("arxiv_id"),
            used_full_text=final_state.get("used_full_text", False),
            paper_title=paper_title,
            facebook_post=final_state.get("facebook_post"),
            facebook_post_id=final_state.get("facebook_post_id"),
            error=final_state.get("error"),
            paper_data=paper_data,
        )
    except Exception as e:
        logger.error(f"Error running Facebook Publisher Agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {e}",
        ) from e


@router.get(
    "/facebook-status",
    summary="Check Facebook Page Integration Status",
)
async def check_facebook_status(
    facebook_client: FacebookDep,
) -> dict[str, Any]:
    """Check if Facebook integration is configured and enabled."""
    return await facebook_client.health_check()
