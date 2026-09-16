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


async def run_deep_agent_ui(
    query: str,
    language: str,
    post_style: str,
    auto_publish: bool,
    model: str,
):
    """Call Deep Research endpoint from Gradio UI."""
    if not query.strip():
        return "⚠️ Please enter an arXiv paper URL, ID, or research topic.", "", ""

    payload = {
        "query": query.strip(),
        "language": "vi" if "Vietnamese" in language else "en",
        "post_style": post_style,
        "auto_publish": auto_publish,
        "model_name": model if model else None,
    }
    url = f"{API_BASE_URL}/deep-research/run"
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code != 200:
                return f"❌ Error ({res.status_code}): {res.text}", "", ""
            data = res.json()
            synthesis = data.get("synthesis_report", "")
            fb_post = data.get("facebook_post", "")
            status_info = f"**Status:** {'Published to Facebook ✅' if data.get('published_to_facebook') else 'Draft preserved 📝'}\n"
            if data.get("facebook_post_id"):
                status_info += f"- **Post ID:** `{data.get('facebook_post_id')}`\n"
            if data.get("facebook_post_url"):
                status_info += f"- **Post URL:** [{data.get('facebook_post_url')}]({data.get('facebook_post_url')})\n"
            status_info += f"- **Duration:** {data.get('duration_seconds')}s\n"
            status_info += f"- **Papers Analyzed:** {len(data.get('papers', []))}\n"
            return synthesis, fb_post, status_info
    except Exception as e:
        return f"❌ Request error: {str(e)}", "", ""


async def publish_draft_to_facebook_ui(message: str, link: str):
    """Publish drafted post directly to Facebook."""
    if not message.strip():
        return "⚠️ Cannot publish empty post."
    url = f"{API_BASE_URL}/deep-research/publish-facebook"
    payload = {"message": message.strip(), "link": link.strip() if link else None}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, json=payload)
            data = res.json()
            if res.status_code in (200, 201) and data.get("success"):
                sim_text = " [Simulated/Dry-run]" if data.get("is_simulated") else ""
                return f"✅ Published to Facebook! Post ID: {data.get('post_id')}{sim_text}"
            else:
                return f"❌ Publishing failed: {data.get('message', res.text)}"
    except Exception as e:
        return f"❌ Request error: {str(e)}"


def create_gradio_interface():
    """Create and configure the Gradio interface with RAG Chat and Deep Agent tabs."""

    with gr.Blocks(
        title="arXiv Paper Curator & Deep Agent",
        theme=gr.themes.Soft(),
    ) as interface:
        gr.Markdown(
            """
            # 🔬 arXiv Paper Curator & Deep Research Agent
            Research cutting-edge arXiv papers, ask in-depth questions, or autonomously generate and publish Facebook posts.
            """
        )

        with gr.Tabs():
            with gr.TabItem("💬 arXiv RAG Chat"):
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

                query_input.submit(
                    fn=stream_response,
                    inputs=[query_input, top_k, use_hybrid, model_choice, categories],
                    outputs=[response_output],
                    show_progress=True,
                )

            with gr.TabItem("🤖 Deep Agent & Facebook Publisher"):
                gr.Markdown(
                    """
                    ### 🚀 Autonomous Deep Research & Facebook Publishing
                    Enter an arXiv paper URL / ID or a broad research topic.
                    The Deep Agent will analyze paper methodology, benchmarks, and limitations, then synthesize an engaging Facebook post.
                    """
                )
                with gr.Row():
                    with gr.Column(scale=3):
                        deep_query = gr.Textbox(
                            label="arXiv Paper URL / ID or Topic",
                            placeholder="e.g. https://arxiv.org/abs/2403.05530 or 'Test-Time Compute in LLMs'",
                            lines=2,
                        )
                    with gr.Column(scale=1):
                        deep_run_btn = gr.Button(
                            "🚀 Run Deep Research", variant="primary", size="lg"
                        )

                with gr.Row():
                    with gr.Column(scale=1):
                        lang_choice = gr.Radio(
                            choices=["English", "Vietnamese (Tiếng Việt)"],
                            value="English",
                            label="Post Language",
                        )
                        style_choice = gr.Dropdown(
                            choices=[
                                "technical_deep_dive",
                                "executive_summary",
                                "viral_breakdown",
                            ],
                            value="technical_deep_dive",
                            label="Facebook Post Style",
                        )
                        auto_pub_checkbox = gr.Checkbox(
                            value=False,
                            label="Auto-publish to Facebook Page immediately",
                            info="If unchecked, you can review and publish with 1 click below.",
                        )
                        deep_model = gr.Dropdown(
                            choices=[
                                "llama3.2:latest",
                                "qwen2.5:7b",
                                "gemini-1.5-flash",
                                "gpt-4o",
                            ],
                            value="llama3.2:latest",
                            label="Reasoning LLM",
                        )

                    with gr.Column(scale=2):
                        status_box = gr.Markdown(
                            value="Waiting to start deep research...", label="Status"
                        )

                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("#### 🧠 In-Depth Scientific Synthesis")
                        synthesis_output = gr.Markdown(value="", height=400)
                    with gr.Column(scale=1):
                        gr.Markdown("#### 📱 Generated Facebook Post")
                        fb_post_output = gr.Textbox(
                            label="Editable Facebook Post", lines=15
                        )
                        fb_link_input = gr.Textbox(
                            label="Attached Link (optional)",
                            placeholder="https://arxiv.org/abs/...",
                        )
                        with gr.Row():
                            publish_btn = gr.Button(
                                "📤 Publish Draft to Facebook", variant="secondary"
                            )
                            pub_status = gr.Label(label="Publishing Status")

                deep_run_btn.click(
                    fn=run_deep_agent_ui,
                    inputs=[
                        deep_query,
                        lang_choice,
                        style_choice,
                        auto_pub_checkbox,
                        deep_model,
                    ],
                    outputs=[synthesis_output, fb_post_output, status_box],
                )

                publish_btn.click(
                    fn=publish_draft_to_facebook_ui,
                    inputs=[fb_post_output, fb_link_input],
                    outputs=[pub_status],
                )

        gr.Markdown(
            """
            ---
            **Note**: Ensure FastAPI server is running (`uvicorn src.main:app --port 8000`).
            Configure `FACEBOOK__PAGE_ID` and `FACEBOOK__PAGE_ACCESS_TOKEN` in `.env` for live Facebook publishing.
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
