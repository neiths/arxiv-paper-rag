import logging
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime
from src.services.agents.deep_research.context import DeepResearchContext
from src.services.agents.deep_research.prompts import (
    DEEP_PAPER_ANALYSIS_PROMPT,
    MULTI_PAPER_SYNTHESIS_PROMPT,
)
from src.services.agents.deep_research.state import DeepResearchState

logger = logging.getLogger(__name__)


async def deep_analysis_node(
    state: DeepResearchState,
    runtime: Runtime[DeepResearchContext],
) -> dict[str, Any]:
    """Perform in-depth scientific analysis and technical synthesis using LLM."""
    context = runtime.context
    llm = context.llm

    target_papers = state.get("target_papers", [])
    paper_full_texts = state.get("paper_full_texts", {})
    mode = state.get("mode", "direct_paper")
    logs = list(state.get("logs", []))

    if not target_papers:
        err = "No papers available for deep analysis."
        logs.append(f"Error: {err}")
        return {"error": err, "logs": logs}

    logs.append(f"Beginning deep technical evaluation ({mode} mode)...")
    logger.info(f"Running deep analysis for {len(target_papers)} papers in {mode} mode")

    try:
        if mode == "direct_paper":
            paper = target_papers[0]
            content = paper_full_texts.get(paper["arxiv_id"], paper["abstract"])
            prompt = DEEP_PAPER_ANALYSIS_PROMPT.format(
                title=paper["title"],
                authors=", ".join(paper["authors"][:5]),
                arxiv_id=paper["arxiv_id"],
                content=content[:15000],  # Keep prompt within context bounds
            )
        else:
            # Topic research mode: multi-paper synthesis
            summaries = []
            for i, p in enumerate(target_papers, 1):
                summaries.append(
                    f"Paper {i}: {p['title']}\n"
                    f"Authors: {', '.join(p['authors'][:4])}\n"
                    f"ArXiv ID: {p['arxiv_id']}\n"
                    f"Abstract: {p['abstract']}\n"
                )
            papers_summary_text = "\n---\n".join(summaries)
            prompt = MULTI_PAPER_SYNTHESIS_PROMPT.format(
                topic=state.get("input_query", ""),
                papers_summary=papers_summary_text,
            )

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        synthesis_report = str(response.content).strip()

        logs.append("Completed deep technical synthesis report.")
        return {
            "synthesis_report": synthesis_report,
            "logs": logs,
        }

    except Exception as e:
        err_msg = f"Deep analysis generation failed: {e!s}"
        logger.error(err_msg)
        logs.append(f"Error: {err_msg}")
        return {"error": err_msg, "logs": logs}
