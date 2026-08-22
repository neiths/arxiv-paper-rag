import logging
import time
from typing import Literal

from langgraph.runtime import Runtime

from ..context import Context
from ..models import GuardrailScoring
from ..prompts import GUARDRAIL_PROMPT
from ..state import AgentState
from .utils import get_latest_query

logger = logging.getLogger(__name__)


def continue_after_guardrail(
    state: AgentState,
    runtime: Runtime[Context] | None = None,
) -> Literal["continue", "out_of_scope"]:
    """Determine routing after guardrail validation.

    :param state: Current agent state
    :param runtime: Optional runtime context for threshold lookup
    :returns: "continue" if score >= threshold, otherwise "out_of_scope"
    """
    guardrail_result = state.get("guardrail_result")

    if not guardrail_result:
        logger.warning("No guardrail result found, defaulting to continue")
        return "continue"

    score = guardrail_result.score
    threshold = (
        runtime.context.guardrail_threshold
        if runtime and hasattr(runtime, "context")
        else 60
    )

    logger.info(f"Guardrail score: {score}, threshold: {threshold}")

    return "continue" if score >= threshold else "out_of_scope"


async def ainvoke_guardrail_step(
    state: AgentState,
    runtime: Runtime[Context],
) -> dict[str, GuardrailScoring]:
    """Validate whether user query is within domain scope using LLM.

    This node evaluates whether the user's question pertains to Computer Science,
    AI, and Machine Learning academic research papers and assigns a relevance score.

    :param state: Current agent state
    :param runtime: Runtime context
    :returns: Dictionary with guardrail_result
    """
    logger.info("NODE: guardrail_validation")
    start_time = time.time()

    # Get the latest query
    query = get_latest_query(state["messages"])
    logger.debug(f"Evaluating query: {query[:100]}")

    # Create span for guardrail validation
    span = None
    span_ctx = None
    if (
        runtime.context.langfuse_enabled
        and runtime.context.langfuse_tracer
        and runtime.context.trace
    ):
        try:
            span_ctx = runtime.context.langfuse_tracer.start_span(
                name="guardrail_validation",
                input_data={
                    "query": query,
                    "threshold": runtime.context.guardrail_threshold,
                },
                metadata={
                    "node": "guardrail",
                    "model": runtime.context.model_name,
                },
            )
            span = span_ctx.__enter__()
            logger.debug("Created Langfuse span for guardrail validation")
        except Exception as e:
            logger.warning(f"Failed to create span for guardrail validation: {e}")

    try:
        # Create guardrail prompt from template
        guardrail_prompt = GUARDRAIL_PROMPT.format(question=query)

        # Get LLM from runtime context
        llm = runtime.context.ollama_client.get_langchain_model(
            model=runtime.context.model_name,
            temperature=0.0,
        )

        # Create structured output LLM for guardrail scoring
        structured_llm = llm.with_structured_output(GuardrailScoring)

        # Invoke LLM for guardrail evaluation
        logger.info("Invoking LLM for guardrail validation")
        response: GuardrailScoring = await structured_llm.ainvoke(guardrail_prompt)

        logger.info(
            f"Guardrail result - Score: {response.score}, Reason: {response.reason}"
        )

        # Update span with successful result
        if span_ctx:
            execution_time = (time.time() - start_time) * 1000
            runtime.context.langfuse_tracer.update_span(
                span,
                output={
                    "score": response.score,
                    "reason": response.reason,
                    "decision": (
                        "continue"
                        if response.score >= runtime.context.guardrail_threshold
                        else "out_of_scope"
                    ),
                },
                metadata={
                    "execution_time_ms": execution_time,
                    "threshold": runtime.context.guardrail_threshold,
                },
            )

    except Exception as e:
        logger.error(f"LLM guardrail validation failed: {e}, falling back to default")

        # Fallback to a conservative default if LLM fails
        response = GuardrailScoring(
            score=50,
            reason=f"LLM validation failed, using conservative default: {str(e)}",
        )

        # Update span with error
        if span_ctx:
            execution_time = (time.time() - start_time) * 1000
            runtime.context.langfuse_tracer.update_span(
                span,
                output={
                    "score": response.score,
                    "reason": response.reason,
                    "error": str(e),
                    "fallback": True,
                },
                metadata={
                    "execution_time_ms": execution_time,
                    "threshold": runtime.context.guardrail_threshold,
                },
                level="ERROR",
            )

    finally:
        if span_ctx:
            span_ctx.__exit__(None, None, None)

    return {"guardrail_result": response}
