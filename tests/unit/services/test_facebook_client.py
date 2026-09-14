from unittest.mock import AsyncMock, patch

import pytest
from src.config import FacebookSettings
from src.services.facebook.client import FacebookClient
from src.services.facebook.service import FacebookService


@pytest.fixture
def test_fb_settings():
    return FacebookSettings(
        page_id="1234567890",
        page_access_token="EAABtest_token",
        enabled=True,
        dry_run=False,
    )


@pytest.fixture
def unconfigured_fb_settings():
    return FacebookSettings(
        page_id="",
        page_access_token="",
        enabled=False,
        dry_run=False,
    )


@pytest.mark.asyncio
async def test_facebook_client_dry_run_when_unconfigured(unconfigured_fb_settings):
    client = FacebookClient(settings=unconfigured_fb_settings)
    assert not client.is_configured

    # Publish should simulate without throwing error
    response = await client.publish_feed_post(
        message="Exciting paper on Deep Agents!",
        link="https://arxiv.org/abs/2401.00001",
    )

    assert response.success is True
    assert response.is_simulated is True
    assert "simulated" in (response.post_id or "")


@pytest.mark.asyncio
async def test_facebook_client_publish_feed_success(test_fb_settings):
    client = FacebookClient(settings=test_fb_settings)
    assert client.is_configured

    from unittest.mock import MagicMock

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "1234567890_987654321"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        response = await client.publish_feed_post(
            message="Check out this breakthrough!",
            link="https://arxiv.org/abs/2401.00001",
        )

        assert response.success is True
        assert response.post_id == "1234567890_987654321"
        assert response.is_simulated is False


@pytest.mark.asyncio
async def test_facebook_client_publish_feed_error_handled(test_fb_settings):
    client = FacebookClient(settings=test_fb_settings)

    from unittest.mock import MagicMock

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "error": {
            "message": "Invalid OAuth access token.",
            "type": "OAuthException",
            "code": 190,
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        response = await client.publish_feed_post(message="Testing error handling")

        assert response.success is False
        assert response.post_id is None
        assert "Invalid OAuth access token" in response.message


@pytest.mark.asyncio
async def test_facebook_service_publish_paper_post(test_fb_settings):
    client = FacebookClient(settings=test_fb_settings)
    service = FacebookService(client=client)

    with patch.object(client, "publish_feed_post") as mock_publish:
        mock_publish.return_value = AsyncMock(
            success=True,
            post_id="post_123",
            url="https://www.facebook.com/post_123",
            is_simulated=False,
            message="Published",
        )

        result = await service.publish_paper_post(
            post_content="Research summary...",
            paper_url="https://arxiv.org/abs/2401.00001",
        )

        assert result.success is True
        mock_publish.assert_called_once()
