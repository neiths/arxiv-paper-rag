"""Unit tests for Langfuse tracer and RAG tracer."""

from unittest.mock import MagicMock

import pytest
from src.config import Settings
from src.services.langfuse.client import LangfuseTracer
from src.services.langfuse.tracer import RAGTracer


@pytest.fixture
def disabled_settings() -> Settings:
    from src.config import LangfuseSettings

    return Settings(langfuse=LangfuseSettings(enabled=False))


@pytest.fixture
def enabled_settings() -> Settings:
    from src.config import LangfuseSettings

    return Settings(
        langfuse=LangfuseSettings(
            enabled=True,
            public_key="pk-test-12345",
            secret_key="sk-test-12345",
            host="http://localhost:3001",
        )
    )


def test_langfuse_tracer_disabled(disabled_settings):
    """Test that LangfuseTracer gracefully no-ops when disabled."""
    tracer = LangfuseTracer(disabled_settings)
    assert tracer.client is None

    # trace_rag_request should yield None and not raise
    with tracer.trace_rag_request(query="test", user_id="user1") as trace:
        assert trace is None

    # start_span should yield None and not raise
    with tracer.start_span(name="test_span") as span:
        assert span is None

    # start_generation should yield None and not raise
    with tracer.start_generation(
        name="test_gen", model="m", input_data="prompt"
    ) as gen:
        assert gen is None

    # trace_langgraph_agent should yield (None, None)
    with tracer.trace_langgraph_agent(name="agent") as (ctx, handler):
        assert ctx is None
        assert handler is None

    assert tracer.get_trace_id() is None
    assert tracer.submit_feedback(trace_id="t1", score=1.0) is False
    tracer.flush()
    tracer.shutdown()


def test_rag_tracer_with_disabled_langfuse(disabled_settings):
    """Test that RAGTracer methods work without errors when Langfuse is disabled."""
    langfuse_tracer = LangfuseTracer(disabled_settings)
    rag_tracer = RAGTracer(langfuse_tracer)

    with rag_tracer.trace_request(user_id="user1", query="test query") as trace:
        assert trace is None

        with rag_tracer.trace_embedding(trace, query="test query") as emb_span:
            assert emb_span is None

        with rag_tracer.trace_search(trace, query="test query", top_k=5) as search_span:
            assert search_span is None
            rag_tracer.end_search(search_span, chunks=[], arxiv_ids=[], total_hits=0)

        with rag_tracer.trace_prompt_construction(trace, chunks=[]) as prompt_span:
            assert prompt_span is None
            rag_tracer.end_prompt(prompt_span, prompt="test prompt")

        with rag_tracer.trace_generation(
            trace, model="llama", prompt="test prompt"
        ) as gen_span:
            assert gen_span is None
            rag_tracer.end_generation(gen_span, response="test answer", model="llama")

        rag_tracer.end_request(trace, response="test answer", total_duration=0.5)


def test_trace_rag_request_with_mocked_client(enabled_settings):
    """Test trace_rag_request with a mocked Langfuse client."""
    tracer = LangfuseTracer(enabled_settings)
    mock_client = MagicMock()
    mock_span = MagicMock()
    mock_span.trace_id = "trace_abc123"

    mock_client.start_as_current_observation.return_value.__enter__.return_value = (
        mock_span
    )
    mock_client.start_as_current_observation.return_value.__exit__.return_value = None
    tracer.client = mock_client

    with tracer.trace_rag_request(
        query="What is quantum ML?",
        user_id="user_42",
        session_id="session_42",
        metadata={"custom": "val"},
        tags=["rag", "arxiv"],
    ) as trace:
        assert trace == mock_span
        mock_client.start_as_current_observation.assert_called_once_with(
            name="rag_request",
            as_type="span",
            input={"query": "What is quantum ML?"},
            metadata={"custom": "val"},
        )

    # get_trace_id with trace
    assert tracer.get_trace_id(mock_span) == "trace_abc123"


def test_rag_tracer_full_pipeline_mocked(enabled_settings):
    """Test full RAGTracer lifecycle with mocked Langfuse observations."""
    tracer = LangfuseTracer(enabled_settings)
    mock_client = MagicMock()
    mock_root = MagicMock()
    mock_span = MagicMock()
    mock_gen = MagicMock()

    tracer.client = mock_client

    rag_tracer = RAGTracer(tracer)

    # Mock start_span and start_generation
    mock_client.start_as_current_observation.side_effect = [
        # root trace
        MagicMock(
            __enter__=MagicMock(return_value=mock_root),
            __exit__=MagicMock(return_value=None),
        ),
        # embedding span
        MagicMock(
            __enter__=MagicMock(return_value=mock_span),
            __exit__=MagicMock(return_value=None),
        ),
        # search span
        MagicMock(
            __enter__=MagicMock(return_value=mock_span),
            __exit__=MagicMock(return_value=None),
        ),
        # prompt span
        MagicMock(
            __enter__=MagicMock(return_value=mock_span),
            __exit__=MagicMock(return_value=None),
        ),
        # gen span
        MagicMock(
            __enter__=MagicMock(return_value=mock_gen),
            __exit__=MagicMock(return_value=None),
        ),
    ]

    with rag_tracer.trace_request("user_1", "What is attention?") as trace:
        with rag_tracer.trace_embedding(trace, "What is attention?"):
            pass

        with rag_tracer.trace_search(trace, "What is attention?", top_k=3) as s_span:
            rag_tracer.end_search(
                s_span, chunks=[{"id": 1}], arxiv_ids=["2401.00001"], total_hits=1
            )

        with rag_tracer.trace_prompt_construction(trace, chunks=[{"id": 1}]) as p_span:
            rag_tracer.end_prompt(p_span, "prompt content")

        with rag_tracer.trace_generation(trace, "llama3.2", "prompt content") as g_span:
            rag_tracer.end_generation(g_span, "Attention is all you need.", "llama3.2")

        rag_tracer.end_request(trace, "Attention is all you need.", total_duration=1.2)

    assert mock_root.update.called
    assert mock_client.flush.called


def test_submit_feedback_mocked(enabled_settings):
    """Test submit_feedback calls create_score correctly."""
    tracer = LangfuseTracer(enabled_settings)
    mock_client = MagicMock()
    tracer.client = mock_client

    success = tracer.submit_feedback(
        trace_id="t123", score=0.9, comment="Great answer!"
    )
    assert success is True
    mock_client.create_score.assert_called_once_with(
        trace_id="t123",
        name="user-feedback",
        value=0.9,
        comment="Great answer!",
    )
