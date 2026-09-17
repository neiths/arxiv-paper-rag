import logging
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime
from src.services.agents.deep_research.context import DeepResearchContext
from src.services.agents.deep_research.prompts import FACEBOOK_POST_PROMPT
from src.services.agents.deep_research.state import DeepResearchState

logger = logging.getLogger(__name__)


async def social_writer_node(
    state: DeepResearchState,
    runtime: Runtime[DeepResearchContext],
) -> dict[str, Any]:
    """Format deep research synthesis into a high-engagement Facebook post."""
    context = runtime.context
    llm = context.llm

    synthesis_report = state.get("synthesis_report", "")
    target_papers = state.get("target_papers", [])
    language = state.get("language", "en")
    post_style = state.get("post_style", "technical_deep_dive")
    logs = list(state.get("logs", []))

    if not synthesis_report:
        err = "No synthesis report available to write Facebook post."
        logs.append(f"Error: {err}")
        return {"error": err, "logs": logs}

    primary_paper = target_papers[0] if target_papers else {}
    title = primary_paper.get("title", state.get("input_query", "AI Breakthrough"))
    paper_url = primary_paper.get(
        "abs_url", f"https://arxiv.org/abs/{primary_paper.get('arxiv_id', '')}"
    )
    authors = ", ".join(primary_paper.get("authors", [])[:4])

    logs.append(
        f"Generating Facebook post in language='{language}' (style='{post_style}')..."
    )

    try:
        prompt = FACEBOOK_POST_PROMPT.format(
            language="Vietnamese" if language == "vi" else "English",
            post_style=post_style,
            synthesis_report=synthesis_report[:8000],
            title=title,
            paper_url=paper_url,
            authors=authors or "ArXiv Researchers",
        )

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        post_content = str(response.content).strip()

        logs.append("Facebook post content crafted successfully.")
        return {
            "facebook_post": post_content,
            "logs": logs,
        }

    except Exception as e:
        err_msg = f"Social post generation failed: {e!s}"
        logger.error(err_msg)
        logs.append(f"Error: {err_msg}")
        return {"error": err_msg, "logs": logs}
