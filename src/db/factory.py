from src.config import get_settings
from src.db.interfaces.base import BaseDataBaseInterface
from src.db.interfaces.postgresql import PostgreSQLDataBase, PostgreSQLSettings


def make_database() -> BaseDataBaseInterface:
    """
    Factory function to create a database instance based on settings.
    Returns:
        BaseDataBaseInterface: An instance of a database interface.
    """
    # Get application settings
    settings = get_settings()

    # Create PostgreSQL configuration from settings
    config = PostgreSQLSettings(
        database_url=settings.postgres_database_url,
        echo_sql=settings.postgres_echo_sql,
        pool_size=settings.postgres_pool_size,
        max_overflow=settings.postgres_max_overflow,
    )

    database = PostgreSQLDataBase(config=config)
    database.startup()

    return database
