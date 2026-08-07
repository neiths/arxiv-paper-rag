import logging
import sys
from functools import lru_cache
from typing import Any

sys.path.insert(0, "/opt/airflow")

# Initlialize all the services and clients that will be used in the DAGs.
# This is done to avoid re-initializing them for each task, which can be expensive.
from src.db.factory import make_database
from src.services.arxiv.factory import make_arxiv_client
from src.services.metadata_fetcher import make_metadata_fetcher
from src.services.opensearch.factory import make_opensearch_client
from src.services.pdf_parser.factory import make_pdf_parser_service

# Initialize logger
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_cached_services() -> tuple[Any, Any, Any, Any, Any]:
    """
    Initialize and cache the services and clients used in the DAGs.

    Returns:
        Tuple containing initialized services and clients.
    """
    logger.info("Initializing services and clients...")

    # Initialize database
    db = make_database()

    # Initialize Arxiv client
    arxiv_client = make_arxiv_client()

    # Initialize metadata fetcher
    metadata_fetcher = make_metadata_fetcher()

    # Initialize OpenSearch client
    opensearch_client = make_opensearch_client()

    # Initialize PDF parser service
    pdf_parser_service = make_pdf_parser_service()

    # Create metadata fetcher with dependencies
    metadata_fetcher = make_metadata_fetcher(arxiv_client, pdf_parser_service)

    logger.info("Services and clients initialized successfully.")

    return (arxiv_client, pdf_parser_service, db, metadata_fetcher, opensearch_client)
