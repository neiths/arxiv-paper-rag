import json
import logging
import time
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.dependencies import (
    CacheDep,
    EmbeddingsDep,
    OllamaDep,
    OpenSearchDep,
    SettingsDep,
)
from src.schemas.api.ask import (
    AskRequest,
    AskResponse,
)

logger = logging.getLogger(__name__)

# Two separate routers - one for regular ask, one for streaming
ask_router = APIRouter(tags=["ask"])
stream_router = APIRouter(tags=["stream"])


async def _prepare_chunks_and_sources(
    request: AskRequest,
    opensearch_client,
    embeddings_service,
) -> tuple[list[dict], list[str], list[str]]:
    """Retrieve and prepare chunks for RAG with clean tracing."""

    query_embedding = None
    if request.use_hybrid:
        try:
            query_embedding = await embeddings_service.embed_query(request.query)
            logger.info("Generated query embedding for hybrid search")
        except Exception as e:
            logger.warning(f"Failed to generate embeddings, falling back to BM25: {e}")

    search_results = opensearch_client.search_unified(
        query=request.query,
        query_embedding=query_embedding,
        size=request.top_k,
        categories=request.categories,
        use_hybrid=request.use_hybrid,
    )

    chunks = []
    arxiv_ids = []
    sources_set = set()

    for hit in search_results.get("hits", []):
        arxiv_id = hit.get("arxiv_id", "")

        chunks.append(
            {
                "arxiv_id": arxiv_id,
                "chunk_text": hit.get("chunk_text", hit.get("abstract", "")),
            }
        )

        if arxiv_id:
            arxiv_ids.append(arxiv_id)
            arxiv_id_clean = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
            sources_set.add(f"https://arxiv.org/pdf/{arxiv_id_clean}.pdf")

    return chunks, list(sources_set), arxiv_ids


@ask_router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    settings: SettingsDep,
    opensearch_client: OpenSearchDep,
    embeddings_service: EmbeddingsDep,
    ollama_client: OllamaDep,
    cache_client: CacheDep,
) -> AskResponse:
    """Clean RAG endpoint with essential tracing and exact match caching."""

    start_time = time.time()
    effective_model = settings.ollama_model

    if request.model != effective_model:
        logger.warning(
            "Requested model '%s' is not the configured Ollama model; using '%s' instead",
            request.model,
            effective_model,
        )
        request = request.model_copy(update={"model": effective_model})

    try:
        # Check exact cache first
        cached_response = None
        if cache_client:
            try:
                cached_response = await cache_client.find_cached_response(request)
                if cached_response:
                    logger.info("Returning cached response for exact query match")
                    return cached_response
            except Exception as e:
                logger.warning(f"Cache check failed, proceeding with normal flow: {e}")

        # Generate query embedding for hybrid search if needed
        query_embedding = None

        # Retrieve chunks
        chunks, sources, _ = await _prepare_chunks_and_sources(
            request,
            opensearch_client,
            embeddings_service,
        )

        if not chunks:
            response = AskResponse(
                query=request.query,
                answer="I couldn't find any relevant information in the papers to answer your question.",
                sources=[],
                chunks_used=0,
                search_mode="bm25" if not request.use_hybrid else "hybrid",
            )
            return response

        # Build prompt
        from src.services.ollama.prompts import RAGPromptBuilder

        prompt_builder = RAGPromptBuilder()

        try:
            prompt_data = prompt_builder.create_structured_prompt(request.query, chunks)
            final_prompt = prompt_data["prompt"]
        except Exception:
            final_prompt = prompt_builder.create_rag_prompt(request.query, chunks)

        # Generate answer
        rag_response = await ollama_client.generate_rag_answer(
            query=request.query, chunks=chunks, model=request.model
        )
        answer = rag_response.get("answer", "Unable to generate answer")

        # Prepare response
        response = AskResponse(
            query=request.query,
            answer=answer,
            sources=sources,
            chunks_used=len(chunks),
            search_mode="bm25" if not request.use_hybrid else "hybrid",
        )

        # Store response in exact match cache
        if cache_client:
            try:
                await cache_client.store_response(request, response)
            except Exception as e:
                logger.warning(f"Failed to store response in cache: {e}")

        return response

    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@stream_router.post("/stream")
async def ask_question_stream(
    request: AskRequest,
    settings: SettingsDep,
    opensearch_client: OpenSearchDep,
    embeddings_service: EmbeddingsDep,
    ollama_client: OllamaDep,
    cache_client: CacheDep,
) -> StreamingResponse:
    """Clean streaming RAG endpoint."""

    effective_model = settings.ollama_model

    if request.model != effective_model:
        logger.warning(
            "Requested streaming model '%s' is not the configured Ollama model; using '%s' instead",
            request.model,
            effective_model,
        )
        request = request.model_copy(update={"model": effective_model})

    async def generate_stream():
        start_time = time.time()

        try:
            # Check exact cache first
            if cache_client:
                try:
                    cached_response = await cache_client.find_cached_response(request)
                    if cached_response:
                        logger.info(
                            "Returning cached response for exact streaming query match"
                        )

                        # Send metadata first (same format as non-cached)
                        metadata_response = {
                            "sources": cached_response.sources,
                            "chunks_used": cached_response.chunks_used,
                            "search_mode": cached_response.search_mode,
                        }
                        yield f"data: {json.dumps(metadata_response)}\n\n"

                        # Stream the cached response in chunks
                        for chunk in cached_response.answer.split():
                            yield f"data: {json.dumps({'chunk': chunk + ' '})}\n\n"

                        # Send completion signal with just the final answer
                        yield f"data: {json.dumps({'answer': cached_response.answer, 'done': True})}\n\n"
                        return
                except Exception as e:
                    logger.warning(
                        f"Cache check failed, proceeding with normal flow: {e}"
                    )

            # Retrieve chunks
            chunks, sources, _ = await _prepare_chunks_and_sources(
                request,
                opensearch_client,
                embeddings_service,
            )

            if not chunks:
                yield f"data: {json.dumps({'answer': 'No relevant information found.', 'sources': [], 'done': True})}\n\n"
                return

            # Send metadata first
            search_mode = "bm25" if not request.use_hybrid else "hybrid"
            metadata_response = {
                "sources": sources,
                "chunks_used": len(chunks),
                "search_mode": search_mode,
            }
            yield f"data: {json.dumps(metadata_response)}\n\n"

            # Build prompt
            from src.services.ollama.prompts import RAGPromptBuilder

            prompt_builder = RAGPromptBuilder()
            final_prompt = prompt_builder.create_rag_prompt(request.query, chunks)

            # Stream generation
            full_response = ""
            async for chunk in ollama_client.generate_rag_answer_stream(
                query=request.query, chunks=chunks, model=request.model
            ):
                if chunk.get("response"):
                    text_chunk = chunk["response"]
                    full_response += text_chunk
                    yield f"data: {json.dumps({'chunk': text_chunk})}\n\n"

                if chunk.get("done", False):
                    yield f"data: {json.dumps({'answer': full_response, 'done': True})}\n\n"
                    break

            # Store response in exact match cache
            if cache_client and full_response:
                try:
                    search_mode = "bm25" if not request.use_hybrid else "hybrid"
                    response_to_cache = AskResponse(
                        query=request.query,
                        answer=full_response,
                        sources=sources,
                        chunks_used=len(chunks),
                        search_mode=search_mode,
                    )
                    await cache_client.store_response(request, response_to_cache)
                except Exception as e:
                    logger.warning(f"Failed to store streaming response in cache: {e}")

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
