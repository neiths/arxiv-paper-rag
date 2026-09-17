import logging

from langgraph.graph import END, START, StateGraph

from .context import DeepResearchContext
from .nodes import (
    deep_analysis_node,
    direct_paper_node,
    facebook_publisher_node,
    route_input_node,
    social_writer_node,
    topic_research_node,
)
from .state import DeepResearchState

logger = logging.getLogger(__name__)


def route_after_input(state: DeepResearchState) -> str:
    """Route to direct paper deep-dive or topic research."""
    if state.get("error"):
        return END
    mode = state.get("mode", "topic_research")
    return "direct_paper" if mode == "direct_paper" else "topic_research"


def check_error_after_gathering(state: DeepResearchState) -> str:
    """Check if paper gathering succeeded before deep analysis."""
    if state.get("error"):
        return END
    return "deep_analysis"


def check_error_after_analysis(state: DeepResearchState) -> str:
    """Check if analysis succeeded before social post generation."""
    if state.get("error"):
        return END
    return "social_writer"


def build_deep_research_graph():
    """Build and compile the LangGraph workflow for Deep Research & Facebook Publishing."""
    logger.info("Building Deep Research LangGraph workflow with context_schema")

    workflow = StateGraph(DeepResearchState, context_schema=DeepResearchContext)

    # Register nodes
    workflow.add_node("route_input", route_input_node)
    workflow.add_node("direct_paper", direct_paper_node)
    workflow.add_node("topic_research", topic_research_node)
    workflow.add_node("deep_analysis", deep_analysis_node)
    workflow.add_node("social_writer", social_writer_node)
    workflow.add_node("facebook_publisher", facebook_publisher_node)

    # Edges
    workflow.add_edge(START, "route_input")

    workflow.add_conditional_edges(
        "route_input",
        route_after_input,
        {
            "direct_paper": "direct_paper",
            "topic_research": "topic_research",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "direct_paper",
        check_error_after_gathering,
        {
            "deep_analysis": "deep_analysis",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "topic_research",
        check_error_after_gathering,
        {
            "deep_analysis": "deep_analysis",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "deep_analysis",
        check_error_after_analysis,
        {
            "social_writer": "social_writer",
            END: END,
        },
    )

    workflow.add_edge("social_writer", "facebook_publisher")
    workflow.add_edge("facebook_publisher", END)

    compiled_graph = workflow.compile()
    logger.info("✓ Deep Research graph compiled successfully")
    return compiled_graph
