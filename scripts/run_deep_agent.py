#!/usr/bin/env python3
"""Deep Research & Facebook Publisher CLI Tool.

Usage examples:
    # Research a specific paper by arXiv URL in Vietnamese:
    python scripts/run_deep_agent.py --query "https://arxiv.org/abs/2403.05530" --lang vi

    # Research a topic by keyword in English with automatic Facebook publishing:
    python scripts/run_deep_agent.py --query "Test-Time Compute in Large Language Models" --lang en --auto-publish

    # Custom model (e.g. Gemini or Ollama Qwen):
    python scripts/run_deep_agent.py --query "2403.05530" --model "llama3.2:latest"
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings  # noqa: E402
from src.services.agents.deep_research.factory import (
    make_deep_research_service,
)  # noqa: E402
from src.services.arxiv.factory import make_arxiv_client  # noqa: E402
from src.services.facebook.factory import make_facebook_service  # noqa: E402
from src.services.pdf_parser.factory import make_pdf_parser_service  # noqa: E402


async def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Deep Research Agent for arXiv papers and Facebook publishing."
    )
    parser.add_argument(
        "--query",
        "-q",
        required=True,
        help="arXiv paper URL, ID (e.g., '2403.05530'), or research topic string.",
    )
    parser.add_argument(
        "--lang",
        "-l",
        default="en",
        choices=["en", "vi"],
        help="Target language for the social media post: 'en' (English) or 'vi' (Vietnamese). Default: 'en'.",
    )
    parser.add_argument(
        "--style",
        "-s",
        default="technical_deep_dive",
        choices=["technical_deep_dive", "executive_summary", "viral_breakdown"],
        help="Style/tone for Facebook post. Default: 'technical_deep_dive'.",
    )
    parser.add_argument(
        "--auto-publish",
        "--auto-publis",
        action="store_true",
        default=None,
        help="Automatically publish the generated post to Facebook Page via Meta Graph API.",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=None,
        help="LLM model override (e.g. 'llama3.2:latest', 'qwen2.5:7b', 'gemini-1.5-flash').",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("🔬 DEEP RESEARCH & FACEBOOK PUBLISHER AGENT")
    print("=" * 80)
    print(f"Query:        {args.query}")
    print(f"Language:     {'Vietnamese' if args.lang == 'vi' else 'English'}")
    print(f"Post Style:   {args.style}")
    print(f"Auto-Publish: {args.auto_publish}")
    if args.model:
        print(f"Model:        {args.model}")
    print("=" * 80)

    settings = get_settings()

    # Initialize dependencies
    arxiv_client = make_arxiv_client()
    pdf_parser = make_pdf_parser_service()
    facebook_service = make_facebook_service(settings)

    deep_research_service = make_deep_research_service(
        settings=settings,
        arxiv_client=arxiv_client,
        pdf_parser=pdf_parser,
        facebook_service=facebook_service,
    )

    print("\n🚀 Executing Deep Research workflow...\n")
    result = await deep_research_service.run_research(
        query=args.query,
        language=args.lang,
        post_style=args.style,
        auto_publish=args.auto_publish,
        model_name=args.model,
    )

    if not result.get("success"):
        print("\n❌ Deep Research encountered an error:")
        print(result.get("error"))
        print("\nExecution Logs:")
        for log in result.get("logs", []):
            print(f"  • {log}")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("📑 PAPERS ANALYZED")
    print("=" * 80)
    for p in result.get("papers", []):
        print(f"• [{p.get('arxiv_id')}] {p.get('title')}")
        print(f"  URL: {p.get('abs_url')}")
        print(f"  Authors: {', '.join(p.get('authors', [])[:3])}")

    print("\n" + "=" * 80)
    print("🧠 DEEP RESEARCH SYNTHESIS REPORT")
    print("=" * 80)
    print(result.get("synthesis_report"))

    print("\n" + "=" * 80)
    print("📱 GENERATED FACEBOOK POST")
    print("=" * 80)
    print(result.get("facebook_post"))
    print("=" * 80)

    if result.get("published_to_facebook"):
        print("\n🎉 POST PUBLISHED TO FACEBOOK!")
        print(f"Post ID:  {result.get('facebook_post_id')}")
        if result.get("facebook_post_url"):
            print(f"Post URL: {result.get('facebook_post_url')}")
    elif result.get("publish_error"):
        print(f"\n⚠️ Facebook Publishing failed: {result.get('publish_error')}")
        print(
            "Your deep research synthesis report and Facebook post draft are preserved above."
        )
    else:
        print("\n[INFO] Post was NOT published to Facebook (auto-publish disabled).")
        print("Draft is preserved above and can be copied or published via API.")

    print(f"\n⏱️ Total elapsed time: {result.get('duration_seconds')}s")


if __name__ == "__main__":
    asyncio.run(main())
