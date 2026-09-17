import logging

from .client import FacebookClient
from .models import FacebookPageInfo, FacebookPostResponse

logger = logging.getLogger(__name__)


class FacebookService:
    """High-level service managing Facebook publishing workflow."""

    def __init__(self, client: FacebookClient):
        self.client = client

    @property
    def is_enabled(self) -> bool:
        return self.client.enabled

    @property
    def is_configured(self) -> bool:
        return self.client.is_configured

    async def verify_connection(self) -> FacebookPageInfo:
        """Verify API token and page connectivity."""
        return await self.client.get_page_info()

    async def publish_paper_post(
        self,
        post_content: str,
        paper_url: str | None = None,
        image_path: str | None = None,
    ) -> FacebookPostResponse:
        """Publish a formatted paper research post to Facebook.

        :param post_content: Text formatted for Facebook audience.
        :param paper_url: Optional arXiv link.
        :param image_path: Optional path to a figure or banner image.
        :returns: FacebookPostResponse.
        """
        if not post_content or not post_content.strip():
            return FacebookPostResponse(
                success=False,
                message="Post content cannot be empty.",
            )

        clean_text = post_content.strip()

        # If an image is provided and exists, publish as photo post
        if image_path:
            logger.info(f"Publishing photo post with image: {image_path}")
            return await self.client.publish_photo(
                caption=clean_text, image_path=image_path
            )

        # Otherwise publish standard feed post with paper link
        logger.info(f"Publishing feed post with link: {paper_url}")
        return await self.client.publish_feed_post(message=clean_text, link=paper_url)
