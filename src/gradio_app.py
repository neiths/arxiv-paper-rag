import json
import logging
from collections.abc import Iterator

import gradio as gr
import httpx

logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_MODEL = "llama3.2:latest"
AVAILABLE_CATEGORIES = ["cs.AI", "cs.LG"]


async def stream_response(
    query: str,
    top_k: int = 3,
    use_hybrid: bool = True,
    model: str = DEFAULT_MODEL,
    categories: str = "",
) -> Iterator[str]:
    """Stream response from the RAG API"""
    if not query.strip():
        yield "Please enter a question."
        return

    # Parse categories
    category_list = (
        [cat.strip() for cat in categories.split(",") if cat.strip()]
        if categories
        else None
    )

    # Prepare request payload
    payload = {
        "query": query,
        "top_k": top_k,
        "use_hybrid": use_hybrid,
        "model": model,
        "categories": category_list,
    }

    try:
        url = f"{API_BASE_URL}/stream"
        async with (
            httpx.AsyncClient(timeout=60.0) as client,
            client.stream(
                "POST",
                url,
                json=payload,
                headers={"Accept": "text/plain"},
            ) as response,
        ):
            if response.status_code != 200:
                yield f"Error: API returned status {response.status_code}"
                return

            current_answer = ""
            sources = []
            chunks_used = 0
            search_mode = ""

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    try:
                        data = json.loads(data_str)

                        # Handle error
                        if "error" in data:
                            yield f"Error: {data['error']}"
                            return

                        # Handle metadata
                        if "sources" in data:
                            sources = data["sources"]
                            chunks_used = data.get("chunks_used", 0)
                            search_mode = data.get("search_mode", "unknown")
                            continue

                        # Handle streaming chunks
                        if "chunk" in data:
                            current_answer += data["chunk"]
                            # Format response with sources if we have them
                            formatted_response = current_answer
                            if sources or chunks_used:
                                formatted_response += "\n\n**Search Info:**\n"
                                formatted_response += f"- Mode: {search_mode}\n"
                                formatted_response += f"- Chunks used: {chunks_used}\n"
                                if sources:
                                    formatted_response += (
                                        f"- Sources: {len(sources)} papers\n"
                                    )
                                    for i, source in enumerate(
                                        sources[:3], 1
                                    ):  # Show first 3 sources
                                        formatted_response += f"  {i}. [{source.split('/')[-1]}]({source})\n"
                                    if len(sources) > 3:
                                        formatted_response += (
                                            f"  ... and {len(sources) - 3} more\n"
                                        )

                            yield formatted_response

                        # Handle completion
                        if data.get("done", False):
                            final_answer = data.get("answer", current_answer)
                            if final_answer != current_answer:
                                current_answer = final_answer

                            # Final formatted response
                            formatted_response = current_answer
                            if sources or chunks_used:
                                formatted_response += "\n\n**Search Info:**\n"
                                formatted_response += f"- Mode: {search_mode}\n"
                                formatted_response += f"- Chunks used: {chunks_used}\n"
                                if sources:
                                    formatted_response += (
                                        f"- Sources: {len(sources)} papers\n"
                                    )
                                    for i, source in enumerate(sources[:3], 1):
                                        formatted_response += f"  {i}. [{source.split('/')[-1]}]({source})\n"
                                    if len(sources) > 3:
                                        formatted_response += (
                                            f"  ... and {len(sources) - 3} more\n"
                                        )

                            yield formatted_response
                            break

                    except json.JSONDecodeError:
                        continue  # Skip malformed JSON lines

    except httpx.RequestError as e:
        yield f"Connection error: {e!s}\nMake sure the API server is running at {API_BASE_URL}"
    except Exception as e:
        yield f"Unexpected error: {e!s}"


async def run_facebook_agent(
    arxiv_id: str,
    model: str,
    dry_run: bool,
) -> tuple[str, str]:
    """Call the LangGraph Facebook Publisher Agent endpoint."""
    payload = {
        "arxiv_id": arxiv_id.strip() if arxiv_id.strip() else None,
        "model": model,
        "dry_run": dry_run,
    }
    try:
        url = f"{API_BASE_URL}/agent/publish-facebook"
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                return (
                    f"❌ **API Error**: Status {response.status_code}\n\n{response.text}",
                    "",
                )

            data = response.json()
            status_val = data.get("status")
            error = data.get("error")
            paper_title = data.get("paper_title", "Unknown Title")
            arxiv_id_res = data.get("arxiv_id", "")
            post_content = data.get("facebook_post", "")
            used_full_text = data.get("used_full_text", False)
            post_id = data.get("facebook_post_id")

            if error:
                status_text = f"❌ **Error**: {error}\n- **Paper**: {paper_title} (`{arxiv_id_res}`)"
            elif status_val == "published":
                status_text = (
                    f"✅ **Published to Facebook Page!**\n\n"
                    f"- **Post ID**: `{post_id}`\n"
                    f"- **Paper Title**: {paper_title}\n"
                    f"- **arXiv ID**: `{arxiv_id_res}`\n"
                    f"- **Source Used**: {'Full Parsed PDF Text' if used_full_text else 'arXiv Abstract'}"
                )
            else:  # dry_run_success
                status_text = (
                    f"🔍 **Dry Run Complete (Draft Generated)**\n\n"
                    f"- **Paper Title**: {paper_title}\n"
                    f"- **arXiv ID**: `{arxiv_id_res}`\n"
                    f"- **Source Used**: {'Full Parsed PDF Text' if used_full_text else 'arXiv Abstract'}\n"
                    f"- **Note**: Post was not published to Facebook API. Uncheck 'Dry Run Mode' to publish live."
                )

            return status_text, post_content

    except httpx.RequestError as e:
        return (
            f"❌ **Connection Error**: {e!s}\nMake sure the API server is running at `{API_BASE_URL}`",
            "",
        )
    except Exception as e:
        return f"❌ **Unexpected Error**: {e!s}", ""


def create_gradio_interface():
    """Create and configure the Gradio interface"""

    with gr.Blocks(
        title="arXiv Paper Curator & Facebook Agent",
        theme=gr.themes.Soft(),
    ) as interface:
        gr.Markdown(
            """
            # 🔬 arXiv Paper Curator & LangGraph Facebook Agent

            Search papers, chat with your library via RAG, or generate structured Facebook posts using LangGraph agents.
            """
        )

        with gr.Tabs():
            with gr.TabItem("💬 RAG Chat"):
                with gr.Row():
                    with gr.Column(scale=3):
                        query_input = gr.Textbox(
                            label="Your Question",
                            placeholder="What are transformers in machine learning?",
                            lines=2,
                            max_lines=5,
                        )

                    with gr.Column(scale=1):
                        submit_btn = gr.Button(
                            "Ask Question", variant="primary", size="lg"
                        )

                with (
                    gr.Row(),
                    gr.Column(),
                    gr.Accordion("Advanced Options", open=False),
                ):
                    top_k = gr.Slider(
                        minimum=1,
                        maximum=10,
                        value=3,
                        step=1,
                        label="Number of chunks to retrieve",
                        info="More chunks = more context but slower generation",
                    )

                    use_hybrid = gr.Checkbox(
                        value=True,
                        label="Use hybrid search (BM25 + vector embeddings)",
                        info="Usually better results than keyword-only search",
                    )

                    model_choice = gr.Dropdown(
                        choices=[
                            "llama3.2:latest",
                            "llama3.2:3b",
                            "llama3.1:8b",
                            "qwen2.5:7b",
                        ],
                        value=DEFAULT_MODEL,
                        label="LLM Model",
                        info="Larger models may give better answers but are slower",
                    )

                    categories = gr.Textbox(
                        label="arXiv Categories (optional)",
                        placeholder="cs.AI, cs.LG, cs.CL",
                        info="Comma-separated. Leave empty for all categories",
                    )

                response_output = gr.Markdown(
                    label="Answer",
                    value="Ask a question to get started!",
                    height=400,
                    elem_classes=["response-markdown"],
                )

                # Examples
                gr.Examples(
                    examples=[
                        [
                            "What are transformers in machine learning?",
                            3,
                            True,
                            "llama3.2:latest",
                            "cs.AI, cs.LG",
                        ],
                        [
                            "How do convolutional neural networks work?",
                            5,
                            True,
                            "llama3.2:latest",
                            "cs.CV, cs.LG",
                        ],
                        [
                            "What is attention mechanism in deep learning?",
                            4,
                            False,
                            "llama3.2:latest",
                            "cs.AI",
                        ],
                        [
                            "Explain reinforcement learning algorithms",
                            3,
                            True,
                            "llama3.2:latest",
                            "cs.LG, cs.AI",
                        ],
                        [
                            "What are the latest developments in NLP?",
                            5,
                            True,
                            "llama3.2:latest",
                            "cs.CL",
                        ],
                    ],
                    inputs=[query_input, top_k, use_hybrid, model_choice, categories],
                )

                # Handle submission
                submit_btn.click(
                    fn=stream_response,
                    inputs=[query_input, top_k, use_hybrid, model_choice, categories],
                    outputs=[response_output],
                    show_progress=True,
                )

                # Handle Enter key
                query_input.submit(
                    fn=stream_response,
                    inputs=[query_input, top_k, use_hybrid, model_choice, categories],
                    outputs=[response_output],
                    show_progress=True,
                )

            with gr.TabItem("🤖 Facebook Paper Agent"):
                gr.Markdown(
                    """
                    ### 📢 LangGraph Paper Summarizer & Facebook Publisher Agent
                    Select a paper (or leave blank to pick the **newest paper in DB**).
                    The agent will fetch the paper, summarize key features & methodology, format it, and post it to your Facebook Page.
                    """
                )
                with gr.Row():
                    with gr.Column(scale=2):
                        fb_arxiv_id = gr.Textbox(
                            label="arXiv ID (optional)",
                            placeholder="e.g., 2507.17748 (Leave blank to pick newest paper in DB)",
                        )
                        fb_model_choice = gr.Dropdown(
                            choices=[
                                "llama3.2:latest",
                                "llama3.2:3b",
                                "llama3.1:8b",
                                "qwen2.5:7b",
                            ],
                            value=DEFAULT_MODEL,
                            label="LLM Model for Agent",
                        )
                        fb_dry_run = gr.Checkbox(
                            value=True,
                            label="Dry Run Mode (Preview summary without posting to Facebook)",
                            info="Uncheck this box when you are ready to publish directly to your Facebook Page.",
                        )
                        fb_run_btn = gr.Button(
                            "🚀 Run LangGraph Facebook Agent",
                            variant="primary",
                            size="lg",
                        )

                    with gr.Column(scale=3):
                        fb_status_output = gr.Markdown(
                            label="Agent Status",
                            value="*Click 'Run LangGraph Facebook Agent' to start.*",
                        )
                        fb_post_preview = gr.Markdown(
                            label="Facebook Post Content Preview",
                            value="",
                        )

                fb_run_btn.click(
                    fn=run_facebook_agent,
                    inputs=[fb_arxiv_id, fb_model_choice, fb_dry_run],
                    outputs=[fb_status_output, fb_post_preview],
                    show_progress=True,
                )

        gr.Markdown(
            """
            ---

            **Note**: Make sure the RAG API server is running at `http://localhost:8000` before using this interface.

            **Categories**: cs.AI (Artificial Intelligence), cs.LG (Machine Learning), cs.CL (Computational Linguistics),
            cs.CV (Computer Vision), cs.NE (Neural Networks), stat.ML (Statistics - Machine Learning)
            """
        )

    return interface


def main():
    """Main entry point for the Gradio app"""
    print("🚀 Starting arXiv Paper Curator Gradio Interface...")
    print(f"📡 API Base URL: {API_BASE_URL}")

    interface = create_gradio_interface()

    # Launch the interface with queue enabled for streaming generator support
    interface.queue().launch(
        server_name="0.0.0.0",
        server_port=7861,  # Changed to avoid port conflict
        share=False,
        show_error=True,
        quiet=False,
    )


if __name__ == "__main__":
    main()
