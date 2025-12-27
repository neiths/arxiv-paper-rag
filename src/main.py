import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from src.config import get_settings
from src.db.factory import make_database
from src.routers import ask, papers


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up the application...")
    
    settings = get_settings()
    app.state.settings = settings

    database = make_database()
    app.state.database = database
    logger.info("Database connected")
    
    logger.info("API is ready to serve requests.")
    yield
    
    database.shutdown()
    logger.info("Database connection closed.")
    
    
app = FastAPI(
    title="RAG API",
    description="API for Retrieval-Augmented Generation (RAG) system",
    version=os.getenv("RAG_API_VERSION", "0.1.0"),
    lifespan=lifespan,
)


app.include_router(ask.router, prefix="/ask", tags=["ask"])
app.include_router(papers.router)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(app, port=8000, host="0.0.0.0")