from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from src.config import FacebookSettings, Settings
from src.models.paper import Paper
from src.services.agent.facebook_publisher import FacebookPublisherAgent
from src.services.facebook.client import FacebookClient


@pytest.fixture
def mock_settings():
    return Settings(
        facebook=FacebookSettings(
            page_id="123456789",
            page_access_token="fake_token",
            graph_api_version="v20.0",
            enabled=True,
        )
    )


@pytest.fixture
def mock_paper():
    return Paper(
        id=None,
        arxiv_id="2507.12345",
        title="Test Attention Mechanism in Large Language Models",
        authors=["Alice Smith", "Bob Jones"],
        abstract="This paper introduces a novel self-attention mechanism that speeds up transformer training by 50%.",
        categories=["cs.AI", "cs.LG"],
        published_date=datetime.now(UTC),
        pdf_url="https://arxiv.org/pdf/2507.12345.pdf",
        raw_text="Introduction\nAttention mechanisms are essential for transformers...",
        sections=[
            {"heading": "Introduction", "text": "Attention mechanisms are essential..."}
        ],
    )


@pytest.mark.asyncio
async def test_facebook_client_post_success(mock_settings):
    client = FacebookClient(mock_settings.facebook)
    assert client.is_configured is True

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123456789_987654321"}
        mock_post.return_value = mock_response

        res = await client.post_to_page(
            "Hello world!", "https://arxiv.org/abs/2507.12345"
        )
        assert res["id"] == "123456789_987654321"


@pytest.mark.asyncio
async def test_agent_dry_run_flow(mock_settings, mock_paper):
    mock_session = MagicMock()
    mock_repo = MagicMock()
    mock_repo.get_all.return_value = [mock_paper]
    mock_repo.get_by_arxiv_id.return_value = mock_paper

    agent = FacebookPublisherAgent(session=mock_session, settings=mock_settings)
    agent.repository = mock_repo

    fake_llm_response = MagicMock()
    fake_llm_response.content = "🚀 **Novel Attention Mechanism!**\n\n📄 **Title**: Test Attention\n👥 **Authors**: Alice Smith\n\n🌟 **Key Features**\n- Faster training"

    with patch("src.services.agent.facebook_publisher.ChatOllama") as mock_chat:
        mock_chat.return_value.invoke.return_value = fake_llm_response

        result = await agent.run(arxiv_id="2507.12345", dry_run=True)

        assert result["status"] == "dry_run_success"
        assert result["arxiv_id"] == "2507.12345"
        assert "Novel Attention Mechanism" in result["facebook_post"]
        assert "https://arxiv.org/abs/2507.12345" in result["facebook_post"]
        assert result["facebook_post_id"] == "DRY_RUN_ID"
