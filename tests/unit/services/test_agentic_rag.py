"""Unit tests for AgenticRAGService and LangGraph agent workflow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from src.services.agents.agentic_rag import AgenticRAGService
from src.services.agents.config import GraphConfig
from src.services.agents.factory import make_agentic_rag_service
from src.services.agents.models import GradingResult, GuardrailScoring, SourceItem


@pytest.fixture
def mock_clients():
    """Create mock clients for AgenticRAGService initialization."""
    opensearch_client = MagicMock()
    ollama_client = MagicMock()
    embeddings_client = MagicMock()
    langfuse_tracer = MagicMock()
    langfuse_tracer.client = None

    return {
        "opensearch_client": opensearch_client,
        "ollama_client": ollama_client,
        "embeddings_client": embeddings_client,
        "langfuse_tracer": langfuse_tracer,
    }


@pytest.fixture
def agent_service(mock_clients):
    """Instantiate AgenticRAGService with mock clients."""
    return AgenticRAGService(
        opensearch_client=mock_clients["opensearch_client"],
        ollama_client=mock_clients["ollama_client"],
        embeddings_client=mock_clients["embeddings_client"],
        langfuse_tracer=mock_clients["langfuse_tracer"],
        graph_config=GraphConfig(
            model="llama3.2:1b",
            top_k=3,
            guardrail_threshold=60,
        ),
    )


class TestAgenticRAGService:
    """Test suite for AgenticRAGService methods and workflow execution."""

    def test_initialization_and_compilation(self, agent_service):
        assert agent_service.graph is not None
        assert agent_service.graph_config.guardrail_threshold == 60

    def test_factory_function(self, mock_clients):
        service = make_agentic_rag_service(
            opensearch_client=mock_clients["opensearch_client"],
            ollama_client=mock_clients["ollama_client"],
            embeddings_client=mock_clients["embeddings_client"],
            langfuse_tracer=mock_clients["langfuse_tracer"],
            top_k=5,
            use_hybrid=False,
        )
        assert isinstance(service, AgenticRAGService)
        assert service.graph_config.top_k == 5
        assert service.graph_config.use_hybrid is False

    @pytest.mark.asyncio
    async def test_ask_empty_query_raises_value_error(self, agent_service):
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await agent_service.ask(query="   ")

    @pytest.mark.asyncio
    async def test_ask_successful_workflow_run(self, agent_service):
        mock_result = {
            "messages": [
                HumanMessage(content="What are transformers?"),
                AIMessage(content="Transformers are attention-based models."),
            ],
            "guardrail_result": GuardrailScoring(score=90, reason="CS research topic"),
            "routing_decision": "generate_answer",
            "relevant_sources": [
                SourceItem(
                    arxiv_id="1706.03762",
                    title="Attention Is All You Need",
                    url="https://arxiv.org/abs/1706.03762",
                    relevance_score=0.95,
                )
            ],
            "grading_results": [
                GradingResult(
                    document_id="retrieved_docs",
                    is_relevant=True,
                    score=1.0,
                    reasoning="Relevant paper",
                )
            ],
            "retrieval_attempts": 1,
            "rewritten_query": None,
        }

        with patch.object(
            agent_service.graph, "ainvoke", new_callable=AsyncMock
        ) as mock_ainvoke:
            mock_ainvoke.return_value = mock_result

            response = await agent_service.ask(
                query="What are transformers?", user_id="user_123"
            )

            assert response["query"] == "What are transformers?"
            assert response["answer"] == "Transformers are attention-based models."
            assert response["guardrail_score"] == 90
            assert response["retrieval_attempts"] == 1
            assert len(response["sources"]) == 1
            assert response["sources"][0]["arxiv_id"] == "1706.03762"
            assert (
                "Validated query scope (score: 90/100)" in response["reasoning_steps"]
            )
            assert "Generated answer from context" in response["reasoning_steps"]

    @pytest.mark.asyncio
    async def test_ask_out_of_scope_workflow_run(self, agent_service):
        mock_result = {
            "messages": [
                HumanMessage(content="How to bake bread?"),
                AIMessage(
                    content="I apologize, but I only answer CS/AI research questions."
                ),
            ],
            "guardrail_result": GuardrailScoring(score=15, reason="Cooking topic"),
            "routing_decision": "out_of_scope",
            "relevant_sources": [],
            "grading_results": [],
            "retrieval_attempts": 0,
            "rewritten_query": None,
        }

        with patch.object(
            agent_service.graph, "ainvoke", new_callable=AsyncMock
        ) as mock_ainvoke:
            mock_ainvoke.return_value = mock_result

            response = await agent_service.ask(query="How to bake bread?")

            assert response["guardrail_score"] == 15
            assert response["retrieval_attempts"] == 0
            assert len(response["sources"]) == 0
            assert "Handled query as out-of-scope" in response["reasoning_steps"]

    def test_extract_answer_fallback_empty_messages(self, agent_service):
        answer = agent_service._extract_answer({"messages": []})
        assert answer == "No answer generated."

    def test_mermaid_diagram_generation(self, agent_service):
        mermaid = agent_service.get_graph_mermaid()
        assert "graph TD" in mermaid
        assert "guardrail" in mermaid
        assert "out_of_scope" in mermaid
        assert "retrieve" in mermaid
