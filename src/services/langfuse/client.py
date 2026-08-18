import logging
from contextlib import contextmanager
from typing import Any

from langfuse import Langfuse
from src.config import Settings

logger = logging.getLogger(__name__)


class LangfuseTracer:
    """Wrapper for Langfuse v3 tracing client with CallbackHandler support."""

    def __init__(self, settings: Settings):
        self.settings = settings.langfuse
        self.client: Langfuse | None = None

        if (
            self.settings.enabled
            and self.settings.public_key
            and self.settings.secret_key
        ):
            try:
                # Initialize Langfuse v3 singleton client
                # Configuration moved to client initialization (not handler)
                self.client = Langfuse(
                    public_key=self.settings.public_key,
                    secret_key=self.settings.secret_key,
                    host=self.settings.host,
                    flush_at=self.settings.flush_at,
                    flush_interval=self.settings.flush_interval,
                    debug=self.settings.debug,
                )
                logger.info(
                    f"Langfuse v3 tracing initialized (host: {self.settings.host})"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Langfuse: {e}")
                self.client = None
        else:
            logger.info("Langfuse tracing disabled or missing credentials")

    def get_callback_handler(self):
        """
        Get a CallbackHandler for LangChain/LangGraph integration.

        This is the v3/v4 recommended approach - all LLM calls are automatically traced.

        Returns:
            CallbackHandler instance if Langfuse is enabled, None otherwise
        """
        if not self.client:
            return None

        try:
            from langfuse.langchain import CallbackHandler

            return CallbackHandler(public_key=self.settings.public_key)
        except Exception as e:
            logger.error(f"Error creating CallbackHandler: {e}")
            return None

    @contextmanager
    def trace_rag_request(
        self,
        query: str,
        user_id: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ):
        """
        Context manager for tracing a RAG request in Langfuse v3/v4.

        Creates a top-level span and propagates trace attributes (user_id, session_id,
        metadata, tags) into the OpenTelemetry context so child spans/generations link properly.

        Args:
            query: The user query being processed
            user_id: User identifier
            session_id: Optional session identifier
            metadata: Additional metadata to attach to the trace
            tags: Optional tags for the trace

        Yields:
            LangfuseSpan or None: Root observation context object for updates
        """
        if not self.client:
            yield None
            return

        session = session_id or f"session_{user_id}"
        meta = metadata or {"query": query}

        try:
            from langfuse import propagate_attributes

            with (
                self.client.start_as_current_observation(
                    name="rag_request",
                    as_type="span",
                    input={"query": query},
                    metadata=meta,
                ) as span,
                propagate_attributes(
                    user_id=user_id,
                    session_id=session,
                    metadata=meta,
                    tags=tags,
                ),
            ):
                yield span
        except Exception as e:
            logger.error(f"Error creating RAG request trace: {e}")
            yield None

    @contextmanager
    def trace_langgraph_agent(
        self,
        name: str,
        user_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ):
        """
        Context manager to wrap LangGraph agent execution with a top-level trace span.

        Usage:
            with tracer.trace_langgraph_agent(name="agentic_rag", ...) as (trace_ctx, handler):
                result = graph.invoke(input, config={"callbacks": [handler]})
                if trace_ctx:
                    tracer.update_span(trace_ctx, output=result)

        Args:
            name: Name for the trace span (e.g., "agentic_rag_graph")
            user_id: Optional user identifier
            session_id: Optional session identifier
            metadata: Additional metadata to attach
            tags: Optional tags for the trace

        Yields:
            Tuple of (trace_context, callback_handler) for graph execution
        """
        if not self.client:
            yield (None, None)
            return

        try:
            from langfuse import propagate_attributes

            handler = self.get_callback_handler()
            with (
                self.client.start_as_current_observation(
                    name=name,
                    as_type="agent",
                    metadata=metadata or {},
                ) as span,
                propagate_attributes(
                    user_id=user_id,
                    session_id=session_id,
                    metadata=metadata,
                    tags=tags,
                    trace_name=name,
                ),
            ):
                yield (span, handler)
        except Exception as e:
            logger.error(f"Error creating LangGraph agent trace: {e}")
            yield (None, None)

    def get_trace_id(self, trace=None) -> str | None:
        """
        Get the current trace ID from Langfuse context.

        Args:
            trace: Optional span or observation object with trace_id attribute

        Returns:
            Trace ID string or None if trace is disabled
        """
        if not self.client:
            return None

        if trace and hasattr(trace, "trace_id"):
            return trace.trace_id

        try:
            return self.client.get_current_trace_id()
        except Exception as e:
            logger.error(f"Error getting trace ID: {e}")
            return None

    def submit_feedback(
        self,
        trace_id: str,
        score: float,
        name: str = "user-feedback",
        comment: str | None = None,
    ) -> bool:
        """
        Submit user feedback for a trace.

        Args:
            trace_id: Trace ID
            score: Feedback score (0-1 or -1 to 1)
            name: Name of the score (default: "user-feedback")
            comment: Optional feedback comment

        Returns:
            True if feedback was submitted successfully, False otherwise
        """
        if not self.client:
            logger.warning("Cannot submit feedback: Langfuse is disabled")
            return False

        try:
            self.client.create_score(
                trace_id=trace_id,
                name=name,
                value=score,
                comment=comment,
            )
            logger.info(f"Submitted feedback for trace {trace_id}: score={score}")
            return True
        except Exception as e:
            logger.error(f"Error submitting feedback: {e}")
            return False

    def flush(self):
        """Flush any pending traces."""
        if self.client:
            try:
                self.client.flush()
            except Exception as e:
                logger.error(f"Error flushing Langfuse: {e}")

    def shutdown(self):
        """Shutdown the Langfuse client."""
        if self.client:
            try:
                self.client.flush()
                self.client.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down Langfuse: {e}")

    @contextmanager
    def start_generation(
        self,
        name: str,
        model: str,
        input_data: Any,
        metadata: dict[str, Any] | None = None,
        model_parameters: dict[str, Any] | None = None,
    ):
        """
        Start a generation span for LLM calls.

        Usage:
            with tracer.start_generation(name="decision_llm", model="llama3.2", input_data=prompt) as gen:
                response = await llm.generate(...)
                tracer.update_generation(gen, output=response, usage_metadata={...})

        Args:
            name: Name for this generation (e.g., "decision_llm", "grading_llm")
            model: Model identifier (e.g., "llama3.2:1b", "gpt-4o")
            input_data: Input to the LLM (prompt or messages)
            metadata: Additional metadata (temperature, max_tokens, etc.)
            model_parameters: Optional dict of model parameters

        Yields:
            Generation observation context object for updates
        """
        if not self.client:
            yield None
            return

        try:
            with self.client.start_as_current_observation(
                name=name,
                as_type="generation",
                model=model,
                input=input_data,
                metadata=metadata or {},
                model_parameters=model_parameters,
            ) as generation:
                yield generation
        except Exception as e:
            logger.error(f"Error creating generation span: {e}")
            yield None

    @contextmanager
    def start_span(
        self,
        name: str,
        input_data: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Start a generic span for non-LLM operations.

        Usage:
            with tracer.start_span(name="retrieve_papers", input_data={"query": q}) as span:
                docs = retrieve(...)
                tracer.update_span(span, output={"docs_count": len(docs)})

        Args:
            name: Name for this span (e.g., "retrieve_papers", "grade_documents")
            input_data: Input to this operation
            metadata: Additional metadata

        Yields:
            Span observation context object for updates
        """
        if not self.client:
            yield None
            return

        try:
            with self.client.start_as_current_observation(
                name=name,
                as_type="span",
                input=input_data,
                metadata=metadata or {},
            ) as span:
                yield span
        except Exception as e:
            logger.error(f"Error creating span: {e}")
            yield None

    def update_generation(
        self,
        generation,
        output: Any,
        usage_metadata: dict[str, Any] | None = None,
        completion_start_time: float | None = None,
    ):
        """
        Update a generation span with output and usage metrics.

        Args:
            generation: Generation object from start_generation()
            output: LLM output/response
            usage_metadata: Token usage and timing info
                - prompt_tokens: int
                - completion_tokens: int
                - total_tokens: int
                - latency_ms: float
            completion_start_time: Optional start time for latency calculation
        """
        if not generation:
            return

        try:
            update_data: dict[str, Any] = {"output": output}

            if usage_metadata:
                usage_details = {}
                if "prompt_tokens" in usage_metadata:
                    usage_details["input"] = usage_metadata.get("prompt_tokens", 0)
                if "completion_tokens" in usage_metadata:
                    usage_details["output"] = usage_metadata.get("completion_tokens", 0)
                if "total_tokens" in usage_metadata:
                    usage_details["total"] = usage_metadata.get("total_tokens", 0)
                if usage_details:
                    update_data["usage_details"] = usage_details

                if "latency_ms" in usage_metadata:
                    update_data["metadata"] = {
                        "latency_ms": usage_metadata["latency_ms"]
                    }

            generation.update(**update_data)
        except Exception as e:
            logger.error(f"Error updating generation: {e}")

    def update_span(
        self,
        span,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ):
        """
        Update a span with output and metadata.

        Args:
            span: Span object from start_span()
            output: Operation output
            metadata: Additional metadata to attach
            level: Log level (e.g., "ERROR", "WARNING", "DEFAULT", "DEBUG") for error tracking
            status_message: Status or error message
        """
        if not span:
            return

        try:
            update_data: dict[str, Any] = {}
            if output is not None:
                update_data["output"] = output
            if metadata:
                update_data["metadata"] = metadata
            if level:
                update_data["level"] = level
            if status_message:
                update_data["status_message"] = status_message

            if update_data:
                span.update(**update_data)
        except Exception as e:
            logger.error(f"Error updating span: {e}")
