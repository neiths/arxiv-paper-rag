import logging
import time
from typing import Any

from src.config import Settings
from src.services.agents.llm_factory import get_agent_llm
from src.services.arxiv.client import ArxivClient
from src.services.facebook.service import FacebookService
from src.services.pdf_parser.parser import PDFParserService

from .context import DeepResearchContext
from .graph import build_deep_research_graph
from .state import DeepResearchState

logger = logging.getLogger(__name__)


class DeepResearchService:
    """Service orchestrating end-to-end Deep Research and Facebook post publishing."""

    def __init__(
        self,
        settings: Settings,
        arxiv_client: ArxivClient,
        pdf_parser: PDFParserService,
        facebook_service: FacebookService,
    ):
        self.settings = settings
        self.arxiv_client = arxiv_client
        self.pdf_parser = pdf_parser
        self.facebook_service = facebook_service
        self.graph = build_deep_research_graph()

    async def run_research(
        self,
        query: str,
        language: str = "en",
        post_style: str = "technical_deep_dive",
        auto_publish: bool | None = None,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        """Execute deep research on arXiv and generate/publish a Facebook post.

        :param query: arXiv URL, paper ID (e.g. "2403.05530"), or research topic string.
        :param language: Output language for Facebook post ("en" or "vi").
        :param post_style: "technical_deep_dive", "executive_summary", or "viral_breakdown".
        :param auto_publish: Whether to post directly to Facebook Page (defaults to config).
        :param model_name: Optional LLM model override (e.g. "llama3.2:latest", "gemini-1.5-flash").
        :returns: Result dictionary containing research findings and post details.
        """
        start_time = time.time()
        logger.info(f"Starting Deep Research for query='{query}', lang='{language}'")

        should_publish = (
            auto_publish
            if auto_publish is not None
            else self.settings.facebook.auto_publish
        )

        # Resolve LLM dynamically (supports Ollama, Gemini, OpenAI)
        llm = get_agent_llm(
            settings=self.settings,
            model_name=model_name,
        )

        context = DeepResearchContext(
            arxiv_client=self.arxiv_client,
            pdf_parser=self.pdf_parser,
            facebook_service=self.facebook_service,
            llm=llm,
            settings=self.settings,
        )

        initial_state: DeepResearchState = {
            "input_query": query,
            "language": language,
            "post_style": post_style,
            "auto_publish": should_publish,
            "model_name": model_name or self.settings.ollama_model,
            "target_papers": [],
            "paper_full_texts": {},
            "sub_questions": [],
            "search_queries": [],
            "paper_ids": [],
            "logs": [
                f"Deep Research Agent initialized at {time.strftime('%Y-%m-%d %H:%M:%S')}"
            ],
        }

        try:
            final_state = await self.graph.ainvoke(initial_state, context=context)
            elapsed = time.time() - start_time
            logger.info(f"Deep Research completed in {elapsed:.2f}s")

            has_error = bool(final_state.get("error"))
            return {
                "success": not has_error,
                "input_query": query,
                "mode": final_state.get("mode", "unknown"),
                "language": language,
                "papers": final_state.get("target_papers", []),
                "synthesis_report": final_state.get("synthesis_report", ""),
                "facebook_post": final_state.get("facebook_post", ""),
                "facebook_post_id": final_state.get("facebook_post_id"),
                "facebook_post_url": final_state.get("facebook_post_url"),
                "published_to_facebook": final_state.get(
                    "published_to_facebook", False
                ),
                "publish_error": final_state.get("publish_error"),
                "logs": final_state.get("logs", []),
                "error": final_state.get("error"),
                "duration_seconds": round(elapsed, 2),
            }

        except Exception as e:
            logger.error(f"Error running deep research: {e}", exc_info=True)
            return {
                "success": False,
                "input_query": query,
                "papers": [],
                "synthesis_report": "",
                "facebook_post": "",
                "published_to_facebook": False,
                "error": str(e),
                "duration_seconds": round(time.time() - start_time, 2),
                "logs": [f"Fatal failure during workflow execution: {e!s}"],
            }
