from unittest.mock import AsyncMock, patch

import pytest


async def test_ask_agentic_endpoint_basic(client):
    mock_ask_result = {
        "query": "What are transformers in machine learning?",
        "answer": "Transformers are neural network architectures...",
        "sources": [
            {
                "arxiv_id": "1706.03762",
                "title": "Attention Is All You Need",
                "url": "https://arxiv.org/pdf/1706.03762.pdf",
            }
        ],
        "reasoning_steps": ["Validated query scope", "Retrieved documents"],
        "retrieval_attempts": 1,
        "trace_id": "test-trace-id",
    }

    with patch(
        "src.services.agents.agentic_rag.AgenticRAGService.ask",
        new_callable=AsyncMock,
    ) as mock_ask:
        mock_ask.return_value = mock_ask_result

        response = await client.post(
            "/api/v1/ask-agentic",
            json={
                "query": "What are transformers in machine learning?",
                "model": "llama3.2:latest",
                "top_k": 3,
                "use_hybrid": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "What are transformers in machine learning?"
        assert data["answer"] == "Transformers are neural network architectures..."
        assert data["retrieval_attempts"] == 1
        assert len(data["reasoning_steps"]) == 2
        assert "https://arxiv.org/pdf/1706.03762.pdf" in data["sources"]


async def test_ask_agentic_endpoint_validation_error(client):
    response = await client.post(
        "/api/v1/ask-agentic",
        json={"query": ""},
    )
    assert response.status_code == 422


async def test_feedback_endpoint_disabled_langfuse(client):
    response = await client.post(
        "/api/v1/feedback",
        json={
            "trace_id": "test-trace-id",
            "score": 1.0,
            "comment": "Great answer!",
        },
    )
    # Langfuse client is disabled in test fixture
    assert response.status_code in [200, 500, 503]
