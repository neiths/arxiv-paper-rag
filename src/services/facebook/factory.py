from src.config import FacebookSettings, Settings

from .client import FacebookClient
from .service import FacebookService


def make_facebook_client(settings: FacebookSettings) -> FacebookClient:
    """Factory to create FacebookClient instance."""
    return FacebookClient(settings=settings)


def make_facebook_service(settings: Settings) -> FacebookService:
    """Factory to create FacebookService instance."""
    client = make_facebook_client(settings.facebook)
    return FacebookService(client=client)
