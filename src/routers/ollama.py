"""FastAPI router for Ollama model management and text generation."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from ..dependencies import OllamaDep
from ..schemas.api.ollama import (
    GeneratePromptRequest,
    ModelDetailResponse,
    PullModelRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ollama", tags=["Ollama"])


@router.get(
    "/models",
    response_model=list[dict[str, Any]],
    summary="List available local Ollama models",
)
async def list_models(ollama_client: OllamaDep) -> list[dict[str, Any]]:
    """List all LLM models currently downloaded and available in Ollama."""
    try:
        return await ollama_client.list_models()
    except Exception as e:
        logger.error(f"Failed to list Ollama models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}",
        ) from e


@router.post(
    "/models/pull",
    summary="Pull a model from Ollama library",
)
async def pull_model(
    request: PullModelRequest, ollama_client: OllamaDep
) -> dict[str, Any]:
    """Download/pull an LLM model from the Ollama registry (e.g. 'llama3.2:latest', 'mistral', 'qwen2.5')."""
    try:
        logger.info(f"Received request to pull model '{request.name}'")
        result = await ollama_client.pull_model(name=request.name, stream=False)
        return result
    except Exception as e:
        logger.error(f"Failed to pull model '{request.name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pull model '{request.name}': {str(e)}",
        ) from e


@router.get(
    "/models/{model_name:path}",
    summary="Get details of a specific Ollama model",
)
async def show_model(model_name: str, ollama_client: OllamaDep) -> dict[str, Any]:
    """Get metadata and detail configuration of a specific model."""
    try:
        return await ollama_client.show_model(name=model_name)
    except Exception as e:
        logger.error(f"Failed to get model info for '{model_name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found or error occurred: {str(e)}",
        ) from e


@router.delete(
    "/models/{model_name:path}",
    summary="Delete a local Ollama model",
)
async def delete_model(model_name: str, ollama_client: OllamaDep) -> dict[str, Any]:
    """Delete a downloaded model from local storage."""
    try:
        return await ollama_client.delete_model(name=model_name)
    except Exception as e:
        logger.error(f"Failed to delete model '{model_name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete model '{model_name}': {str(e)}",
        ) from e


@router.post(
    "/generate",
    summary="Generate text completion using an Ollama model",
)
async def generate(
    request: GeneratePromptRequest, ollama_client: OllamaDep
) -> dict[str, Any]:
    """Directly generate text using a prompt and chosen model."""
    try:
        response = await ollama_client.generate(
            model=request.model,
            prompt=request.prompt,
            stream=False,
            options={
                "temperature": request.temperature,
                "top_p": request.top_p,
            },
        )
        if not response:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Empty response returned from Ollama",
            )
        return response
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text generation failed: {str(e)}",
        ) from e
