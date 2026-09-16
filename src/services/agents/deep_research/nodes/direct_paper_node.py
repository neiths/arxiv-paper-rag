import logging
from typing import Any

from langgraph.runtime import Runtime
from src.services.agents.deep_research.context import DeepResearchContext
from src.services.agents.deep_research.state import DeepResearchState

logger = logging.getLogger(__name__)


async def direct_paper_node(
    state: DeepResearchState,
    runtime: Runtime[DeepResearchContext],
) -> dict[str, Any]:
    """Fetch specific arXiv paper metadata and parse its full PDF content."""
    context = runtime.context
    arxiv_client = context.arxiv_client
    pdf_parser = context.pdf_parser

    paper_ids = state.get("paper_ids", [])
    logs = list(state.get("logs", []))

    if not paper_ids:
        err = "No arXiv paper ID found in state."
        logger.error(err)
        logs.append(f"Error: {err}")
        return {"error": err, "logs": logs}

    arxiv_id = paper_ids[0]
    logs.append(f"Fetching metadata for paper {arxiv_id} from arXiv API...")
    logger.info(f"Fetching paper {arxiv_id}")

    try:
        paper = await arxiv_client.fetch_paper_by_id(arxiv_id)
        if not paper:
            err = f"Could not find paper with ID: {arxiv_id} on arXiv."
            logs.append(err)
            return {"error": err, "logs": logs}

        paper_dict = {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "authors": paper.authors,
            "abstract": paper.abstract,
            "published_date": paper.published_date,
            "categories": paper.categories,
            "pdf_url": paper.pdf_url,
            "abs_url": f"https://arxiv.org/abs/{paper.arxiv_id}",
        }

        full_content = f"# {paper.title}\n\n## Abstract\n{paper.abstract}\n\n"

        # Try downloading & parsing PDF for deep full-text extraction
        pdf_path = None
        try:
            logs.append(f"Downloading PDF for paper {arxiv_id}...")
            pdf_path = await arxiv_client.download_pdf(paper)
        except Exception as e:
            logger.warning(
                f"PDF download failed for {arxiv_id}: {e}. Will rely on abstract."
            )
            logs.append(
                f"Warning: PDF download failed ({e}), continuing with abstract."
            )

        if pdf_path and pdf_path.exists():
            try:
                logs.append("Extracting structured sections via Docling parser...")
                parsed = await pdf_parser.parse_pdf(pdf_path)
                if parsed and parsed.sections:
                    logs.append(
                        f"Successfully extracted {len(parsed.sections)} sections from PDF."
                    )
                    section_texts = []
                    for s in parsed.sections:
                        # Include key sections, skipping references or appendix if too large
                        title_lower = s.title.lower()
                        if "reference" in title_lower or "acknowledg" in title_lower:
                            continue
                        section_texts.append(f"### {s.title}\n{s.content[:3000]}")

                    full_content += "\n\n".join(section_texts)
                elif parsed and parsed.raw_text:
                    # Limit raw text to first ~12,000 characters for token safety
                    full_content += (
                        f"\n\n## Extracted Paper Text\n{parsed.raw_text[:12000]}"
                    )
            except Exception as e:
                logger.warning(f"Docling PDF parsing failed for {arxiv_id}: {e}")
                logs.append(
                    f"Warning: PDF parsing failed ({e}). Using abstract for analysis."
                )

        logs.append(f"Ready for deep analysis of '{paper.title}'.")
        return {
            "target_papers": [paper_dict],
            "paper_full_texts": {paper.arxiv_id: full_content},
            "logs": logs,
        }

    except Exception as e:
        err_msg = f"Failed to retrieve paper {arxiv_id}: {e!s}"
        logger.error(err_msg)
        logs.append(f"Error: {err_msg}")
        return {"error": err_msg, "logs": logs}
