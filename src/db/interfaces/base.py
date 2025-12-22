from abc import ABC, abstractmethod
from typing import Any, ContextManager, Dict, List, Optional

from sqlalchemy.orm import Session

class BaseDataBaseInferface(ABC):
    """Base interface for database operations."""
    
    @abstractmethod
    def startup(self) -> None:
        """Initialize the database connection."""
        
    @abstractmethod
    def shutdown(self) -> None:
        """Close the database connection."""
        
    @abstractmethod
    def get_session(self) -> ContextManager[Session]:
        """Get a database session or connection."""
        