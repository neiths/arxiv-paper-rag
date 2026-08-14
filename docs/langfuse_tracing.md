# Langfuse Observability & Tracing in arXiv Paper Curator

This document provides a comprehensive guide to the **Langfuse v3** observability and tracing architecture implemented in the arXiv Paper Curator RAG system. It covers the self-hosted infrastructure in `docker-compose.yaml`, the service layer design in `src/services/langfuse/`, dependency injection in `src/dependencies.py`, and how distributed tracing is applied across the RAG query and streaming pipelines in `src/routers/ask.py`.

---

## 1. Why Observability & Tracing for RAG?

Retrieval-Augmented Generation (RAG) systems involve multi-step pipelines combining embedding generation, hybrid vector/lexical retrieval, prompt compilation, and large language model (LLM) inference. Without deep observability, diagnosing issues like slow queries, irrelevant context retrieval, prompt truncation, or hallucinated responses becomes extremely difficult.

**Langfuse** is an open-source LLM engineering platform that provides:

- **Nested Tracing**: Hierarchical visualization of every step in the RAG execution path (root request -> query embedding -> OpenSearch retrieval -> prompt formatting -> Ollama generation).
- **Latency & Bottleneck Detection**: Granular execution timing across external API calls (Jina embeddings), database lookups (OpenSearch), and local LLM inference (Ollama).
- **Token & Cost Accounting**: Automatic extraction of prompt tokens, completion tokens, and total token usage.
- **Payload & Metadata Capture**: Logging input queries, top-$k$ retrieved arXiv chunks, paper IDs, prompt previews, model parameters, and final answers.
- **User Feedback & Evaluation**: Ability to score traces and collect feedback for offline evaluation and continuous prompt refinement.

---

## 2. System Architecture & Trace Hierarchy

The tracing architecture is organized hierarchically so that each user request creates a single root trace containing sequential child spans and generations:

```mermaid
flowchart TD
    subgraph Client["Client Interaction"]
        User["User / Gradio UI"] -->|POST /api/v1/ask or /stream| API["FastAPI Application"]
    end

    subgraph TraceTree["Langfuse Trace Hierarchy"]
        Root["Root Trace: api_user (Query, Session, Metadata)"]
        Span1["Span: query_embedding (Timing, Query length)"]
        Span2["Span: search_retrieval (Top-K, Chunks, Paper IDs)"]
        Span3["Span: prompt_construction (Chunk count, Prompt length)"]
        Span4["Generation: llm_generation (Model, Prompt, Tokens, Latency)"]

        Root --> Span1
        Root --> Span2
        Root --> Span3
        Root --> Span4
    end

    subgraph Storage["Langfuse v3 Self-Hosted Stack"]
        API -->|Async Event Batches| Web["langfuse-web (:3001)"]
        Web --> Worker["langfuse-worker (:3030)"]
        Worker --> Redis["langfuse-redis (:6380)"]
        Worker --> Postgres["langfuse-postgres (:5433)"]
        Worker --> ClickHouse["ClickHouse (:8123 / :9000)"]
        Worker --> MinIO["langfuse-minio (:9090 / :9091)"]
    end
```

---

## 3. Infrastructure: Docker Compose Setup

Langfuse v3 uses a high-performance distributed architecture separating web ingestion, asynchronous background processing, analytical storage (ClickHouse), relational metadata (PostgreSQL), task queuing (Redis), and blob storage (MinIO).

All components are defined in [docker-compose.yaml](file:///home/thienhb/Workspace/arxiv-paper-rag/docker-compose.yaml).

### 3.1 Services Breakdown

| Service             | Container Name          | Image / Version                            | Host Port                | Purpose                                                |
| :------------------ | :---------------------- | :----------------------------------------- | :----------------------- | :----------------------------------------------------- |
| `langfuse-web`      | `rag-langfuse-web`      | `langfuse/langfuse:3`                      | `3001:3000`              | UI Dashboard & ingestion HTTP API                      |
| `langfuse-worker`   | `rag-langfuse-worker`   | `langfuse/langfuse-worker:3`               | `3030:3030`              | Asynchronous event processing, worker jobs             |
| `clickhouse`        | `rag-clickhouse`        | `clickhouse/clickhouse-server:24.8-alpine` | Internal (8123/9000)     | OLAP columnar database for high-volume trace analytics |
| `langfuse-postgres` | `rag-langfuse-postgres` | `postgres:17`                              | `5433:5432`              | Relational database for projects, users, and metadata  |
| `langfuse-redis`    | `rag-langfuse-redis`    | `redis:7`                                  | `6380:6379`              | Queue and cache for ingestion and worker coordination  |
| `langfuse-minio`    | `rag-langfuse-minio`    | `minio/minio`                              | `9090:9000`, `9091:9001` | S3-compatible storage for raw trace events and media   |

### 3.2 Docker Compose Configuration Highlights

```yaml
# ClickHouse for Langfuse analytics
clickhouse:
  image: clickhouse/clickhouse-server:24.8-alpine
  container_name: rag-clickhouse
  environment:
    - CLICKHOUSE_DB=langfuse
    - CLICKHOUSE_USER=langfuse
    - CLICKHOUSE_PASSWORD=langfuse
  volumes:
    - clickhouse_data:/var/lib/clickhouse
  networks:
    - rag-network

# Langfuse Web UI & Ingestion Server
langfuse-web:
  image: docker.io/langfuse/langfuse:3
  container_name: rag-langfuse-web
  depends_on:
    langfuse-postgres: { condition: service_healthy }
    langfuse-minio: { condition: service_healthy }
    langfuse-redis: { condition: service_healthy }
    clickhouse: { condition: service_healthy }
  ports:
    - "3001:3000"
  environment:
    NEXTAUTH_URL: http://localhost:3001
    NEXTAUTH_SECRET: ${LANGFUSE_NEXTAUTH_SECRET}
    DATABASE_URL: postgresql://langfuse:langfuse@langfuse-postgres:5432/langfuse
    SALT: ${LANGFUSE_SALT}
    ENCRYPTION_KEY: ${LANGFUSE_ENCRYPTION_KEY}
    CLICKHOUSE_URL: http://clickhouse:8123
    LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://langfuse-minio:9000
    REDIS_HOST: langfuse-redis
    REDIS_AUTH: ${LANGFUSE_REDIS_PASSWORD}
    LANGFUSE_INIT_ORG_NAME: "RAG Organization"
    LANGFUSE_INIT_PROJECT_NAME: "Agentic RAG"
    LANGFUSE_INIT_USER_EMAIL: "admin@example.com"
    LANGFUSE_INIT_USER_PASSWORD: "admin123"
```

---

## 4. Configuration & Environment Variables

The application manages Langfuse configuration using Pydantic Settings in [src/config.py](file:///home/thienhb/Workspace/arxiv-paper-rag/src/config.py#L110-L128).

### 4.1 Client Configuration (`LangfuseSettings`)

These settings control how the Python SDK client communicates with the Langfuse server:

```python
class LangfuseSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="LANGFUSE__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    public_key: str = ""
    secret_key: str = ""
    host: str = "http://localhost:3000"  # Self-hosted Langfuse URL (or http://localhost:3001)
    enabled: bool = True
    flush_at: int = 15                  # Batch size before automatic background flush
    flush_interval: float = 1.0         # Seconds between automatic flushes
    max_retries: int = 3
    timeout: int = 30
    debug: bool = False
```

### 4.2 `.env` Configuration Variables

Add the following to your `.env` file (see [.env.example](file:///home/thienhb/Workspace/arxiv-paper-rag/.env.example#L60-L77)):

```bash
# ==============================================================================
# Langfuse SDK Tracing Configuration (Python Client)
# ==============================================================================
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://localhost:3001
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
LANGFUSE_FLUSH_AT=15
LANGFUSE_FLUSH_INTERVAL=1.0
LANGFUSE_DEBUG=false

# ==============================================================================
# Langfuse Server Configuration (Docker Compose)
# ==============================================================================
LANGFUSE_NEXTAUTH_SECRET=changeme-v3-nextauth-secret-min-32-chars-recommended
LANGFUSE_SALT=changeme-v3-salt-min-32-chars-recommended-for-security
LANGFUSE_ENCRYPTION_KEY=0000000000000000000000000000000000000000000000000000000000000000
LANGFUSE_REDIS_PASSWORD=langfuse_redis_password
LANGFUSE_MINIO_ACCESS_KEY=langfuse_minio
LANGFUSE_MINIO_SECRET_KEY=langfuse_minio_secret
```

---

## 5. Service Layer Implementation

The Langfuse integration is structured into three files under `src/services/langfuse/`:

```
src/services/langfuse/
├── __init__.py
├── client.py       # LangfuseTracer: Low-level SDK v3 client wrapper
├── factory.py      # make_langfuse_tracer(): Singleton factory with caching
└── tracer.py       # RAGTracer: Domain-specific context managers for RAG steps
```

### 5.1 Low-Level Wrapper: `LangfuseTracer`

Defined in [src/services/langfuse/client.py](file:///home/thienhb/Workspace/arxiv-paper-rag/src/services/langfuse/client.py), `LangfuseTracer` wraps the official `langfuse.Langfuse` client and provides clean abstractions for spans, generations, feedback, and callbacks.

#### Key Methods:

1. **Initialization (`__init__`)**:
   Safely initializes the Langfuse v3 client when `enabled=True` and valid credentials are provided. If disabled or credentials are missing, it falls back to a graceful no-op state without throwing runtime exceptions.

2. **Spans (`start_span` / `update_span`)**:
   Context manager for tracing non-LLM operations (e.g. document retrieval, query rewrites, preprocessing).

   ```python
   with tracer.start_span(name="retrieve_papers", input_data={"query": q}) as span:
       docs = retrieve(...)
       tracer.update_span(span, output={"docs_count": len(docs)})
   ```

3. **Generations (`start_generation` / `update_generation`)**:
   Context manager designed specifically for LLM calls. Tracks prompts, completions, model names, latency, and token usage (`prompt_tokens`, `completion_tokens`, `total_tokens`).

   ```python
   with tracer.start_generation(name="llm_rag", model="llama3.2", input_data=prompt) as gen:
       response = await llm.generate(...)
       tracer.update_generation(gen, output=response, usage_metadata={"prompt_tokens": 150, "completion_tokens": 80})
   ```

4. **LangChain / LangGraph Callback (`get_callback_handler` / `trace_langgraph_agent`)**:
   Provides `langfuse.langchain.CallbackHandler` for seamless automatic tracing when using LangChain/LangGraph runnables.

5. **Feedback & Scoring (`submit_feedback`)**:
   Allows attaching numerical scores (`0.0` - `1.0`), evaluation names, and comments to any existing `trace_id`.

6. **Flushing & Teardown (`flush` / `shutdown`)**:
   Flushes buffered events across network boundaries and cleans up background worker threads.

### 5.2 Singleton Factory: `make_langfuse_tracer`

Defined in [src/services/langfuse/factory.py](file:///home/thienhb/Workspace/arxiv-paper-rag/src/services/langfuse/factory.py), this function uses `@lru_cache(maxsize=1)` to ensure that only a single instance of `LangfuseTracer` is instantiated and reused across the application lifecycle:

```python
from functools import lru_cache
from src.config import get_settings
from src.services.langfuse.client import LangfuseTracer

@lru_cache(maxsize=1)
def make_langfuse_tracer() -> LangfuseTracer:
    settings = get_settings()
    return LangfuseTracer(settings)
```

### 5.3 Domain-Specific RAG Tracer: `RAGTracer`

Defined in [src/services/langfuse/tracer.py](file:///home/thienhb/Workspace/arxiv-paper-rag/src/services/langfuse/tracer.py), `RAGTracer` acts as a clean, domain-tailored adapter on top of `LangfuseTracer`. It provides intuitive context managers matching each phase of the RAG pipeline.

| Method                                            | Context / Action     | Captured Metadata                                                  |
| :------------------------------------------------ | :------------------- | :----------------------------------------------------------------- |
| `trace_request(user_id, query)`                   | Root Context Manager | `user_id`, `session_id`, `query`, auto-flush on exit               |
| `trace_embedding(trace, query)`                   | Span Context Manager | `query`, `query_length`, `embedding_duration_ms`, `success` status |
| `trace_search(trace, query, top_k)`               | Span Context Manager | `query`, `top_k` requested                                         |
| `end_search(span, chunks, arxiv_ids, total_hits)` | Span Update & Close  | `chunks_returned`, `unique_papers`, `total_hits`, `arxiv_ids` list |
| `trace_prompt_construction(trace, chunks)`        | Span Context Manager | `chunk_count` input                                                |
| `end_prompt(span, prompt)`                        | Span Update & Close  | `prompt_length`, `prompt_preview` (first 200 chars)                |
| `trace_generation(trace, model, prompt)`          | Span Context Manager | `model`, `prompt_length`, full `prompt`                            |
| `end_generation(span, response, model)`           | Span Update & Close  | `response`, `response_length`, `model_used`                        |
| `end_request(trace, response, total_duration)`    | Trace Finalization   | `answer`, `total_duration_seconds`, `response_length`              |

---

## 6. FastAPI Dependency Injection

The tracer is integrated into FastAPI's dependency injection system in [src/dependencies.py](file:///home/thienhb/Workspace/arxiv-paper-rag/src/dependencies.py#L80-L95).

```python
from src.services.langfuse.client import LangfuseTracer
from src.services.langfuse.factory import make_langfuse_tracer

def get_langfuse_tracer(request: Request) -> LangfuseTracer:
    """Get Langfuse tracer from the request state or factory singleton."""
    return getattr(request.app.state, "langfuse_tracer", None) or make_langfuse_tracer()

# Type alias for route annotations
LangfuseDep = Annotated[LangfuseTracer, Depends(get_langfuse_tracer)]
```

### Benefits of this Pattern:

- **Clean Route Signatures**: Routers simply declare `langfuse_tracer: LangfuseDep` without manual instantiation.
- **Easy Mocking in Tests**: Can be overridden in unit/integration tests via `app.dependency_overrides[get_langfuse_tracer] = lambda: mock_tracer`.
- **Zero Overhead when Disabled**: If `LANGFUSE_ENABLED=false`, the client no-ops gracefully without altering route logic.

---

## 7. Pipeline Tracing in Action

The tracing integration is implemented inside the ask and streaming routers in [src/routers/ask.py](file:///home/thienhb/Workspace/arxiv-paper-rag/src/routers/ask.py).

### 7.1 Standard RAG Endpoint (`POST /api/v1/ask`)

The standard `/ask` endpoint traces every step from request receipt to final output:

```python
@ask_router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    settings: SettingsDep,
    opensearch_client: OpenSearchDep,
    embeddings_service: EmbeddingsDep,
    ollama_client: OllamaDep,
    cache_client: CacheDep,
    langfuse_tracer: LangfuseDep,
) -> AskResponse:
    rag_tracer = RAGTracer(langfuse_tracer)
    start_time = time.time()

    # 1. Start Root Request Trace
    with rag_tracer.trace_request("api_user", request.query) as trace:

        # Exact cache lookup
        if cache_client:
            cached_response = await cache_client.find_cached_response(request)
            if cached_response:
                return cached_response

        # 2. Retrieve Chunks (Embeddings + OpenSearch)
        chunks, sources, _ = await _prepare_chunks_and_sources(
            request, opensearch_client, embeddings_service, rag_tracer, trace
        )

        # 3. Prompt Construction Span
        with rag_tracer.trace_prompt_construction(trace, chunks) as prompt_span:
            prompt_builder = RAGPromptBuilder()
            final_prompt = prompt_builder.create_rag_prompt(request.query, chunks)
            rag_tracer.end_prompt(prompt_span, final_prompt)

        # 4. LLM Generation Span
        with rag_tracer.trace_generation(trace, request.model, final_prompt) as gen_span:
            rag_response = await ollama_client.generate_rag_answer(
                query=request.query, chunks=chunks, model=request.model
            )
            answer = rag_response.get("answer", "Unable to generate answer")
            rag_tracer.end_generation(gen_span, answer, request.model)

        # 5. Finalize Root Trace
        rag_tracer.end_request(trace, answer, time.time() - start_time)

        return response
```

### 7.2 Hybrid Retrieval Tracing (`_prepare_chunks_and_sources`)

Inside `_prepare_chunks_and_sources`, both vector embedding and hybrid search are instrumented as distinct child spans:

```python
# Embedding Span
if request.use_hybrid:
    with rag_tracer.trace_embedding(trace, request.query) as embedding_span:
        try:
            query_embedding = await embeddings_service.embed_query(request.query)
        except Exception as e:
            if embedding_span:
                rag_tracer.tracer.update_span(
                    embedding_span, output={"success": False, "error": str(e)}
                )

# OpenSearch Retrieval Span
with rag_tracer.trace_search(trace, request.query, request.top_k) as search_span:
    search_results = opensearch_client.search_unified(
        query=request.query,
        query_embedding=query_embedding,
        size=request.top_k,
        categories=request.categories,
        use_hybrid=request.use_hybrid,
    )
    # Extract chunks & papers
    ...
    rag_tracer.end_search(search_span, chunks, arxiv_ids, search_results.get("total", 0))
```

### 7.3 Streaming Endpoint (`POST /api/v1/stream`)

The streaming endpoint handles Server-Sent Events (SSE) while maintaining a complete trace lifecycle:

1. Opens the root trace context when the stream generator begins.
2. Traces embedding, OpenSearch retrieval, and prompt construction.
3. Wraps the asynchronous chunk generator in the `llm_generation` span.
4. Finalizes the root trace (`rag_tracer.end_request()`) once all tokens have streamed to the client.

---

## 8. Step-by-Step Setup & Verification Guide

Follow these steps to run the complete stack and verify your traces in Langfuse:

### Step 1: Start the Infrastructure

Start all core services including OpenSearch, Ollama, PostgreSQL, Redis, and the Langfuse cluster:

```bash
docker compose up -d
```

Verify that all containers are healthy:

```bash
docker compose ps
```

### Step 2: Access the Langfuse Web Dashboard

1. Open your browser and navigate to:
   ```
   http://localhost:3001
   ```
2. Log in with the default bootstrapped administrator credentials:
   - **Email**: `admin@example.com`
   - **Password**: `admin123`
3. If logging in for the first time, navigate to **Settings** > **API Keys**.
4. Click **Create New API Keys**.
5. Copy the generated **Public Key** (`pk-lf-...`) and **Secret Key** (`sk-lf-...`).

### Step 3: Configure `.env`

Update your project's `.env` file with your credentials:

```ini
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://localhost:3001
LANGFUSE_PUBLIC_KEY=pk-lf-your-actual-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-actual-secret-key
LANGFUSE_FLUSH_AT=15
LANGFUSE_FLUSH_INTERVAL=1.0
LANGFUSE_DEBUG=false
```

### Step 4: Run the API

If running outside Docker:

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 5: Execute a Test Query

Send a RAG query to the API:

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are transformer attention mechanisms?",
    "top_k": 3,
    "use_hybrid": true,
    "model": "llama3.2:latest",
    "categories": ["cs.AI"]
  }'
```

Or test the streaming endpoint:

```bash
curl -N -X POST http://localhost:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain attention mechanisms in transformers",
    "top_k": 3,
    "use_hybrid": true,
    "model": "llama3.2:latest"
  }'
```

### Step 6: Inspect Traces in Langfuse

1. Return to the Langfuse Web UI at `http://localhost:3001`.
2. Click on **Tracing** > **Traces** in the left sidebar.
3. You will see your request named `api_user` with:
   - **Waterfall View**: Exact timeline showing duration of embedding vs. search vs. prompt building vs. generation.
   - **Spans**: `query_embedding`, `search_retrieval`, `prompt_construction`.
   - **Generation**: `llm_generation` containing the prompt and LLM completion.
   - **Metadata**: Retrieved arXiv IDs, chunk counts, search mode (`hybrid` or `bm25`), and latency in milliseconds.

---

## 9. Best Practices & Production Considerations

### 9.1 Non-Blocking Error Handling

Tracing is designed to be completely non-intrusive. If Langfuse becomes unreachable or encounters network timeout issues, tracing calls fail silently without interrupting the user's RAG request.

### 9.2 Event Flushing

The Langfuse Python SDK uses background worker threads to batch events asynchronously.

- In production, set `LANGFUSE_FLUSH_AT=15` and `LANGFUSE_FLUSH_INTERVAL=1.0` to balance network overhead and trace delivery speed.
- In local development or testing, explicit flushes (`rag_tracer.tracer.flush()`) ensure events are visible in the dashboard immediately.

### 9.3 Handling Exact-Match Cache Hits

When a response is served directly from the Redis cache, the search and LLM generation phases are bypassed. You can observe cache hits in Langfuse as traces that finish in sub-millisecond durations without child generation spans.

### 9.4 Data Retention & Volume Management

Langfuse v3 stores high-volume trace analytics in ClickHouse and large payloads/media in MinIO. Persistent volumes configured in Docker Compose ensure data is preserved across container restarts:

- `clickhouse_data`
- `langfuse_v3_postgres_data`
- `langfuse_v3_minio_data`

---

## 10. Summary

The Langfuse integration provides end-to-end visibility into the arXiv Paper Curator RAG system:

- **`docker-compose.yaml`**: Full self-hosted Langfuse v3 stack (Web, Worker, ClickHouse, Postgres, Redis, MinIO).
- **`src/services/langfuse/client.py`**: Clean, robust SDK v3 client wrapper with fallback handling.
- **`src/services/langfuse/tracer.py`**: Purpose-built RAG tracing adapter capturing embeddings, OpenSearch retrieval, prompt construction, and Ollama generation.
- **`src/dependencies.py`**: FastAPI dependency injection via `LangfuseDep`.
- **`src/routers/ask.py`**: Instrumentation of both synchronous and streaming RAG endpoints.
