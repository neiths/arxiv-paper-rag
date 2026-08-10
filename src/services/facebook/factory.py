from src.config import get_settings
from src.services.facebook.client import FacebookClient


def make_facebook_client() -> FacebookClient:
    settings = get_settings()
    return FacebookClient(settings.facebook)
