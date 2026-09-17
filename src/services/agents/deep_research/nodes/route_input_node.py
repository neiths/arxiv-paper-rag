import logging
import re
from typing import Any

from src.services.agents.deep_research.state import DeepResearchState

logger = logging.getLogger(__name__)

ARXIV_ID_PATTERN = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:)?([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?|[a-z\-]+(?:\.[a-z]{2})?/[0-9]{7}(?:v[0-9]+)?)",
    re.IGNORECASE,
)


def extract_arxiv_id(text: str) -> str | None:
    """Extract an arXiv ID from a URL, identifier string, or text."""
    if not text:
        return None
    # Strip .pdf extension if present in matching group
    text_clean = text.strip()
    match = ARXIV_ID_PATTERN.search(text_clean)
    if match:
        extracted = match.group(1)
        if extracted.endswith(".pdf"):
            extracted = extracted[:-4]
        return extracted
    return None


async def route_input_node(state: DeepResearchState) -> dict[str, Any]:
    """Inspect input query and route to either direct paper deep dive or broad topic research."""
    query = state.get("input_query", "").strip()
    logs = list(state.get("logs", []))

    arxiv_id = extract_arxiv_id(query)

    if arxiv_id:
        msg = f"Detected arXiv paper identifier: {arxiv_id}. Routing to direct paper deep-dive."
        logger.info(msg)
        logs.append(msg)
        return {
            "mode": "direct_paper",
            "paper_ids": [arxiv_id],
            "logs": logs,
        }
    else:
        msg = f"Detected topic/keyword research query: '{query}'. Routing to topic discovery."
        logger.info(msg)
        logs.append(msg)
        return {
            "mode": "topic_research",
            "search_queries": [query],
            "logs": logs,
        }
