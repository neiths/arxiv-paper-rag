"""Unified factory for OpenSearch client."""

from functools import lru_cache

from src.config import Settings, get_settings

from .client import OpenSearchClient


@lru_cache(maxsize=1)
def _get_opensearch_client_cached(host: str) -> OpenSearchClient:
    settings = get_settings()
    return OpenSearchClient(host=host, settings=settings)


def make_opensearch_client(settings: Settings | None = None) -> OpenSearchClient:
    """Factory function to create cached OpenSearch client.

    Uses lru_cache by host string to maintain a singleton instance.

    :param settings: Optional settings instance
    :returns: Cached OpenSearchClient instance
    """
    if settings is None:
        settings = get_settings()

    return _get_opensearch_client_cached(settings.opensearch.host)


def make_opensearch_client_fresh(
    settings: Settings | None = None, host: str | None = None
) -> OpenSearchClient:
    """Factory function to create a fresh OpenSearch client (not cached).

    Use this when you need a new client instance (e.g., for testing
    or when connection issues occur).

    :param settings: Optional settings instance
    :param host: Optional host override
    :returns: New OpenSearchClient instance
    """
    if settings is None:
        settings = get_settings()

    # Use provided host or settings host
    opensearch_host = host or settings.opensearch.host

    return OpenSearchClient(host=opensearch_host, settings=settings)
