from typing import Any

from src.services.facebook.formatter import (
    clean_facebook_post_text,
    is_pure_ascii,
    to_unicode_bold,
)


def extract_message_text(response: Any) -> str:
    """Safely extract plain text from LangChain message response across all LLM providers."""
    content = getattr(response, "content", None)
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

    text_attr = getattr(response, "text", None)
    if isinstance(text_attr, str) and text_attr:
        return text_attr.strip()

    if isinstance(response, str):
        return response.strip()

    return str(content if content is not None else response).strip()


__all__ = [
    "clean_facebook_post_text",
    "extract_message_text",
    "is_pure_ascii",
    "to_unicode_bold",
]
