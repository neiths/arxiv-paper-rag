from http.client import HTTPException

from fastapi import APIRouter
from fastapi import Path

from src.dependencies import DBSessionDep
from src.schemas.paper import PaperBase, PaperCreate, PaperResponse, PaperSearchResponse
from src.repositories.paper import PaperRepository

router = APIRouter(
    prefix="/papers", tags=["papers"]
)

@router.get("/{arxiv_id}", response_model=PaperResponse)
def get_paper_details(
        db: DBSessionDep,
        arxiv_id: str = Path(
            ..., description="arXiv paper ID (e.g., '2401.00001' or '2401.00001v1')", regex=r"^\d{4}\.\d{4,5}(v\d+)?$"
        )
) -> PaperResponse:
    """Get details of paper - Currently returning mock data"""
    # TODO: Replace with actual ArXiv API call when pipeline is set up
    # paper_repo = PaperRepository(db)
    # paper = paper_repo.get_by_arxiv_id(arxiv_id)
    #
    # if not paper:
    #     raise HTTPException(status_code=404, detail="Paper not found")
    #
    # return PaperResponse.model_validate(paper)
    
    # Mock data for testing
    from datetime import datetime
    from uuid import UUID
    
    mock_paper = PaperResponse(
        id=UUID("12345678-1234-5678-1234-567812345678"),
        arxiv_id=arxiv_id,
        title="Attention Is All You Need",
        authors=[
            "Ashish Vaswani",
            "Noam Shazeer",
            "Niki Parmar",
            "Jakob Uszkoreit",
            "Llion Jones",
            "Aidan N. Gomez",
            "Lukasz Kaiser",
            "Illia Polosukhin"
        ],
        abstract="The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train.",
        categories=["cs.CL", "cs.AI", "cs.LG"],
        published_date=datetime(2017, 6, 12, 0, 0, 0),
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        created_at=datetime(2025, 12, 27, 9, 19, 16),
        updated_at=datetime(2025, 12, 27, 9, 19, 16)
    )
    
    return mock_paper




