"""Unit tests for guardrail node and routing."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import HumanMessage
from src.services.agents.context import Context
from src.services.agents.models import GuardrailScoring
from src.services.agents.nodes.guardrail_node import (
    ainvoke_guardrail_step,
    continue_after_guardrail,
)


@pytest.fixture
def mock_context():
    """Create a mock Context for node execution."""
    ollama_client = MagicMock()
    opensearch_client = MagicMock()
    embeddings_client = MagicMock()
    langfuse_tracer = MagicMock()

    return Context(
        ollama_client=ollama_client,
        opensearch_client=opensearch_client,
        embeddings_client=embeddings_client,
        langfuse_tracer=langfuse_tracer,
        trace=None,
        langfuse_enabled=False,
        model_name="llama3.2:1b",
        guardrail_threshold=60,
    )


class MockRuntime:
    """Mock LangGraph Runtime wrapper."""

    def __init__(self, context: Context):
        self.context = context


class TestContinueAfterGuardrail:
    """Tests for continue_after_guardrail routing function."""

    def test_routing_when_no_guardrail_result(self, mock_context):
        state = {"messages": [HumanMessage(content="test")], "guardrail_result": None}
        runtime = MockRuntime(mock_context)

        decision = continue_after_guardrail(state, runtime)
        assert decision == "continue"

    def test_routing_continue_above_threshold(self, mock_context):
        state = {
            "messages": [HumanMessage(content="What are transformers?")],
            "guardrail_result": GuardrailScoring(score=85, reason="CS research query"),
        }
        runtime = MockRuntime(mock_context)

        decision = continue_after_guardrail(state, runtime)
        assert decision == "continue"

    def test_routing_continue_exact_threshold(self, mock_context):
        state = {
            "messages": [HumanMessage(content="Query")],
            "guardrail_result": GuardrailScoring(score=60, reason="Borderline"),
        }
        runtime = MockRuntime(mock_context)

        decision = continue_after_guardrail(state, runtime)
        assert decision == "continue"

    def test_routing_out_of_scope_below_threshold(self, mock_context):
        state = {
            "messages": [HumanMessage(content="How to cook pasta?")],
            "guardrail_result": GuardrailScoring(score=20, reason="Cooking query"),
        }
        runtime = MockRuntime(mock_context)

        decision = continue_after_guardrail(state, runtime)
        assert decision == "out_of_scope"

    def test_routing_without_runtime(self):
        state = {
            "guardrail_result": GuardrailScoring(score=70, reason="Valid"),
        }
        decision = continue_after_guardrail(state)
        assert decision == "continue"

        state_low = {
            "guardrail_result": GuardrailScoring(score=30, reason="Invalid"),
        }
        decision_low = continue_after_guardrail(state_low)
        assert decision_low == "out_of_scope"


class TestAinvokeGuardrailStep:
    """Tests for ainvoke_guardrail_step node execution."""

    @pytest.mark.asyncio
    async def test_guardrail_step_success_disabled_tracer(self, mock_context):
        mock_llm = MagicMock()
        mock_structured_llm = MagicMock()
        mock_structured_llm.ainvoke = AsyncMock(
            return_value=GuardrailScoring(score=90, reason="Valid CS topic")
        )
        mock_llm.with_structured_output.return_value = mock_structured_llm
        mock_context.ollama_client.get_langchain_model.return_value = mock_llm

        state = {
            "messages": [
                HumanMessage(content="Explain transformer attention mechanism")
            ]
        }
        runtime = MockRuntime(mock_context)

        result = await ainvoke_guardrail_step(state, runtime)

        assert "guardrail_result" in result
        assert result["guardrail_result"].score == 90
        assert result["guardrail_result"].reason == "Valid CS topic"

    @pytest.mark.asyncio
    async def test_guardrail_step_with_active_tracer(self, mock_context):
        mock_context.langfuse_enabled = True
        mock_context.trace = MagicMock()

        mock_span = MagicMock()
        mock_span_ctx = MagicMock()
        mock_span_ctx.__enter__.return_value = mock_span
        mock_span_ctx.__exit__.return_value = None
        mock_context.langfuse_tracer.start_span.return_value = mock_span_ctx

        mock_llm = MagicMock()
        mock_structured_llm = MagicMock()
        mock_structured_llm.ainvoke = AsyncMock(
            return_value=GuardrailScoring(score=95, reason="Strong match")
        )
        mock_llm.with_structured_output.return_value = mock_structured_llm
        mock_context.ollama_client.get_langchain_model.return_value = mock_llm

        state = {"messages": [HumanMessage(content="What is BERT?")]}
        runtime = MockRuntime(mock_context)

        result = await ainvoke_guardrail_step(state, runtime)

        assert result["guardrail_result"].score == 95
        mock_context.langfuse_tracer.start_span.assert_called_once()
        mock_context.langfuse_tracer.update_span.assert_called_once()
        mock_span_ctx.__exit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_guardrail_step_llm_failure_fallback(self, mock_context):
        mock_context.langfuse_enabled = True
        mock_context.trace = MagicMock()

        mock_span = MagicMock()
        mock_span_ctx = MagicMock()
        mock_span_ctx.__enter__.return_value = mock_span
        mock_span_ctx.__exit__.return_value = None
        mock_context.langfuse_tracer.start_span.return_value = mock_span_ctx

        mock_llm = MagicMock()
        mock_structured_llm = MagicMock()
        mock_structured_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM offline"))
        mock_llm.with_structured_output.return_value = mock_structured_llm
        mock_context.ollama_client.get_langchain_model.return_value = mock_llm

        state = {"messages": [HumanMessage(content="What is BERT?")]}
        runtime = MockRuntime(mock_context)

        result = await ainvoke_guardrail_step(state, runtime)

        assert "guardrail_result" in result
        assert result["guardrail_result"].score == 50
        assert "LLM validation failed" in result["guardrail_result"].reason
        mock_context.langfuse_tracer.update_span.assert_called_once()
        assert mock_context.langfuse_tracer.update_span.call_args[1]["level"] == "ERROR"
        mock_span_ctx.__exit__.assert_called_once()
