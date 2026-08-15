import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.exceptions import MetadataFetchingException, PipelineException
from src.schemas.arxiv.paper import ArxivPaper
from src.schemas.pdf_parser.models import ParserType, PdfContent
from src.services.arxiv.client import ArxivClient
from src.services.metadata_fetcher import MetadataFetcher, make_metadata_fetcher
from src.services.pdf_parser.parser import PDFParserService


class TestMetadataFetcher:
    @pytest.fixture
    def mock_arxiv_client(self):
        client = MagicMock(spec=ArxivClient)
        return client

    @pytest.fixture
    def mock_pdf_parser(self):
        parser = MagicMock(spec=PDFParserService)
        return parser

    @pytest.fixture
    def metadata_fetcher(
        self,
        mock_arxiv_client,
        mock_pdf_parser,
        tmp_path,
    ):
        return MetadataFetcher(
            arxiv_client=mock_arxiv_client,
            pdf_parser=mock_pdf_parser,
            pdf_cache_dir=tmp_path,
            max_concurrent_downloads=2,
            max_concurrent_parsing=1,
        )

    @pytest.fixture
    def sample_arxiv_papers(self):
        return [
            ArxivPaper(
                arxiv_id="2024.0001v1",
                title="Test Paper 1",
                authors=["Author 1"],
                abstract="Abstract 1",
                categories=["cs.AI"],
                published_date="2024-01-01T00:00:00Z",
                pdf_url="http://arxiv.org/pdf/2024.0001v1",
            ),
            ArxivPaper(
                arxiv_id="2024.0002v1",
                title="Test Paper 2",
                authors=["Author 2"],
                abstract="Abstract 2",
                categories=["cs.AI"],
                published_date="2024-01-02T00:00:00Z",
                pdf_url="http://arxiv.org/pdf/2024.0002v1",
            ),
        ]

    @pytest.fixture
    def sample_pdf_content(self):
        return PdfContent(
            raw_text="Sample PDF content",
            sections=[],
            tables=[],
            figures=[],
            parser_used=ParserType.DOCLING,
            metadata={},
        )

    def test_metadata_fetcher_initialization(
        self, mock_arxiv_client, mock_pdf_parser, tmp_path
    ):
        fetcher = MetadataFetcher(
            arxiv_client=mock_arxiv_client,
            pdf_parser=mock_pdf_parser,
            pdf_cache_dir=tmp_path,
            max_concurrent_downloads=2,
            max_concurrent_parsing=1,
        )
        assert fetcher.arxiv_client == mock_arxiv_client
        assert fetcher.pdf_parser == mock_pdf_parser
        assert fetcher.pdf_cache_dir == tmp_path
        assert fetcher.max_concurrent_downloads == 2
        assert fetcher.max_concurrent_parsing == 1

    @pytest.mark.asyncio
    async def tset_empty_papers_list(self, metadata_fetcher):
        result = await metadata_fetcher.fetch_and_process_papers(
            max_results=0, process_pdfs=False, store_to_db=False
        )

        assert result["papers_fetched"] == 0
        assert result["pdfs_downloaded"] == 0
        assert result["pdfs_parsed"] == 0
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_rate_limiting_respected(self, metadata_fetcher):
        metadata_fetcher.arxiv_client.fetch_papers = AsyncMock(return_value=[])

        start_time = time.time()
        await metadata_fetcher.fetch_and_process_papers(max_results=1)
        end_time = time.time()

        assert end_time - start_time < 1.0
