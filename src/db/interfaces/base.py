from abc import ABC, abstractmethod
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session


class BaseDataBaseInterface(ABC):
    """Base interface for database operations."""

    @abstractmethod
    def startup(self) -> None:
        """Initialize the database connection."""

    @abstractmethod
    def shutdown(self) -> None:
        """Close the database connection."""

    @abstractmethod
    def get_session(self) -> AbstractContextManager[Session]:
        """Get a database session or connection."""
