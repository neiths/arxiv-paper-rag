import asyncio
import logging
import signal
import sys
from pathlib import Path

# Ensure project root is in sys.path when running as a direct script
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.services.cache.factory import make_cache_client
from src.services.embeddings.factory import make_embeddings_service
from src.services.langfuse.factory import make_langfuse_tracer
from src.services.ollama.factory import make_ollama_client
from src.services.opensearch.factory import make_opensearch_client
from src.services.telegram.factory import make_telegram_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("telegram_runner")


async def run_bot() -> None:
    """Initialize dependencies and run Telegram bot service."""
    settings = get_settings()
    logger.info("Initializing dependencies for Telegram Bot...")

    if not settings.telegram.enabled:
        logger.error(
            "Telegram bot is disabled in configuration. "
            "Set TELEGRAM__ENABLED=true in your environment or .env file."
        )
        sys.exit(1)

    if not settings.telegram.bot_token:
        logger.error(
            "Telegram bot token is not configured. "
            "Set TELEGRAM__BOT_TOKEN=<your_token> in your environment or .env file."
        )
        sys.exit(1)

    # Initialize external clients and services
    opensearch_client = make_opensearch_client()
    if not opensearch_client.health_check():
        logger.warning("OpenSearch connection failed - search features may be limited.")
    else:
        logger.info("OpenSearch connected successfully.")

    embeddings_client = make_embeddings_service()
    ollama_client = make_ollama_client()

    # Optional cache service
    cache_client = None
    try:
        cache_client = make_cache_client(settings)
    except Exception as e:
        logger.warning(
            f"Redis cache client unavailable ({e}); proceeding without cache."
        )

    # Optional Langfuse tracer
    langfuse_tracer = None
    try:
        langfuse_tracer = make_langfuse_tracer()
    except Exception as e:
        logger.warning(
            f"Langfuse tracer initialization failed ({e}); proceeding without tracing."
        )

    bot = make_telegram_service(
        opensearch_client=opensearch_client,
        embeddings_client=embeddings_client,
        ollama_client=ollama_client,
        cache_client=cache_client,
        langfuse_tracer=langfuse_tracer,
    )

    if not bot:
        logger.error("Failed to create TelegramBot instance.")
        sys.exit(1)

    # Start polling
    try:
        await bot.start()
    except Exception as e:
        logger.error(
            f"Failed to connect Telegram Bot: {e}. "
            "Please ensure TELEGRAM__BOT_TOKEN is a valid token from @BotFather."
        )
        if langfuse_tracer:
            langfuse_tracer.shutdown()
        sys.exit(1)

    logger.info(
        "Telegram Bot is running and polling for updates. Press Ctrl+C to stop."
    )

    # Setup signal handlers for graceful termination
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError):
            # Signal handling fallback (e.g. non-Unix platforms)
            pass

    try:
        await stop_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logger.info("Stopping Telegram Bot...")
        await bot.stop()
        if langfuse_tracer:
            langfuse_tracer.shutdown()
        logger.info("Telegram Bot stopped gracefully.")


def main() -> None:
    """Entrypoint function."""
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
