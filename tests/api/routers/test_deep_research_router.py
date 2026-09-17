from unittest.mock import AsyncMock, patch

import pytest
from src.services.facebook.models import FacebookPageInfo, FacebookPostResponse


@pytest.mark.asyncio
async def test_deep_research_run_endpoint(client):
    mock_result = {
        "success": True,
        "input_query": "https://arxiv.org/abs/2403.05530",
        "mode": "direct_paper",
        "language": "en",
        "papers": [{"title": "Gemini 1.5", "arxiv_id": "2403.05530"}],
        "synthesis_report": "Deep evaluation of Gemini 1.5...",
        "facebook_post": "🚀 Gemini 1.5 Breakthrough!",
        "facebook_post_id": "fb_123",
        "facebook_post_url": "https://facebook.com/fb_123",
        "published_to_facebook": True,
        "duration_seconds": 1.5,
        "logs": [],
        "error": None,
    }

    with patch(
        "src.services.agents.deep_research.service.DeepResearchService.run_research",
        new_callable=AsyncMock,
    ) as mock_run:
        mock_run.return_value = mock_result

        response = await client.post(
            "/api/v1/deep-research/run",
            json={
                "query": "https://arxiv.org/abs/2403.05530",
                "language": "en",
                "post_style": "technical_deep_dive",
                "auto_publish": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["facebook_post_id"] == "fb_123"
        assert data["published_to_facebook"] is True


@pytest.mark.asyncio
async def test_deep_research_publish_facebook_endpoint(client):
    mock_resp = FacebookPostResponse(
        success=True,
        post_id="post_manual_123",
        url="https://facebook.com/post_manual_123",
        is_simulated=False,
        message="Published successfully",
    )

    with patch(
        "src.services.facebook.service.FacebookService.publish_paper_post",
        new_callable=AsyncMock,
    ) as mock_pub:
        mock_pub.return_value = mock_resp

        response = await client.post(
            "/api/v1/deep-research/publish-facebook",
            json={
                "message": "Custom post content to publish!",
                "link": "https://arxiv.org/abs/2403.05530",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["post_id"] == "post_manual_123"


@pytest.mark.asyncio
async def test_deep_research_facebook_status_endpoint(client):
    mock_status = FacebookPageInfo(
        page_id="1234567890",
        name="AI Research Daily",
        is_valid=True,
    )

    with patch(
        "src.services.facebook.service.FacebookService.verify_connection",
        new_callable=AsyncMock,
    ) as mock_verify:
        mock_verify.return_value = mock_status

        response = await client.get("/api/v1/deep-research/facebook/status")
        assert response.status_code == 200
        data = response.json()
        assert data["page_id"] == "1234567890"
        assert data["is_valid"] is True
