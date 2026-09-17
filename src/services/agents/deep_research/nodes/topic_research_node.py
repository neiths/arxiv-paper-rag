import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime
from src.services.agents.deep_research.context import DeepResearchContext
from src.services.agents.deep_research.prompts import TOPIC_DECOMPOSITION_PROMPT
from src.services.agents.deep_research.state import DeepResearchState

logger = logging.getLogger(__name__)


async def topic_research_node(
    state: DeepResearchState,
    runtime: Runtime[DeepResearchContext],
) -> dict[str, Any]:
    """Decompose research topic, search arXiv, and gather relevant candidate papers."""
    context = runtime.context
    arxiv_client = context.arxiv_client
    pdf_parser = context.pdf_parser
    llm = context.llm

    topic = state.get("input_query", "").strip()
    logs = list(state.get("logs", []))

    logs.append(f"Analyzing research topic: '{topic}'...")

    # 1. Use LLM to plan targeted arXiv queries and research questions
    search_queries = [f"all:{topic}"]
    key_questions = []

    try:
        prompt_content = TOPIC_DECOMPOSITION_PROMPT.format(topic=topic)
        response = await llm.ainvoke([HumanMessage(content=prompt_content)])
        response_text = str(response.content)

        # Attempt to parse JSON response
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}")
        if start_idx != -1 and end_idx != -1:
            json_str = response_text[start_idx : end_idx + 1]
            data = json.loads(json_str)
            if "search_queries" in data and isinstance(data["search_queries"], list):
                search_queries = [
                    q.strip() for q in data["search_queries"] if q.strip()
                ]
            if "key_questions" in data and isinstance(data["key_questions"], list):
                key_questions = data["key_questions"]
    except Exception as e:
        logger.warning(
            f"LLM topic decomposition failed ({e}), using default search query."
        )
        logs.append("Using direct keyword search for arXiv retrieval.")

    logs.append(f"Executing arXiv search with {len(search_queries)} queries...")

    # 2. Search arXiv with the queries
    found_papers: dict[str, Any] = {}
    for q in search_queries[:2]:
        try:
            # Construct valid arXiv query format
            safe_query = (
                f"ti:{q} OR abs:{q}"
                if not any(op in q for op in [":", "AND", "OR"])
                else q
            )
            papers = await arxiv_client.fetch_papers_with_query(
                search_query=safe_query,
                max_results=3,
                sort_by="relevance",
            )
            for p in papers:
                if p.arxiv_id not in found_papers:
                    found_papers[p.arxiv_id] = p
        except Exception as err:
            logger.warning(f"arXiv search query '{q}' error: {err}")

    # Fallback to category search if no papers found
    if not found_papers:
        logs.append("No exact query matches; falling back to category search...")
        try:
            papers = await arxiv_client.fetch_papers(
                max_results=3, sort_by="submittedDate"
            )
            for p in papers:
                found_papers[p.arxiv_id] = p
        except Exception as err:
            logger.error(f"Fallback paper search failed: {err}")

    if not found_papers:
        err_msg = f"No papers found on arXiv for topic: '{topic}'"
        logs.append(f"Error: {err_msg}")
        return {"error": err_msg, "logs": logs}

    paper_list = list(found_papers.values())[:4]
    logs.append(f"Found {len(paper_list)} candidate papers.")

    target_papers = []
    paper_full_texts = {}

    for idx, paper in enumerate(paper_list):
        p_dict = {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "authors": paper.authors,
            "abstract": paper.abstract,
            "published_date": paper.published_date,
            "categories": paper.categories,
            "pdf_url": paper.pdf_url,
            "abs_url": f"https://arxiv.org/abs/{paper.arxiv_id}",
        }
        target_papers.append(p_dict)

        # For the top paper, attempt to fetch full PDF text for deep analysis
        content = f"# {paper.title}\n\n## Abstract\n{paper.abstract}\n"
        if idx == 0:
            try:
                pdf_path = await arxiv_client.download_pdf(paper)
                if pdf_path and pdf_path.exists():
                    parsed = await pdf_parser.parse_pdf(pdf_path)
                    if parsed and parsed.raw_text:
                        content += f"\n## Full Text Excerpts\n{parsed.raw_text[:10000]}"
            except Exception as e:
                logger.warning(
                    f"Failed to parse PDF for top paper {paper.arxiv_id}: {e}"
                )

        paper_full_texts[paper.arxiv_id] = content

    return {
        "search_queries": search_queries,
        "sub_questions": key_questions,
        "target_papers": target_papers,
        "paper_full_texts": paper_full_texts,
        "logs": logs,
    }
