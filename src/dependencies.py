from functools import lru_cache
from typing import Annotated, Generator

from fastapi import Depends, Request

from sqlalchemy.orm import Session
from src.config import Settings
from src.db.interfaces.base import BaseDataBaseInterface


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_request_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> BaseDataBaseInterface:
    return request.app.state.database


def get_db_session(database: Annotated[BaseDataBaseInterface, Depends(get_database)]) -> Generator[Session, None, None]:
    """Get database session dependency."""
    with database.get_session() as session:
        yield session


# def get_opensearch_service(request: Request) -> OpenSearchService:
#     return getattr(request.app.state, "opensearch_service", None)


# Dependency type aliases for better type hints
SettingsDep = Annotated[Settings, Depends(get_request_settings)]
DatabaseDep = Annotated[BaseDataBaseInterface, Depends(get_database)]
DBSessionDep = Annotated[Generator[Session, None, None], Depends(get_db_session)]
# OpenSearchServiceDep = Annotated[OpenSearchService, Depends(get_opensearch_service)]