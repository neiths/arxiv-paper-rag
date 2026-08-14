from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import httpx
import pytest
from src.exceptions import (
    ArxivAPIException,
    ArxivAPITimeoutError,
    ArxivParseError,
    PDFDownloadException,
    PDFDownloadTimeoutError,
)
from src.schemas.arxiv.paper import ArxivPaper
from src.services.arxiv.client import ArxivClient
from src.services.arxiv.factory import make_arxiv_client


class TestArxivClient:
    """Test ArxivClient fucntionality."""

    @pytest.fixture
    def arxiv_client(self):
        from src.config import ArxivSettings

        settings = ArxivSettings(
            base_url="https://export.arxiv.org/api/query",
            search_category="cs.AI",
            max_results=10,
            rate_limit_delay=0.1,  # Faster for tests
            timeout_seconds=5,
            pdf_cache_dir="/tmp/test_arxiv_cache",
        )
        # Return a configured ArxivClient for tests
        return ArxivClient(settings=settings)

    @pytest.fixture
    def mock_arxiv_response(self):
        return """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/2024.0001v1</id>
            <updated>2024-01-01T00:00:00Z</updated>
            <published>2024-01-01T00:00:00Z</published>
            <title>Test Paper Title</title>
            <summary>Test abstract content</summary>
            <author><name>Test Author</name></author>
            <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
            <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
            <link title="pdf" href="http://arxiv.org/pdf/2024.0001v1" rel="alternate" type="application/pdf"/>
          </entry>
        </feed>"""

    def test_factory_creates_client(self):
        client = make_arxiv_client()
        assert isinstance(client, ArxivClient)
        assert client.search_category == "cs.AI"
        assert client.max_results == 15

    @pytest.mark.asyncio
    async def test_fetch_papers_success(self, arxiv_client, mock_arxiv_response):
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.text = mock_arxiv_response
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            papers = await arxiv_client.fetch_papers(max_results=1)

            assert len(papers) == 1
            assert papers[0].arxiv_id == "2024.0001v1"
            assert papers[0].title == "Test Paper Title"
            assert papers[0].abstract == "Test abstract content"
            assert papers[0].authors == ["Test Author"]
            assert papers[0].categories == ["cs.AI"]

    @pytest.mark.asyncio
    async def test_fetch_papers_with_date_filters(
        self,
        arxiv_client,
        mock_arxiv_response,
    ):
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.text = mock_arxiv_response
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            papers = await arxiv_client.fetch_papers(
                max_results=1,
                from_date="20240101",
                to_date="20240131",
            )

            assert len(papers) == 1
            call_args = mock_client.return_value.__aenter__.return_value.get.call_args[
                0
            ][0]
            assert "submittedDate:[202401010000+TO+202401312359]" in call_args
