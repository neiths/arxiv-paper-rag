from src.config import Settings
from src.services.arxiv.client import ArxivClient
from src.services.facebook.service import FacebookService
from src.services.pdf_parser.parser import PDFParserService

from .service import DeepResearchService


def make_deep_research_service(
    settings: Settings,
    arxiv_client: ArxivClient,
    pdf_parser: PDFParserService,
    facebook_service: FacebookService,
) -> DeepResearchService:
    """Factory to build DeepResearchService."""
    return DeepResearchService(
        settings=settings,
        arxiv_client=arxiv_client,
        pdf_parser=pdf_parser,
        facebook_service=facebook_service,
    )
