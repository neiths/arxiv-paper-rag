from typing import Any

from src.services.facebook.formatter import (
    clean_facebook_post_text,
    is_pure_ascii,
    to_unicode_bold,
)


def extract_message_text(response: Any) -> str:
    """Safely extract plain text from LangChain message response across all LLM providers."""
    if hasattr(response, "text") and response.text:
        return str(response.text).strip()

    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "".join(parts).strip()

    return str(content).strip()


__all__ = [
    "clean_facebook_post_text",
    "extract_message_text",
    "is_pure_ascii",
    "to_unicode_bold",
]
