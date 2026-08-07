import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from src.config import get_settings
from src.db.factory import make_database
from src.services.arxiv.factory import make_arxiv_client
from src.services.embeddings.factory import make_embeddings_client
from src.services.opensearch.factory import make_opensearch_client
from src.services.pdf_parser.factory import make_pdf_parser_service
from src.services.ollama.client import OllamaClient
from src.services.cache.client import CacheClient
from src.routers import ask
from src.routers import hybrid_search, ping

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

    # Initialize shared service clients used by request dependencies.
    app.state.opensearch_client = make_opensearch_client(settings)
    app.state.arxiv_client = make_arxiv_client()
    app.state.pdf_parser = make_pdf_parser_service()
    app.state.embeddings_service = make_embeddings_client(settings)
    app.state.ollama_client = OllamaClient(settings)

    # Redis cache is optional; keep the app running even if Redis is unavailable.
    try:
        import redis

        redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
            password=settings.redis.password or None,
            decode_responses=settings.redis.decode_responses,
            socket_timeout=settings.redis.socket_timeout,
            socket_connect_timeout=settings.redis.socket_connect_timeout,
        )
        app.state.cache_client = CacheClient(redis_client, settings.redis)
    except Exception as exc:
        logger.warning(f"Cache client unavailable: {exc}")

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


app.include_router(ask.ask_router, prefix="/ask", tags=["ask"])
app.include_router(ask.stream_router, prefix="/stream", tags=["stream"])
app.include_router(hybrid_search.router)
app.include_router(ping.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=8000, host="0.0.0.0")
