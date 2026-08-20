from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from src.main import app


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Async backend for testing."""
    return "asyncio"


@pytest.fixture
async def client():
    """HTTP client for API testing with mocked services."""
    # Mock database startup and session to prevent real connections
    with (
        patch(
            "src.db.interfaces.postgresql.PostgreSQLDataBase.startup"
        ) as mock_startup,
        patch(
            "src.db.interfaces.postgresql.PostgreSQLDataBase.get_session"
        ) as mock_get_session,
        patch("src.main.make_opensearch_client") as mock_os,
        patch("src.main.make_arxiv_client") as mock_arxiv,
        patch("src.main.make_pdf_parser_service") as mock_pdf,
        patch("src.main.make_ollama_client") as mock_ollama,
        patch("src.main.make_cache_client") as mock_cache,
        patch(
            "src.repositories.paper.PaperRepository.get_by_arxiv_id"
        ) as mock_get_by_id,
    ):
        # Mock startup to do nothing
        mock_startup.return_value = None

        # Mock get_session to return a mock session
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_get_session.return_value.__exit__.return_value = None

        # Mock repository methods to return None (not found) by default
        mock_get_by_id.return_value = None

        # Set up other mock return values
        mock_os_instance = MagicMock()
        mock_os_instance.health_check.return_value = True
        mock_os_instance.setup_indices.return_value = {"hybrid_index": True}
        mock_os_instance.client.count.return_value = {"count": 10}
        mock_os.return_value = mock_os_instance
        mock_arxiv.return_value = MagicMock()
        mock_pdf.return_value = MagicMock()
        mock_ollama.return_value = AsyncMock()
        mock_cache.return_value = MagicMock()

        async with LifespanManager(app) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as client:
                yield client
