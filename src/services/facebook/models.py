from typing import Any

from pydantic import BaseModel, Field


class FacebookPostRequest(BaseModel):
    """Request model for publishing a Facebook feed post."""

    message: str = Field(..., min_length=1, description="Post text content")
    link: str | None = Field(
        None, description="Optional URL to attach (e.g. arXiv link)"
    )


class FacebookPhotoPostRequest(BaseModel):
    """Request model for publishing a Facebook photo post."""

    caption: str = Field(..., description="Photo caption / post text")
    image_url: str | None = Field(None, description="Public URL to the image")
    image_path: str | None = Field(None, description="Local path to image file")


class FacebookPostResponse(BaseModel):
    """Response model after publishing to Facebook."""

    success: bool
    post_id: str | None = None
    url: str | None = None
    is_simulated: bool = False
    message: str = ""
    raw_response: dict[str, Any] = Field(default_factory=dict)


class FacebookPageInfo(BaseModel):
    """Information about the connected Facebook Page."""

    page_id: str
    name: str = ""
    is_valid: bool = False
    error: str | None = None
