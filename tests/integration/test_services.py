import pytest
from unittest.mock import MagicMock, patch
from src.config import get_settings
from src.services.arxiv.factory import make_arxiv_client
from src.services.opensearch.factory import make_opensearch_client


@pytest.mark.asyncio
async def test_arxiv_client_basic(mock_arxiv_response):
    """Test arXiv client with mocked API response to avoid rate limiting."""
    client = make_arxiv_client()

    # Mock the HTTP request to avoid hitting the real arXiv API (which enforces rate limiting)
    with patch("httpx.AsyncClient") as mock_http_client:
        mock_response = MagicMock()
        mock_response.text = mock_arxiv_response
        mock_response.raise_for_status.return_value = None

        mock_http_client.return_value.__aenter__.return_value.get.return_value = (
            mock_response
        )

        papers = await client.fetch_papers(max_results=1)

        assert isinstance(papers, list)
        assert len(papers) == 1
        assert papers[0].arxiv_id == "2401.00001v1"
        assert (
            papers[0].title == "Attention Is All You Need: A Transformer Architecture"
        )


def test_opensearch_client_health():
    client = make_opensearch_client()

    health = client.health_check()
    assert isinstance(health, bool)


def test_settings_loading():
    settings = get_settings()

    assert hasattr(settings, "app_version")
    assert hasattr(settings, "service_name")
    assert hasattr(settings, "environment")
