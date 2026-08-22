#!/usr/bin/env python3
"""Interactive test script for Agentic RAG Graph and all its nodes.

Usage:
  # Run predefined scenario test suite (in-scope, out-of-scope, borderline):
  python src/services/agents/run_test.py

  # Test a specific custom query:
  python src/services/agents/run_test.py --query "What is the transformer architecture?"

  # Test out-of-scope query:
  python src/services/agents/run_test.py --scenario out_of_scope

  # Interactive mode:
  python src/services/agents/run_test.py --interactive

  # Print graph ASCII structure and Mermaid diagram:
  python src/services/agents/run_test.py --inspect-graph
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

# Add project root to python path
project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langchain_core.messages import HumanMessage
from src.config import get_settings
from src.services.agents.agentic_rag import AgenticRAGService
from src.services.agents.config import GraphConfig
from src.services.agents.context import Context
from src.services.embeddings.factory import make_embeddings_service
from src.services.langfuse.factory import make_langfuse_tracer
from src.services.ollama.factory import make_ollama_client
from src.services.opensearch.factory import make_opensearch_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_test")

# Silence noisy third-party loggers during testing
for logger_name in ["httpcore", "httpx", "urllib3", "opensearch"]:
    logging.getLogger(logger_name).setLevel(logging.WARNING)


TEST_SCENARIOS = {
    "in_scope": {
        "title": "1. In-Scope CS/AI Research Query",
        "description": "Tests: Guardrail (Pass) -> Retrieve -> Grade -> Generate Answer",
        "query": "What are the latest advances in transformer architectures and self-attention mechanisms?",
    },
    "out_of_scope": {
        "title": "2. Out-of-Scope Non-Research Query",
        "description": "Tests: Guardrail (Fail) -> Out-of-Scope Node -> END (No retrieval)",
        "query": "How do I bake a chocolate cake at home?",
    },
    "vague_query": {
        "title": "3. Vague / Short Research Query",
        "description": "Tests: Guardrail (Pass) -> Retrieve -> Rewrite Query (if needed) -> Answer",
        "query": "fast vision models",
    },
}


def print_banner(title: str, subtitle: str = ""):
    """Print formatted section header."""
    width = 75
    print("\n" + "=" * width)
    print(f"  {title}")
    if subtitle:
        print(f"  {subtitle}")
    print("=" * width)


def print_result_summary(result: dict, raw_graph_result: dict | None = None):
    """Print structured summary of graph execution."""
    print("\n" + "-" * 75)
    print("                      AGENT EXECUTION SUMMARY")
    print("-" * 75)

    # 1. Query info
    print(f"📝 Original Query : {result.get('query')}")
    if result.get("rewritten_query"):
        print(f"🔄 Rewritten Query: {result.get('rewritten_query')}")

    # 2. Guardrail
    guardrail_score = result.get("guardrail_score")
    if guardrail_score is not None:
        status_icon = "✓" if guardrail_score >= 60 else "✗"
        print(f"🛡️  Guardrail Score : {guardrail_score}/100 [{status_icon}]")

    # 3. Retrieval & Grading
    print(f"🔎 Retrieval Try  : {result.get('retrieval_attempts', 0)} attempt(s)")
    sources = result.get("sources", [])
    print(f"📚 Sources Found  : {len(sources)}")
    for idx, src in enumerate(sources, 1):
        arxiv_id = src.get("arxiv_id", "N/A")
        title = src.get("title", "Unknown Title")
        score = src.get("relevance_score", 0.0)
        print(f"   [{idx}] arXiv:{arxiv_id} (Score: {score:.3f}) - {title[:60]}...")

    # 4. Reasoning Steps
    steps = result.get("reasoning_steps", [])
    if steps:
        print(f"🧠 Reasoning Flow : {' -> '.join(steps)}")

    # 5. Timing
    exec_time = result.get("execution_time", 0.0)
    print(f"⏱️  Execution Time : {exec_time:.2f}s")

    # 6. Final Output / Answer
    print("-" * 75)
    print("📄 FINAL RESPONSE:")
    print("-" * 75)
    print(result.get("answer", "No answer."))
    print("=" * 75 + "\n")


async def run_single_query(
    agent_service: AgenticRAGService, query: str, user_id: str = "test_user"
):
    """Execute a single query through the AgenticRAGService and print results."""
    logger.info(f"Executing query: '{query}'")
    try:
        result = await agent_service.ask(query=query, user_id=user_id)
        print_result_summary(result)
        return result
    except Exception as e:
        logger.error(f"Execution failed for query '{query}': {e}", exc_info=True)
        return None


async def run_interactive_mode(agent_service: AgenticRAGService):
    """Run an interactive CLI session where user can input queries."""
    print_banner("INTERACTIVE AGENTIC RAG CLI", "Type 'exit', 'quit', or 'q' to end.")

    while True:
        try:
            query = input("\n👉 Enter your question: ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                print("\nGoodbye!\n")
                break

            await run_single_query(agent_service, query)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting interactive mode...")
            break


def inspect_graph(agent_service: AgenticRAGService):
    """Print graph representation (ASCII / Mermaid)."""
    print_banner("LANGGRAPH WORKFLOW GRAPH INSPECTION")
    try:
        mermaid_syntax = agent_service.get_graph_mermaid()
        print("\n--- MERMAID DIAGRAM ---")
        print(mermaid_syntax)
    except Exception as e:
        logger.warning(f"Could not generate Mermaid diagram: {e}")

    try:
        ascii_graph = agent_service.get_graph_ascii()
        print("\n--- ASCII GRAPH ---")
        print(ascii_graph)
    except Exception as e:
        logger.warning(f"Could not generate ASCII graph: {e}")


async def main():
    parser = argparse.ArgumentParser(
        description="Agentic RAG Test Script for testing graphs, nodes, and guardrails."
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        help="Run a specific custom question through the agent.",
    )
    parser.add_argument(
        "--scenario",
        "-s",
        type=str,
        choices=["all", "in_scope", "out_of_scope", "vague_query"],
        default="all",
        help="Run a specific scenario or all predefined scenarios (default: all).",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Start an interactive session to test custom queries one by one.",
    )
    parser.add_argument(
        "--inspect-graph",
        action="store_true",
        help="Inspect the compiled LangGraph structure (Mermaid and ASCII).",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Override LLM model name (e.g., 'llama3.2:1b').",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=int,
        default=60,
        help="Guardrail threshold (0-100, default: 60).",
    )
    parser.add_argument(
        "--top-k",
        "-k",
        type=int,
        default=3,
        help="Number of chunks to retrieve (default: 3).",
    )
    parser.add_argument(
        "--tracing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable/disable Langfuse tracing (default: True).",
    )

    args = parser.parse_args()

    settings = get_settings()
    model_name = args.model or settings.ollama_model or "llama3.2:1b"

    print_banner(
        "INITIALIZING AGENTIC RAG SYSTEM",
        f"Model: {model_name} | Top-k: {args.top_k} | Guardrail Threshold: {args.threshold}",
    )

    # Initialize backend services
    opensearch_client = make_opensearch_client()
    ollama_client = make_ollama_client()
    embeddings_client = make_embeddings_service()
    langfuse_tracer = make_langfuse_tracer() if args.tracing else None

    # Graph configuration
    graph_config = GraphConfig(
        model=model_name,
        top_k=args.top_k,
        guardrail_threshold=args.threshold,
        enable_tracing=args.tracing,
    )

    # Initialize service
    agent_service = AgenticRAGService(
        opensearch_client=opensearch_client,
        ollama_client=ollama_client,
        embeddings_client=embeddings_client,
        langfuse_tracer=langfuse_tracer,
        graph_config=graph_config,
    )

    # Option 1: Graph inspection
    if args.inspect_graph:
        inspect_graph(agent_service)
        return

    # Option 2: Interactive mode
    if args.interactive:
        await run_interactive_mode(agent_service)
        return

    # Option 3: Single custom query
    if args.query:
        print_banner("RUNNING CUSTOM QUERY TEST")
        await run_single_query(agent_service, args.query)
        return

    # Option 4: Predefined scenarios
    scenarios_to_run = (
        TEST_SCENARIOS.keys() if args.scenario == "all" else [args.scenario]
    )

    print_banner(
        "RUNNING AGENTIC RAG TEST SUITE", f"Scenarios: {list(scenarios_to_run)}"
    )

    for scenario_key in scenarios_to_run:
        scenario = TEST_SCENARIOS[scenario_key]
        print_banner(scenario["title"], scenario["description"])
        await run_single_query(agent_service, scenario["query"])
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
