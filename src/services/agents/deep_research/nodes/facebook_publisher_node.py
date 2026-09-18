import logging
from typing import Any

from langgraph.runtime import Runtime
from src.services.agents.deep_research.context import DeepResearchContext
from src.services.agents.deep_research.state import DeepResearchState

logger = logging.getLogger(__name__)


async def facebook_publisher_node(
    state: DeepResearchState,
    runtime: Runtime[DeepResearchContext],
) -> dict[str, Any]:
    """Publish the formatted post to Facebook Page via Meta Graph API."""
    context = runtime.context
    fb_service = context.facebook_service
    settings = context.settings

    post_content = state.get("facebook_post", "")
    target_papers = state.get("target_papers", [])
    logs = list(state.get("logs", []))

    if not post_content:
        err = "No Facebook post content available to publish."
        logs.append(f"Warning: {err}")
        return {"published_to_facebook": False, "logs": logs}

    # Determine whether to auto-publish
    auto_publish = state.get("auto_publish", settings.facebook.auto_publish)
    primary_paper = target_papers[0] if target_papers else {}
    paper_url = primary_paper.get(
        "abs_url", f"https://arxiv.org/abs/{primary_paper.get('arxiv_id', '')}"
    )

    if not auto_publish:
        msg = "Auto-publish is disabled. Facebook post drafted and preserved for manual review."
        logger.info(msg)
        logs.append(msg)
        return {
            "published_to_facebook": False,
            "facebook_post_id": None,
            "logs": logs,
        }

    logs.append("Publishing post to Facebook Page...")
    try:
        response = await fb_service.publish_paper_post(
            post_content=post_content,
            paper_url=paper_url,
        )

        if response.success:
            pub_type = "SIMULATED" if response.is_simulated else "LIVE"
            msg = f"✓ Successfully published to Facebook ({pub_type})! Post ID: {response.post_id}"
            logger.info(msg)
            logs.append(msg)
            return {
                "published_to_facebook": True,
                "facebook_post_id": response.post_id,
                "facebook_post_url": response.url,
                "logs": logs,
            }
        else:
            err_msg = f"Failed to publish to Facebook: {response.message}"
            logger.error(err_msg)
            logs.append(err_msg)
            return {
                "published_to_facebook": False,
                "facebook_post_id": None,
                "publish_error": err_msg,
                "logs": logs,
            }

    except Exception as e:
        err_msg = f"Facebook publication error: {e!s}"
        logger.error(err_msg)
        logs.append(err_msg)
        return {
            "published_to_facebook": False,
            "facebook_post_id": None,
            "publish_error": err_msg,
            "logs": logs,
        }
