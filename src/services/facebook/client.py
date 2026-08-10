import logging
from typing import Any

import httpx
from src.config import FacebookSettings

logger = logging.getLogger(__name__)


class FacebookClient:
    """Client for interacting with the Facebook Graph API to publish posts."""

    def __init__(self, settings: FacebookSettings):
        self.settings = settings

    @property
    def base_url(self) -> str:
        return self.settings.base_url.rstrip("/")

    @property
    def page_id(self) -> str:
        return self.settings.page_id

    @property
    def access_token(self) -> str:
        return self.settings.page_access_token

    @property
    def graph_version(self) -> str:
        return self.settings.graph_api_version

    @property
    def is_configured(self) -> bool:
        return bool(self.page_id and self.access_token and self.settings.enabled)

    async def post_to_page(
        self, message: str, link: str | None = None
    ) -> dict[str, Any]:
        """
        Publish a post to the configured Facebook Page.

        Args:
            message: Text content of the post.
            link: Optional URL to attach to the post.

        Returns:
            Dictionary containing API response (e.g. {"id": "page_id_post_id"}).
        """
        if not self.is_configured:
            raise ValueError(
                "Facebook client is not configured or disabled. "
                "Ensure FACEBOOK__PAGE_ID, FACEBOOK__PAGE_ACCESS_TOKEN, and FACEBOOK__ENABLED=true are set."
            )

        endpoint = f"{self.base_url}/{self.graph_version}/{self.page_id}/feed"
        payload: dict[str, Any] = {
            "message": message,
            "access_token": self.access_token,
        }
        if link:
            payload["link"] = link

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, data=payload)
                response.raise_for_status()
                data = response.json()
                logger.info(f"Successfully posted to Facebook Page: {data.get('id')}")
                return data
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            logger.error(
                f"Facebook Graph API HTTP error: {e.response.status_code} - {error_detail}"
            )
            raise RuntimeError(
                f"Facebook API returned status {e.response.status_code}: {error_detail}"
            ) from e
        except Exception as e:
            logger.error(f"Failed to post to Facebook: {e}")
            raise RuntimeError(f"Error connecting to Facebook API: {e}") from e

    async def health_check(self) -> dict[str, Any]:
        """Check Facebook API integration readiness."""
        if not self.is_configured:
            return {
                "status": "disabled",
                "message": "Facebook settings not configured or disabled.",
            }
        return {
            "status": "healthy",
            "message": f"Facebook client configured for Page ID {self.page_id}",
        }
