import logging
from typing import Any, TypedDict
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session
from src.config import Settings
from src.repositories.paper import PaperRepository
from src.services.agent.prompts import (
    FACEBOOK_PAPER_SUMMARY_SYSTEM_PROMPT,
    FACEBOOK_PAPER_SUMMARY_USER_PROMPT,
)
from src.services.facebook.client import FacebookClient

logger = logging.getLogger(__name__)


class PaperAgentState(TypedDict, total=False):
    arxiv_id: str | None
    paper_id: str | None
    model_name: str | None
    paper_data: dict[str, Any] | None
    used_full_text: bool
    summary: str | None
    facebook_post: str | None
    dry_run: bool
    status: str
    facebook_post_id: str | None
    error: str | None


class FacebookPublisherAgent:
    """LangGraph Agent for fetching papers, generating structured summaries, and posting to Facebook."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        facebook_client: FacebookClient | None = None,
    ):
        self.session = session
        self.settings = settings
        self.repository = PaperRepository(session)
        self.facebook_client = facebook_client or FacebookClient(settings.facebook)
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(PaperAgentState)

        builder.add_node("fetch_paper", self._fetch_paper_node)
        builder.add_node("summarize_paper", self._summarize_paper_node)
        builder.add_node("format_facebook_post", self._format_facebook_post_node)
        builder.add_node("publish_facebook", self._publish_facebook_node)

        builder.set_entry_point("fetch_paper")
        builder.add_edge("fetch_paper", "summarize_paper")
        builder.add_edge("summarize_paper", "format_facebook_post")
        builder.add_edge("format_facebook_post", "publish_facebook")
        builder.add_edge("publish_facebook", END)

        return builder.compile()

    def _fetch_paper_node(self, state: PaperAgentState) -> PaperAgentState:
        logger.info("LangGraph Node [1/4]: Fetching paper from DB...")
        paper = None
        arxiv_id_param = state.get("arxiv_id")
        paper_id_param = state.get("paper_id")

        if arxiv_id_param:
            paper = self.repository.get_by_arxiv_id(arxiv_id_param)
        elif paper_id_param:
            try:
                paper = self.repository.get_by_id(UUID(paper_id_param))
            except Exception:
                paper = None

        if not paper:
            # Fallback: get the newest paper in DB
            papers = self.repository.get_all(limit=1)
            if papers:
                paper = papers[0]

        if not paper:
            logger.error("No papers found in database.")
            return {
                "error": "No paper found in database.",
                "status": "failed",
            }

        used_full_text = False
        full_text_content = ""

        # Prefer full parsed text if available
        if paper.raw_text and len(paper.raw_text.strip()) > 100:
            used_full_text = True
            full_text_content = f"--- EXTRACTED PARSED TEXT (FIRST 4000 CHARS) ---\n{paper.raw_text[:4000]}"
        elif paper.sections and isinstance(paper.sections, list):
            used_full_text = True
            sec_texts = []
            for sec in paper.sections[:5]:
                if isinstance(sec, dict) and "heading" in sec and "text" in sec:
                    sec_texts.append(f"### {sec['heading']}\n{sec['text'][:500]}")
            full_text_content = "--- PARSED SECTIONS ---\n" + "\n\n".join(sec_texts)

        authors_list = (
            paper.authors if isinstance(paper.authors, list) else [str(paper.authors)]
        )
        categories_list = (
            paper.categories
            if isinstance(paper.categories, list)
            else [str(paper.categories)]
        )
        published_str = (
            paper.published_date.strftime("%Y-%m-%d")
            if paper.published_date
            else "Recent"
        )

        paper_data = {
            "id": str(paper.id),
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "authors": authors_list,
            "abstract": paper.abstract,
            "categories": categories_list,
            "published_date": published_str,
            "pdf_url": paper.pdf_url,
            "full_text_section": full_text_content,
        }

        logger.info(
            f"Paper selected: '{paper.title}' (arXiv:{paper.arxiv_id}). Used full text: {used_full_text}"
        )
        return {
            "paper_id": str(paper.id),
            "arxiv_id": paper.arxiv_id,
            "paper_data": paper_data,
            "used_full_text": used_full_text,
            "status": "paper_fetched",
        }

    def _summarize_paper_node(self, state: PaperAgentState) -> PaperAgentState:
        if state.get("error"):
            return state

        logger.info("LangGraph Node [2/4]: Generating paper summary with LLM...")
        paper_data = state.get("paper_data")
        if not paper_data:
            return {"error": "Missing paper data for summarization", "status": "failed"}

        model_name = state.get("model_name") or self.settings.ollama_model
        primary_cat = (
            paper_data["categories"][0] if paper_data.get("categories") else "AI"
        )
        primary_cat_clean = primary_cat.replace(".", "")

        sys_prompt = FACEBOOK_PAPER_SUMMARY_SYSTEM_PROMPT.format(
            title=paper_data["title"],
            authors=", ".join(paper_data["authors"][:5]),
            paper_link=f"https://arxiv.org/abs/{paper_data['arxiv_id']}",
            primary_category=primary_cat_clean,
        )

        user_prompt = FACEBOOK_PAPER_SUMMARY_USER_PROMPT.format(
            title=paper_data["title"],
            arxiv_id=paper_data["arxiv_id"],
            authors=", ".join(paper_data["authors"]),
            categories=", ".join(paper_data["categories"]),
            published_date=paper_data["published_date"],
            abstract=paper_data["abstract"],
            full_text_section=paper_data.get("full_text_section", ""),
        )

        try:
            llm = ChatOllama(
                model=model_name,
                base_url=self.settings.ollama_host,
                timeout=float(self.settings.ollama_timeout),
            )
            messages = [
                SystemMessage(content=sys_prompt),
                HumanMessage(content=user_prompt),
            ]
            response = llm.invoke(messages)
            summary_text = str(response.content)
            logger.info("Summary generated successfully.")
            return {
                "summary": summary_text,
                "status": "summarized",
            }
        except Exception as e:
            logger.error(f"LLM summarization failed: {e}")
            return {"error": f"LLM summarization failed: {e}", "status": "failed"}

    def _format_facebook_post_node(self, state: PaperAgentState) -> PaperAgentState:
        if state.get("error"):
            return state

        logger.info("LangGraph Node [3/4]: Formatting Facebook post...")
        summary = state.get("summary", "")
        paper_data = state.get("paper_data", {})
        arxiv_id = paper_data.get("arxiv_id", "")
        paper_link = f"https://arxiv.org/abs/{arxiv_id}"

        facebook_post = (
            f"{summary.strip()}\n\n🔗 Paper Link: {paper_link}"
            if paper_link not in summary
            else summary.strip()
        )

        return {
            "facebook_post": facebook_post,
            "status": "formatted",
        }

    async def _publish_facebook_node(self, state: PaperAgentState) -> PaperAgentState:
        if state.get("error"):
            return state

        logger.info("LangGraph Node [4/4]: Processing Facebook publishing...")
        facebook_post = state.get("facebook_post", "")
        paper_data = state.get("paper_data", {})
        paper_link = f"https://arxiv.org/abs/{paper_data.get('arxiv_id', '')}"
        dry_run = state.get("dry_run", True)

        if dry_run or not self.facebook_client.is_configured:
            reason = (
                "Dry run requested"
                if dry_run
                else "Facebook client credentials not configured"
            )
            logger.info(f"Skipping actual Facebook API post ({reason}).")
            return {
                "facebook_post_id": "DRY_RUN_ID",
                "status": "dry_run_success",
            }

        try:
            result = await self.facebook_client.post_to_page(
                message=facebook_post, link=paper_link
            )
            post_id = result.get("id", "PUBLISHED_ID")
            logger.info(f"Successfully posted to Facebook Page! Post ID: {post_id}")
            return {
                "facebook_post_id": post_id,
                "status": "published",
            }
        except Exception as e:
            logger.error(f"Facebook API publish error: {e}")
            return {
                "error": f"Facebook API publish error: {e}",
                "status": "failed",
            }

    async def run(
        self,
        arxiv_id: str | None = None,
        paper_id: str | None = None,
        dry_run: bool = True,
        model_name: str | None = None,
    ) -> PaperAgentState:
        """Execute the full LangGraph Facebook Publisher workflow."""
        initial_state: PaperAgentState = {
            "arxiv_id": arxiv_id,
            "paper_id": paper_id,
            "model_name": model_name,
            "dry_run": dry_run,
            "used_full_text": False,
            "status": "started",
        }
        final_state = await self.graph.ainvoke(initial_state)
        return final_state
