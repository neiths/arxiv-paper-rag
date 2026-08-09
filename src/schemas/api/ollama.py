"""API schemas for Ollama management endpoints."""

from typing import Any
from pydantic import BaseModel, Field


class PullModelRequest(BaseModel):
    """Request schema for pulling a model."""

    name: str = Field(
        ...,
        description="Name of the model to pull (e.g. 'llama3.2:latest')",
        example="llama3.2:latest",
    )


class GeneratePromptRequest(BaseModel):
    """Request schema for direct text generation."""

    model: str = Field(
        default="llama3.2:latest",
        description="Model name to use for generation",
        example="llama3.2:latest",
    )
    prompt: str = Field(
        ...,
        description="Prompt text for generation",
        example="Why is the sky blue?",
    )
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Sampling temperature"
    )
    top_p: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Nucleus sampling top_p"
    )


class ModelDetailResponse(BaseModel):
    """Response schema for model information."""

    name: str
    modified_at: str | None = None
    size: int | None = None
    digest: str | None = None
    details: dict[str, Any] | None = None
