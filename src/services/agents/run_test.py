import asyncio
import logging
import sys
from pathlib import Path

# Add project root to python path to ensure imports work correctly when run from any folder
project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langchain_core.messages import HumanMessage
from src.config import get_settings
from src.services.agents.agentic_rag import AgenticRAGService
from src.services.agents.context import Context
from src.services.ollama.factory import make_ollama_client
from src.services.opensearch.factory import make_opensearch_client
from src.services.embeddings.factory import make_embeddings_service
from src.services.langfuse.factory import make_langfuse_tracer

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("run_test")


async def main():
    logger.info("Initializing clients and services...")
    settings = get_settings()

    # Initialize clients using their standard factories
    opensearch_client = make_opensearch_client()
    ollama_client = make_ollama_client()
    embeddings_client = make_embeddings_service()
    langfuse_tracer = make_langfuse_tracer()

    logger.info("Initializing AgenticRAGService...")
    agent_service = AgenticRAGService(
        opensearch_client=opensearch_client,
        ollama_client=ollama_client,
        embeddings_client=embeddings_client,
        langfuse_tracer=langfuse_tracer,
    )

    # Define test query
    query = "What are the latest advances in machine learning for medical imaging?"
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])

    # Set up runtime Context
    context = Context(
        ollama_client=ollama_client,
        opensearch_client=opensearch_client,
        embeddings_client=embeddings_client,
        langfuse_tracer=langfuse_tracer,
        langfuse_enabled=False,  # Change to True if Langfuse is configured and running
        model_name=settings.ollama_model or "llama3.2:latest",
    )

    # Initial state for the agentic RAG graph
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "original_query": query,
        "retrieval_attempts": 0,
        "relevant_sources": [],
        "grading_results": [],
        "metadata": {},
    }

    logger.info(f"Running agent with query: '{query}'")

    try:
        # Execute the compiled graph asynchronously, passing the context parameter directly
        result = await agent_service.graph.ainvoke(initial_state, context=context)

        print("\n" + "=" * 40)
        print("=== AGENT EXECUTION RESULT ===")
        print("=" * 40)
        print(f"Original Query:  {result.get('original_query')}")
        print(f"Rewritten Query: {result.get('rewritten_query')}")
        print("-" * 40)
        print("Messages history:")
        for idx, msg in enumerate(result.get("messages", [])):
            print(f"  {idx + 1}. [{type(msg).__name__}]: {msg.content}")
        print("=" * 40 + "\n")

    except Exception as e:
        logger.error(f"Error executing agent: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
