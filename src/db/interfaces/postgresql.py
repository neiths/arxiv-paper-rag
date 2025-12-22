import logging
from contextlib import contextmanager
from typing import Optional, Generator

from pydantic import Field
from pydantic_settings import BaseSettings
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from sqlalchemy.engine import Engine
from sqlalchemy import create_engine, text, inspect

from src.db.interfaces.base import BaseDataBaseInferface

logger = logging.getLogger(__name__)


class PostgreSQLSettings(BaseSettings):
    """PostgreSQL configuration settings."""

    database_url: str = Field(
        default="postgresql+psycopg2://rag_user:rag_password@postgres:5432/rag_db",
        description="PostgreSQL database URL",
    )
    echo_sql: bool = Field(
        default=False,
        description="Enable SQL query logging",
    )
    pool_size: int = Field(
        default=20,
        description="Database connection pool size",
    )
    max_overflow: int = Field(default=0, description="Max overflow connections")

    class Config:
        env_prefix = "POSTGRES_"


# use declarative_base to create a base class for models
Base = declarative_base()


class PostgreSQLDataBase(BaseDataBaseInferface):
    """PostgreSQL database implementation."""

    def __init__(self, config: PostgreSQLSettings):
        self.config = config
        self.engine = Optional[Engine] = None
        self.session_factory = Optional[sessionmaker] = None

    def startup(self) -> None:
        """Initialize the PostgreSQL database connection."""
        try:
            # log connection attempt
            logger.info(
                f"Attempting to connect to PostgreSQL at: {self.config.database_url.split('@')[1] if '@' in self.config.database_url else 'localhost'}"
            )

            self.engine = create_engine(
                self.config.database_url,
                echo=self.config.echo_sql,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
            )

            self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

            # Test the connection
            assert self.engine is not None
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info(
                    "Database connection test successful."
                )

            # Check which tables exist before creating
            inspector = inspect(self.engine)
            existing_tables = inspector.get_table_names()

            # Create tables if they do not exist (idempotent operation)
            Base.metadata.create_all(bind=self.engine)

            # check if  any new tables were created
            updated_tables = inspector.get_table_names()
            new_tables = set(updated_tables) - set(existing_tables)

            if new_tables:
                logger.info(
                    f"Created new tables: {', '.join(new_tables)}"
                )
            else:
                logger.info(
                    "All tables already exist. No new tables were created."
                )

            logger.info("PostgreSQL database initialized successfully.")
            assert self.engine is not None

            logger.info(f"Database: {self.engine.url.database}")
            logger.info(f"Total tables: {', '.join(updated_tables) if updated_tables else 'None'}")
            logger.info("Database connection established successfully.")

        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL database: {e}")
            raise

    def shutdown(self) -> None:
        """Close the PostgreSQL database connection."""
        if self.engine:
            self.engine.dispose()
            logger.info("PostgreSQL database connection closed.")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a PostgreSQL database session."""
        if not self.session_factory:
            raise RuntimeError("Database session factory is not initialized.")

        session: Session = self.session_factory()
        try:
            yield session

        except Exception as e:
            session.rollback()
            logger.error(f"Session rollback due to error: {e}")
            raise
        finally:
            session.close()
