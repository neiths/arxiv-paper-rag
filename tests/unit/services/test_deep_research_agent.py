from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.config import Settings
from src.schemas.arxiv.paper import ArxivPaper
from src.services.agents.deep_research.nodes.route_input_node import (
    extract_arxiv_id,
    route_input_node,
)
from src.services.agents.deep_research.service import DeepResearchService
from src.services.facebook.models import FacebookPostResponse


def test_extract_arxiv_id():
    """Test extracting arXiv IDs from various inputs."""
    assert extract_arxiv_id("https://arxiv.org/abs/2403.05530") == "2403.05530"
    assert extract_arxiv_id("https://arxiv.org/pdf/2403.05530.pdf") == "2403.05530"
    assert extract_arxiv_id("arxiv:2403.05530v1") == "2403.05530v1"
    assert extract_arxiv_id("2403.05530") == "2403.05530"
    assert extract_arxiv_id("Test-Time Compute and Reasoning Models") is None


@pytest.mark.asyncio
async def test_route_input_node_direct_paper():
    state = {"input_query": "https://arxiv.org/abs/2403.05530", "logs": []}
    result = await route_input_node(state)
    assert result["mode"] == "direct_paper"
    assert result["paper_ids"] == ["2403.05530"]


@pytest.mark.asyncio
async def test_route_input_node_topic():
    state = {"input_query": "Diffusion Transformers in Computer Vision", "logs": []}
    result = await route_input_node(state)
    assert result["mode"] == "topic_research"
    assert "Diffusion Transformers" in result["search_queries"][0]


@pytest.mark.asyncio
async def test_deep_research_service_end_to_end_direct_paper():
    from src.config import FacebookSettings

    fb_settings = FacebookSettings(
        auto_publish=True, enabled=True, page_id="123", page_access_token="tok"
    )
    settings = Settings(facebook=fb_settings)

    # Mock ArxivClient
    arxiv_client = MagicMock()
    mock_paper = ArxivPaper(
        arxiv_id="2403.05530",
        title="Gemini 1.5: Unlocking Multimodal Understanding Across Millions of Tokens",
        authors=["Gemini Team", "DeepMind"],
        abstract="We introduce Gemini 1.5, a highly compute-efficient multimodal model...",
        published_date="2024-03-08",
        categories=["cs.AI", "cs.CL"],
        pdf_url="https://arxiv.org/pdf/2403.05530.pdf",
    )
    arxiv_client.fetch_paper_by_id = AsyncMock(return_value=mock_paper)
    arxiv_client.download_pdf = AsyncMock(
        return_value=None
    )  # Simulate abstract fallback

    # Mock PDFParser
    pdf_parser = MagicMock()

    # Mock FacebookService
    facebook_service = MagicMock()
    facebook_service.publish_paper_post = AsyncMock(
        return_value=FacebookPostResponse(
            success=True,
            post_id="fb_123456789_post",
            url="https://www.facebook.com/fb_123456789_post",
            is_simulated=False,
            message="Published",
        )
    )

    # Mock LLM response
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[
            MagicMock(
                content="### Deep Analysis\nCore breakthrough is 1M token context window..."
            ),
            MagicMock(
                content="🚀 Gemini 1.5: 1M Token Context!\n\nDeepMind just released Gemini 1.5... #AI"
            ),
        ]
    )

    with patch(
        "src.services.agents.deep_research.service.get_agent_llm", return_value=mock_llm
    ):
        service = DeepResearchService(
            settings=settings,
            arxiv_client=arxiv_client,
            pdf_parser=pdf_parser,
            facebook_service=facebook_service,
        )

        result = await service.run_research(
            query="https://arxiv.org/abs/2403.05530",
            language="en",
            auto_publish=True,
        )

        assert result["success"] is True
        assert result["mode"] == "direct_paper"
        assert len(result["papers"]) == 1
        assert "Gemini 1.5" in result["papers"][0]["title"]
        assert "Deep Analysis" in result["synthesis_report"]
        assert "Gemini 1.5" in result["facebook_post"]
        assert result["published_to_facebook"] is True
        assert result["facebook_post_id"] == "fb_123456789_post"
