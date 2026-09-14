# arXiv Paper Curator — RAG System

A production-ready retrieval-augmented generation (RAG) system for academic research papers from arXiv. Ingest papers daily, extract and chunk content with semantic embeddings, search hybrid (BM25 + vectors), and answer research questions with streaming responses powered by local Ollama inference.

## System Status

| Component             | Status | Notes                                                                               |
| --------------------- | ------ | ----------------------------------------------------------------------------------- |
| **Data Ingestion**    | 🟡 85% | Daily arXiv sync, PDF parsing with Docling. Missing: OCR fallback for scanned PDFs. |
| **Storage**           | 🟡 80% | PostgreSQL + OpenSearch indexing. Missing: Backfill pipeline for re-indexing.       |
| **Hybrid Search**     | 🟡 70% | BM25 + vector search with RRF. Missing: Cross-encoder re-ranking layer.             |
| **LLM Generation**    | 🟢 95% | Ollama inference with SSE streaming, source citations.                              |
| **API Layer**         | 🟢 95% | FastAPI endpoints, request caching, health checks.                                  |
| **Client Interface**  | 🟡 75% | Gradio web UI, Telegram bot. Missing: Feedback widgets.                             |
| **Observability**     | 🟡 55% | Langfuse tracing & feedback collection. Missing: RAGAS evals, prompt versioning.    |
| **Training Pipeline** | ⚪ 0%  | Planned Phase 2 enhancement with Amazon SageMaker.                                  |

## Architecture Overview

```mermaid
flowchart TB
    subgraph Data["Data Ingestion (Airflow)"]
        ArxivAPI["arXiv API + Metadata Fetch"]
        PDFParse["PDF Extraction (Docling)"]
        OCRFall["OCR Fallback ❌ MISSING"]
        Chunk["Chunking (Section-Aware)"]
        Embed["Embeddings (Jina API)"]
    end

    subgraph Storage["Storage Layer"]
        PG[("PostgreSQL<br/>(Metadata & Full Text)")]
        OS[("OpenSearch<br/>(Chunks & Vectors)")]
        Backfill["Backfill Pipeline ❌ MISSING"]
    end

    subgraph Retrieval["Retrieval Pipeline"]
        Search["Hybrid Search<br/>(BM25 + Vector)"]
        Filter["Filters<br/>(Category, Latest)"]
        Rerank["Re-ranking ❌ MISSING"]
        Context["Context Builder"]
    end

    subgraph LLM["LLM Generation"]
        Prompt["Prompt Template"]
        Ollama["Ollama Inference"]
        Answer["Answer + Citations"]
    end

    subgraph API["API & Clients"]
        FastAPI["FastAPI Routes<br/>(/ask, /stream, /feedback)"]
        Gradio["Gradio Web UI"]
        Telegram["Telegram Bot"]
    end

    subgraph Observability["Observability (Langfuse)"]
        Traces["Request Traces"]
        Feedback["Feedback Collection"]
        Evals["RAGAS Evals ❌ MISSING"]
    end

    ArxivAPI --> PDFParse
    PDFParse -.->|on error| OCRFall
    PDFParse --> Chunk
    OCRFall --> Chunk
    Chunk --> Embed
    Embed --> PG
    Embed --> OS
    PG -.->|batch| Backfill -.-> OS

    Gradio --> FastAPI
    Telegram --> FastAPI
    FastAPI --> Search
    Search --> Filter
    Filter --> Rerank
    Rerank --> Context
    Context --> Prompt
    Prompt --> Ollama
    Ollama --> Answer
    Answer --> FastAPI

    FastAPI -.-> Traces
    FastAPI -.-> Feedback
    Feedback -.-> Evals

    classDef missing fill:#ffcccc,stroke:#cc0000,stroke-width:2px;
    classDef ready fill:#ccffcc,stroke:#00aa00,stroke-width:2px;
    classDef partial fill:#ffffcc,stroke:#ffaa00,stroke-width:2px;
```

## Key Capabilities

### ✅ Production-Ready Features

**Data Ingestion & Indexing**

- Daily scheduled arXiv API sync (Monday-Friday 6 AM UTC)
- Docling-based PDF extraction with section-aware structure recognition
- Semantic chunking with overlapping sliding windows
- Jina AI embeddings (1024-dim) for dense retrieval
- Batch ingestion via Airflow DAGs with error handling

**Hybrid Search Pipeline**

- BM25 keyword matching for lexical search
- Dense vector search (kNN) for semantic similarity
- OpenSearch Reciprocal Rank Fusion (RRF) combining both signals
- arXiv category filtering (`cs.AI`, `cs.LG`, `cs.CV`, etc.)
- Redis caching for identical queries

**LLM Generation & Streaming**

- Local Ollama inference (bring your own model)
- Server-Sent Events (SSE) streaming for responsive UI
- Source citation with arXiv paper IDs
- Prompt templates with context builder

**API & Client Interfaces**

- FastAPI REST endpoints with async support
- `POST /api/v1/ask` — synchronous RAG answers
- `POST /api/v1/stream` — streaming SSE responses
- `POST /api/v1/ask-agentic` — agentic workflow with query rewriting
- `POST /api/v1/hybrid-search/` — direct chunk retrieval
- `GET /api/v1/health` — service health with component status
- Gradio web UI for interactive querying
- Telegram bot interface for mobile access

**Observability & Tracing**

- Langfuse integration for request tracing
- Trace spans for embedding, search, LLM generation, and agent execution
- User feedback endpoint (`/api/v1/feedback`) for score/comment collection
- Request logging and performance metrics

### 🟡 Partial Implementation

- **Re-ranking Layer** — Currently retrieves top-K directly without cross-encoder re-ranking. Roadmap: Add `BAAI/bge-reranker-base` or Cohere Rerank for precision.
- **Gradio Feedback Widgets** — API endpoint exists but Gradio UI lacks thumbs-up/down buttons.
- **RAGAS Evaluations** — No automated evaluation pipeline; roadmap includes Faithfulness, Answer Relevance, Context Precision metrics.
- **Langfuse Prompt Versioning** — Prompts stored locally; upgrade planned to fetch from Langfuse Prompt Registry.

### ❌ Missing / Roadmap

- **OCR Fallback** — Scanned/image-only PDFs not handled; Docling `do_ocr=False` by default.
- **OpenSearch Backfill Pipeline** — No batch re-indexing when index drops or embedding model upgrades.
- **RAGAS Eval Framework** — Automated quality metrics (Faithfulness, Answer Relevance, Context Precision/Recall).
- **SageMaker Fine-tuning** — Planned Phase 2: use user feedback to fine-tune re-rankers and embeddings.

## Tech Stack

| Layer                | Technology                               |
| -------------------- | ---------------------------------------- |
| **Data Source**      | arXiv API (OAI-PMH / Atom Feed)          |
| **Orchestration**    | Apache Airflow                           |
| **PDF Processing**   | Docling + pytesseract (fallback planned) |
| **Embeddings**       | Jina AI (1024-dim)                       |
| **Search Index**     | OpenSearch (BM25 + kNN RRF)              |
| **Metadata Store**   | PostgreSQL                               |
| **Cache**            | Redis                                    |
| **LLM Inference**    | Ollama (local models)                    |
| **API Framework**    | FastAPI + Uvicorn                        |
| **Web UI**           | Gradio                                   |
| **Observability**    | Langfuse                                 |
| **Containerization** | Docker Compose                           |

## Repository Structure

```
src/
  ├── main.py                          FastAPI application entry point
  ├── config.py                        Environment and config management
  ├── gradio_app.py                    Gradio web UI
  ├── db/
  │   ├── base.py                      Database abstractions
  │   └── factory.py                   Connection factory for PostgreSQL
  ├── models/
  │   ├── paper.py                     Paper metadata ORM model
  │   └── ...
  ├── routers/
  │   ├── ask.py                       POST /api/v1/ask (sync QA)
  │   ├── stream.py                    POST /api/v1/stream (SSE streaming)
  │   ├── hybrid_search.py             POST /api/v1/hybrid-search
  │   ├── feedback.py                  POST /api/v1/feedback
  │   ├── health.py                    GET /api/v1/health
  │   └── agentic.py                   POST /api/v1/ask-agentic
  ├── schemas/
  │   ├── ask_schema.py                Request/response models
  │   ├── feedback_schema.py           Feedback schemas
  │   └── ...
  ├── services/
  │   ├── arxiv/
  │   │   ├── client.py                arXiv OAI-PMH API client
  │   │   └── metadata_fetcher.py      Metadata and PDF download
  │   ├── pdf_parser/
  │   │   └── docling.py               Docling PDF extraction
  │   ├── embeddings/
  │   │   └── jina_client.py           Jina AI embedding API
  │   ├── indexing/
  │   │   ├── text_chunker.py          Section-aware chunking
  │   │   └── opensearch_indexer.py    Bulk indexing to OpenSearch
  │   ├── opensearch/
  │   │   ├── client.py                OpenSearch query & index ops
  │   │   ├── query_builder.py         Hybrid search query construction
  │   │   └── index_config_hybrid.py   RRF pipeline configuration
  │   ├── ollama/
  │   │   ├── client.py                Ollama LLM inference
  │   │   ├── prompts.py               Prompt templates & context builder
  │   │   └── prompts/                 Static prompt files
  │   ├── cache/
  │   │   └── redis_client.py          Redis caching for Q&A pairs
  │   ├── langfuse/
  │   │   └── tracer.py                Langfuse trace instrumentation
  │   └── telegram/                    Telegram bot interface (optional)
  └── utils/
      └── logging.py                   Centralized logging

airflow/
  ├── dags/
  │   ├── arxiv_paper_ingestion.py     Main daily ingestion DAG (Daily 6 AM UTC)
  │   ├── hello_world_dag.py           Example DAG
  │   └── arxiv_backfill_dag.py        Planned: backfill pipeline
  ├── plugins/                         Custom Airflow operators
  ├── Dockerfile                       Airflow container
  ├── requirements.txt                 Airflow Python dependencies
  └── entrypoint.sh                    Airflow startup script

notebooks/
  ├── arxiv_api_testing.ipynb          arXiv API exploration
  ├── docling_testing.ipynb            PDF parsing validation
  ├── ollama_api_testing.ipynb         Local LLM testing
  ├── chunking_testing.ipynb           Chunking strategy validation
  ├── metadata_fetcher.ipynb           Metadata ingestion workflow
  └── storage_connection_testing.ipynb DB & search index connection checks

tests/
  ├── test_arxiv_client.py             arXiv client unit tests
  ├── test_pdf_parser.py               PDF parser tests
  ├── test_opensearch_query_builder.py Hybrid search tests
  ├── test_metadata_fetcher.py         Metadata fetcher tests
  └── conftest.py                      Pytest configuration

docs/
  ├── rag_architecture_gap_analysis.md Detailed gap analysis & roadmap
  ├── Query_Builder_Class_Explanation.md Hybrid search deep dive
  ├── Understanding_Hybrid_Search_Pipeline_Opensearch.md Search pipeline docs
  ├── OpenSearch_Index_Configuration_Explained.md Index setup guide
  ├── langfuse_tracing.md              Observability & tracing guide
  ├── bearer_token_middleware.md       API authentication (planned)
  └── telegram_bot.md                  Telegram interface docs

docker-compose.yaml                    Multi-container orchestration
Dockerfile                             API service container
pyproject.toml                         Python dependencies & build config
README.md                              This file
```

## Prerequisites

### System Requirements

- **Docker Desktop** or Docker Engine with **Docker Compose v2+**
- **Python 3.12** (if running outside Docker)
- **At least 8 GB RAM** (recommended: 16 GB for smooth operation)
- **GPU** (optional, but recommended for faster embeddings and LLM inference)

### Required API Keys & Credentials

- **Jina API Key** — for semantic embeddings ([get from Jina Cloud](https://jina.ai))
- **Langfuse API Key** (optional) — for observability and tracing
- **Ollama models** — at least one model pulled locally (e.g., `ollama pull llama3.2:latest`)

## Configuration & Environment Setup

1. **Copy environment template:**

   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your settings:**

   ```env
   # LLM Configuration
   OLLAMA_HOST=http://localhost:11434
   OLLAMA_MODEL=llama3.2:latest

   # Embeddings
   JINA_API_KEY=your-jina-api-key-here

   # Search & Storage
   OPENSEARCH_HOST=http://localhost:9200
   OPENSEARCH_USER=admin
   OPENSEARCH_PASSWORD=admin
   POSTGRES_DATABASE_URL=postgresql+psycopg2://rag_user:rag_password@localhost:5432/rag_db
   POSTGRES_USER=rag_user
   POSTGRES_PASSWORD=rag_password

   # Cache
   REDIS_HOST=localhost
   REDIS_PORT=6379

   # Observability (optional)
   LANGFUSE_PUBLIC_KEY=your-key
   LANGFUSE_SECRET_KEY=your-secret
   LANGFUSE_HOST=https://cloud.langfuse.com

   # arXiv Ingestion
   ARXIV_FETCH_LIMIT=100
   ARXIV_CATEGORIES=cs.AI,cs.LG,cs.CV,cs.CL

   # Airflow
   PYTHONPATH=/opt/airflow
   AIRFLOW__CORE__DAGS_FOLDER=/opt/airflow/dags
   ```

3. **Important Notes:**
   - **Ollama model name** must match exact tag: `docker exec rag-ollama ollama list`
   - **Airflow DAGs** require `PYTHONPATH=/opt/airflow` for imports
   - **OpenSearch** requires initial admin credentials; change in production
   - **PostgreSQL** database auto-initializes on first run

## Quick Start: Running the Full Stack

### Start All Services

```bash
docker compose up -d
docker compose ps
docker compose logs -f
```

The system performs health checks on all services. Monitor logs for startup completion.

### Access the Services

| Service                   | URL                        | Purpose                             |
| ------------------------- | -------------------------- | ----------------------------------- |
| **Gradio Web UI**         | http://localhost:7860      | Interactive chat interface          |
| **FastAPI API**           | http://localhost:8000      | REST API endpoints                  |
| **API Docs**              | http://localhost:8000/docs | Swagger API documentation           |
| **Airflow DAGs**          | http://localhost:8081      | Workflow orchestration & monitoring |
| **OpenSearch**            | http://localhost:9200      | Search index (REST API)             |
| **OpenSearch Dashboards** | http://localhost:5601      | Index visualization & management    |
| **PostgreSQL** (Adminer)  | http://localhost:8082      | Database browser & query tool       |
| **Ollama**                | http://localhost:11434     | LLM inference endpoint              |

### Stop & Clean Up

```bash
# Stop services, keep volumes
docker compose down

# Remove everything (volumes, data)
docker compose down -v

# Rebuild a single service
docker compose build api
docker compose up -d api
```

## Development: Local Setup (Without Docker)

### Install Dependencies

```bash
# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Install project dependencies
pip install -e .

# Install development/test dependencies
pip install -e ".[dev]"
```

### Run Services Locally

**FastAPI API:**

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

**Gradio UI:**

```bash
python src/gradio_app.py
```

Ensure external services (PostgreSQL, OpenSearch, Ollama, Redis) are running (easiest via `docker compose up -d` for just the backends).

### Running Tests

All tests use mocking for external API calls to avoid rate limiting and ensure reliable test execution.

```bash
# Run all tests
pytest tests/

# Run with coverage report
pytest --cov=src --cov-report=html tests/

# Run specific test categories
pytest tests/unit/ -v        # Fast unit tests
pytest tests/api/ -v         # API endpoint tests
pytest tests/integration/ -v # Integration tests (with mocking)

# Run specific test file
pytest tests/integration/test_services.py -v
```

**Important Notes:**

- All external API calls (arXiv, embeddings, etc.) are mocked to prevent rate limiting
- Tests run offline and don't require API keys or internet connectivity
- Use `pytest -v -s` to see print output and detailed test execution
- See [docs/TESTING.md](docs/TESTING.md) for comprehensive testing guide and troubleshooting

## API Reference

### Health Check

**Endpoint:** `GET /api/v1/health`

```bash
curl http://localhost:8000/api/v1/health
```

**Response:**

```json
{
  "api": "ok",
  "database": "ok",
  "opensearch": "ok",
  "ollama": "ok",
  "redis": "ok"
}
```

### Ask (Synchronous RAG)

**Endpoint:** `POST /api/v1/ask`

Query the RAG system with a synchronous response.

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are transformers in machine learning?",
    "top_k": 5,
    "use_hybrid": true,
    "model": "llama3.2:latest",
    "categories": ["cs.AI", "cs.LG"]
  }'
```

**Response:**

```json
{
  "answer": "Transformers are a neural network architecture...",
  "sources": [
    {
      "arxiv_id": "1706.03762",
      "title": "Attention Is All You Need",
      "chunk": "The transformer architecture was introduced...",
      "score": 0.89
    }
  ],
  "trace_id": "abc123def456",
  "cached": false
}
```

### Stream (Streaming RAG with SSE)

**Endpoint:** `POST /api/v1/stream`

Stream LLM tokens in real-time (Server-Sent Events).

```bash
curl -N -X POST http://localhost:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are transformers in machine learning?",
    "top_k": 5,
    "use_hybrid": true,
    "model": "llama3.2:latest",
    "categories": ["cs.AI", "cs.LG"]
  }'
```

**Response (SSE stream):**

```
data: {"token": "Transformers", "type": "chunk"}
data: {"token": " are", "type": "chunk"}
data: {"token": " a", "type": "chunk"}
data: {"sources": [...], "type": "metadata"}
data: {"trace_id": "xyz789", "type": "complete"}
```

### Hybrid Search (Direct Chunk Retrieval)

**Endpoint:** `POST /api/v1/hybrid-search/`

Retrieve relevant chunks without LLM generation.

```bash
curl -X POST http://localhost:8000/api/v1/hybrid-search/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "neural networks",
    "top_k": 10,
    "categories": ["cs.AI"]
  }'
```

**Response:**

```json
{
  "chunks": [
    {
      "chunk_id": "123",
      "paper_id": "2001.04451",
      "text": "Neural networks are...",
      "bm25_score": 12.5,
      "vector_score": 0.82,
      "final_score": 0.85
    }
  ],
  "total": 42
}
```

### Agentic RAG (Experimental)

**Endpoint:** `POST /api/v1/ask-agentic`

Advanced query processing with query rewriting and document grading.

```bash
curl -X POST http://localhost:8000/api/v1/ask-agentic \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare transformers vs RNNs",
    "top_k": 5,
    "model": "llama3.2:latest"
  }'
```

### Feedback Collection

**Endpoint:** `POST /api/v1/feedback`

Submit user feedback for a query/answer pair (sent to Langfuse).

```bash
curl -X POST http://localhost:8000/api/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "trace_id": "abc123def456",
    "score": 1,
    "comment": "Great answer with relevant papers!"
  }'
```

## Notebooks & Experiments

The `notebooks/` directory contains Jupyter notebooks for testing and validation:

| Notebook                           | Purpose                                                |
| ---------------------------------- | ------------------------------------------------------ |
| `arxiv_api_testing.ipynb`          | Test arXiv OAI-PMH API with filters and pagination     |
| `docling_testing.ipynb`            | Validate PDF parsing output and section extraction     |
| `ollama_api_testing.ipynb`         | Direct Ollama model testing and prompt experimentation |
| `chunking_testing.ipynb`           | Validate chunking strategies (section-aware + overlap) |
| `metadata_fetcher.ipynb`           | End-to-end metadata ingestion workflow simulation      |
| `storage_connection_testing.ipynb` | Verify PostgreSQL, OpenSearch, and Redis connectivity  |

## Ingestion Workflow (Airflow)

### Daily Ingestion DAG

**DAG ID:** `arxiv_paper_ingestion`
**Schedule:** Daily at 6 AM UTC (Monday–Friday)

The DAG performs:

1. Fetch arXiv metadata for papers from configured categories
2. Download PDFs (local cache in `data/arxiv_pdfs/`)
3. Extract text via Docling parser
4. Chunk content with section-aware + overlapping windows
5. Generate Jina embeddings
6. Store metadata in PostgreSQL
7. Bulk index chunks + embeddings into OpenSearch

**Monitor via:**

- Airflow Web UI: http://localhost:8081/dags/arxiv_paper_ingestion
- DAG file: [airflow/dags/arxiv_paper_ingestion.py](airflow/dags/arxiv_paper_ingestion.py)

### Backfill Pipeline (Planned)

A dedicated backfill DAG will enable:

- Bulk re-indexing from PostgreSQL to OpenSearch
- Model upgrades without data loss
- Index recovery after corruption

## Observability & Tracing

### Langfuse Integration

The system traces every request through Langfuse:

**Traced Components:**

- Embedding generation
- Search retrieval (BM25 + vector + RRF scores)
- Prompt construction
- LLM generation
- Agentic workflows

**Enable Tracing:**

1. Sign up for [Langfuse Cloud](https://cloud.langfuse.com)
2. Get API keys: Public Key & Secret Key
3. Set in `.env`:
   ```env
   LANGFUSE_PUBLIC_KEY=pk_...
   LANGFUSE_SECRET_KEY=sk_...
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```
4. Submit feedback via `/api/v1/feedback` to score answers

**View Traces:**

- Visit https://cloud.langfuse.com → Traces
- Filter by query, model, categories
- See performance bottlenecks

### Request Logging

All API requests are logged to stdout and optionally to files (configurable in `src/config.py`).

## Troubleshooting & Common Issues

### API Issues

| Issue                             | Solution                                                                     |
| --------------------------------- | ---------------------------------------------------------------------------- |
| **404 from Ollama**               | Verify `OLLAMA_MODEL` matches output of `docker exec rag-ollama ollama list` |
| **OpenSearch connection refused** | Check `docker compose ps` — ensure opensearch service is healthy             |
| **Jina embeddings API error**     | Confirm `JINA_API_KEY` in `.env` and has API quota remaining                 |
| **Slow responses**                | Check OpenSearch indexing progress; hybrid search scans all chunks first     |

### Ingestion Issues

| Issue                         | Solution                                                      |
| ----------------------------- | ------------------------------------------------------------- |
| **Airflow DAG import errors** | Verify container has `PYTHONPATH=/opt/airflow` set            |
| **PDF parsing fails**         | Check PDF is not corrupted; Docling logs details in task logs |
| **Missing embeddings**        | Ensure Jina API key is valid and rate limits not exceeded     |

### Database Issues

| Issue                             | Solution                                                              |
| --------------------------------- | --------------------------------------------------------------------- |
| **PostgreSQL connection timeout** | Verify `POSTGRES_DATABASE_URL` and check `docker compose ps postgres` |
| **OpenSearch no indexes**         | Run first ingestion DAG or use backfill script (planned)              |
| **Redis connection refused**      | Restart Redis: `docker compose restart redis`                         |

### Performance Tuning

- **Large queries (100+ papers):** Increase OpenSearch JVM heap in `docker-compose.yaml`
- **Slow embeddings:** Use GPU acceleration (`GPU_ENABLED=true` in `.env`) or smaller model
- **Streaming delays:** Reduce `top_k` parameter or use smaller Ollama model

## Development Roadmap

### Phase 1 — Current (MVP + Observability)

- ✅ Core RAG: Ingestion, Hybrid Search, LLM Generation
- ✅ API & UI: FastAPI, Gradio, basic monitoring
- 🟡 Feedback & Tracing: Langfuse integration, user ratings
- ❌ OCR Fallback: For scanned PDFs (planned)
- ❌ Backfill Pipeline: PostgreSQL ↔ OpenSearch sync (planned)

### Phase 2 — Search Quality Enhancement

- 📋 Cross-Encoder Re-ranking: Semantic re-scoring of top candidates
- 📋 Temporal Filtering: "Latest papers" date-aware search
- 📋 RAGAS Evaluations: Automated quality metrics
- 📋 Langfuse Prompt Registry: Dynamic prompt versioning

### Phase 3 — Training & MLOps (Future)

- 📋 Amazon SageMaker: Fine-tune re-rankers and embeddings
- 📋 Feedback Loop: User ratings → training dataset
- 📋 Model Registry: Version control for embedding/re-ranking models
- 📋 A/B Testing: Compare retrieval and generation strategies

### Phase 4 — Advanced Features (Experimental)

- 📋 Multi-turn conversations with memory
- 📋 Citation-aware fact checking
- 📋 Paper summarization & comparison
- 📋 Semantic Scholar integration

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make changes and run tests: `pytest tests/`
4. Commit with clear messages
5. Push to your fork and open a Pull Request

## Support & Documentation

- **Testing Guide**: [docs/TESTING.md](docs/TESTING.md) — Running tests, handling API rate limits, mocking strategies
- **Gap Analysis & Architecture**: [docs/rag_architecture_gap_analysis.md](docs/rag_architecture_gap_analysis.md)
- **Hybrid Search Deep Dive**: [docs/Query_Builder_Class_Explanation.md](docs/Query_Builder_Class_Explanation.md)
- **OpenSearch Configuration**: [docs/OpenSearch_Index_Configuration_Explained.md](docs/OpenSearch_Index_Configuration_Explained.md)
- **Langfuse Tracing**: [docs/langfuse_tracing.md](docs/langfuse_tracing.md)
- **Telegram Bot Setup**: [docs/telegram_bot.md](docs/telegram_bot.md)

For issues, feature requests, or questions, open an issue on GitHub or consult the documentation files above.

## License

No license has been specified yet.
