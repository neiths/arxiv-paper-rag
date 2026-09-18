import logging
import os

from langchain_core.language_models import BaseChatModel
from src.config import Settings
from src.services.ollama.client import OllamaClient

logger = logging.getLogger(__name__)


def get_agent_llm(
    settings: Settings,
    model_name: str | None = None,
    temperature: float = 0.2,
    ollama_client: OllamaClient | None = None,
) -> BaseChatModel:
    """Create a LangChain chat model based on requested model name and configuration.

    Supports:
    - Ollama models (default, e.g. "llama3.2:latest", "qwen2.5:7b", "deepseek-r1")
    - Google Gemini (e.g. "gemini-1.5-flash", "gemini-2.0-flash" if langchain_google_genai is available)
    - OpenAI (e.g. "gpt-4o", "gpt-4o-mini" if langchain_openai is available)

    :param settings: Application settings
    :param model_name: Name of model to instantiate
    :param temperature: Sampling temperature
    :param ollama_client: Optional existing OllamaClient instance
    :returns: BaseChatModel instance
    """
    gemini_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    openai_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")

    # If user didn't specify a model, prioritize configured cloud API keys over local Ollama
    if not model_name or model_name == settings.ollama_model:
        if gemini_key:
            effective_model = "gemini-3.5-flash"
        elif openai_key:
            effective_model = "gpt-4o-mini"
        else:
            effective_model = settings.ollama_model
    else:
        effective_model = model_name

    # Check for Gemini models
    if effective_model.lower().startswith("gemini") or (
        gemini_key and "gemini" in effective_model.lower()
    ):
        # Map legacy/common model aliases to active, reliable Gemini models
        model_aliases = {
            "gemini": "gemini-3.5-flash",
            "gemini-1.5-flash": "gemini-3.5-flash",
            "gemini-2.0-flash": "gemini-3.5-flash",
            "gemini-2.5-flash": "gemini-3.5-flash",
            "gemini-3.6-flash": "gemini-3.5-flash",
            "gemini-3.7-flash": "gemini-3.5-flash",
            "gemini-flash": "gemini-3.5-flash",
            "gemini-flash-lite": "gemini-3.5-flash-lite",
            "gemini-latest": "gemini-flash-latest",
        }
        resolved_gemini_model = model_aliases.get(
            effective_model.lower(), effective_model
        )

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            logger.info(f"Using Google GenAI model: {resolved_gemini_model}")
            return ChatGoogleGenerativeAI(
                model=resolved_gemini_model,
                temperature=temperature,
                google_api_key=gemini_key,
            )
        except ImportError:
            logger.warning(
                "langchain_google_genai is not installed. Falling back to Ollama."
            )
        except Exception as e:
            logger.warning(
                f"Failed to initialize ChatGoogleGenerativeAI ({e}). Falling back to Ollama."
            )

    # Check for OpenAI models
    if effective_model.lower().startswith(("gpt-", "o1", "o3")) or (
        settings.openai_api_key and "gpt" in effective_model.lower()
    ):
        try:
            from langchain_openai import ChatOpenAI

            api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
            logger.info(f"Using OpenAI model: {effective_model}")
            return ChatOpenAI(
                model=effective_model,
                temperature=temperature,
                api_key=api_key,
            )
        except ImportError:
            logger.warning("langchain_openai is not installed. Falling back to Ollama.")
        except Exception as e:
            logger.warning(
                f"Failed to initialize ChatOpenAI ({e}). Falling back to Ollama."
            )

    # Default to Ollama local LLM
    logger.info(f"Using Ollama local LLM: {effective_model} at {settings.ollama_host}")
    if ollama_client:
        return ollama_client.get_langchain_model(
            model=effective_model, temperature=temperature
        )

    from langchain_ollama import ChatOllama

    return ChatOllama(
        base_url=settings.ollama_host,
        model=effective_model,
        temperature=temperature,
    )
