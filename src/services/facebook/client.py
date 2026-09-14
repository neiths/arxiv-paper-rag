import logging
import time
from pathlib import Path
from typing import Any

import httpx
from src.config import FacebookSettings

from .models import FacebookPageInfo, FacebookPostResponse

logger = logging.getLogger(__name__)


class FacebookClient:
    """Asynchronous client for interacting with Meta Facebook Graph API."""

    def __init__(self, settings: FacebookSettings):
        self.settings = settings
        self.base_url = settings.base_url.rstrip("/")
        self.api_version = settings.graph_api_version
        self.page_id = settings.page_id
        self.access_token = settings.page_access_token
        self.enabled = settings.enabled
        self.dry_run = settings.dry_run

    @property
    def is_configured(self) -> bool:
        """Check whether credentials and page ID are provided."""
        return bool(self.page_id and self.access_token)

    async def get_page_info(self) -> FacebookPageInfo:
        """Verify token and fetch Facebook Page metadata."""
        if not self.is_configured or self.dry_run:
            return FacebookPageInfo(
                page_id=self.page_id or "mock_page_id",
                name="[Dry-Run / Unconfigured Mode]",
                is_valid=False,
                error=(
                    "Credentials missing or dry-run enabled"
                    if not self.is_configured
                    else None
                ),
            )

        url = f"{self.base_url}/{self.api_version}/{self.page_id}"
        params = {
            "fields": "id,name",
            "access_token": self.access_token,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                data = response.json()

                if response.status_code == 200:
                    return FacebookPageInfo(
                        page_id=data.get("id", self.page_id),
                        name=data.get("name", "Unknown Page"),
                        is_valid=True,
                    )
                else:
                    error_msg = data.get("error", {}).get("message", response.text)
                    logger.error(
                        f"Facebook Graph API Error ({response.status_code}): {error_msg}"
                    )
                    return FacebookPageInfo(
                        page_id=self.page_id,
                        name="",
                        is_valid=False,
                        error=error_msg,
                    )
        except Exception as e:
            logger.error(f"Failed to query Facebook Page info: {e}")
            return FacebookPageInfo(
                page_id=self.page_id,
                name="",
                is_valid=False,
                error=str(e),
            )

    async def publish_feed_post(
        self,
        message: str,
        link: str | None = None,
    ) -> FacebookPostResponse:
        """Publish a text/link post to the Facebook Page feed.

        :param message: Main text of the post.
        :param link: Optional URL attachment (e.g. arXiv link).
        :returns: FacebookPostResponse with post ID and status.
        """
        if self.dry_run or not self.is_configured:
            simulated_id = f"simulated_{self.page_id or 'page'}_{int(time.time())}"
            logger.warning(
                f"[Facebook Dry-Run] Not posting live to Facebook (configured={self.is_configured}, dry_run={self.dry_run}). "
                f"Simulated Post ID: {simulated_id}\nPost preview:\n{message[:200]}..."
            )
            return FacebookPostResponse(
                success=True,
                post_id=simulated_id,
                url=f"https://www.facebook.com/{simulated_id}",
                is_simulated=True,
                message="Post generated successfully in dry-run/unconfigured mode.",
                raw_response={"id": simulated_id, "simulated": True},
            )

        url = f"{self.base_url}/{self.api_version}/{self.page_id}/feed"
        payload: dict[str, Any] = {
            "message": message,
            "access_token": self.access_token,
        }
        if link:
            payload["link"] = link

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, data=payload)
                data = response.json()

                if response.status_code in (200, 201) and "id" in data:
                    post_id = data["id"]
                    post_url = f"https://www.facebook.com/{post_id}"
                    logger.info(f"Successfully published post to Facebook: {post_id}")
                    return FacebookPostResponse(
                        success=True,
                        post_id=post_id,
                        url=post_url,
                        is_simulated=False,
                        message="Post published successfully to Facebook Page.",
                        raw_response=data,
                    )
                else:
                    error_obj = data.get("error", {})
                    error_msg = error_obj.get("message", response.text)
                    error_code = error_obj.get("code")
                    logger.error(
                        f"Failed to publish post to Facebook (Code {error_code}): {error_msg}"
                    )
                    return FacebookPostResponse(
                        success=False,
                        post_id=None,
                        is_simulated=False,
                        message=f"Facebook API error ({error_code}): {error_msg}",
                        raw_response=data,
                    )
        except Exception as e:
            logger.error(f"Unexpected error publishing to Facebook: {e}")
            return FacebookPostResponse(
                success=False,
                post_id=None,
                is_simulated=False,
                message=f"Exception connecting to Facebook Graph API: {e!s}",
            )

    async def publish_photo(
        self,
        caption: str,
        image_url: str | None = None,
        image_path: str | None = None,
    ) -> FacebookPostResponse:
        """Publish a photo post to the Facebook Page.

        :param caption: Caption text for the photo.
        :param image_url: Optional public URL to the image.
        :param image_path: Optional local file path to the image.
        :returns: FacebookPostResponse.
        """
        if self.dry_run or not self.is_configured:
            simulated_id = (
                f"simulated_photo_{self.page_id or 'page'}_{int(time.time())}"
            )
            logger.warning(
                f"[Facebook Dry-Run] Not posting photo live to Facebook. Simulated Photo ID: {simulated_id}"
            )
            return FacebookPostResponse(
                success=True,
                post_id=simulated_id,
                url=f"https://www.facebook.com/{simulated_id}",
                is_simulated=True,
                message="Photo post simulated successfully.",
                raw_response={"id": simulated_id, "simulated": True},
            )

        url = f"{self.base_url}/{self.api_version}/{self.page_id}/photos"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                if image_path and Path(image_path).exists():
                    with open(image_path, "rb") as f:
                        files = {"source": (Path(image_path).name, f, "image/jpeg")}
                        data = {"caption": caption, "access_token": self.access_token}
                        response = await client.post(url, data=data, files=files)
                elif image_url:
                    data = {
                        "caption": caption,
                        "url": image_url,
                        "access_token": self.access_token,
                    }
                    response = await client.post(url, data=data)
                else:
                    return FacebookPostResponse(
                        success=False,
                        message="Neither image_url nor valid image_path was provided.",
                    )

                res_data = response.json()
                if response.status_code in (200, 201) and "id" in res_data:
                    post_id = res_data.get("post_id", res_data["id"])
                    return FacebookPostResponse(
                        success=True,
                        post_id=post_id,
                        url=f"https://www.facebook.com/{post_id}",
                        is_simulated=False,
                        message="Photo post published successfully to Facebook Page.",
                        raw_response=res_data,
                    )
                else:
                    error_msg = res_data.get("error", {}).get("message", response.text)
                    return FacebookPostResponse(
                        success=False,
                        message=f"Facebook photo upload failed: {error_msg}",
                        raw_response=res_data,
                    )
        except Exception as e:
            logger.error(f"Error publishing photo to Facebook: {e}")
            return FacebookPostResponse(
                success=False,
                message=f"Exception publishing photo: {e!s}",
            )
