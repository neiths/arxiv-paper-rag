from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from src.config import Settings
from src.services.arxiv.client import ArxivClient
from src.services.facebook.service import FacebookService
from src.services.pdf_parser.parser import PDFParserService


@dataclass
class DeepResearchContext:
    """Runtime dependencies injected into the Deep Research LangGraph nodes."""

    arxiv_client: ArxivClient
    pdf_parser: PDFParserService
    facebook_service: FacebookService
    llm: BaseChatModel
    settings: Settings
