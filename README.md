# arXiv Paper Curator

A full-stack retrieval-augmented generation (RAG) system for arXiv papers. The project ingests papers, extracts PDF content, indexes chunks in OpenSearch, and answers questions with an Ollama-backed LLM.

## What This Project Does

- Fetches arXiv papers and caches PDFs locally
- Parses scientific PDFs with Docling
- Chunks and indexes paper content in OpenSearch
- Supports BM25, vector, and hybrid search
- Answers questions through a FastAPI RAG API
- Streams answers through an SSE endpoint
- Caches exact question/answer pairs in Redis
- Provides a Gradio UI for interactive querying
- Orchestrates ingestion and helper workflows with Airflow
- Includes notebook-based Ollama testing and API experiments

## Architecture

```mermaid
flowchart LR
  U[User] --> G[Gradio UI]
  U --> A[FastAPI API]
  G --> A
  A --> R[Redis Cache]
  A --> O[OpenSearch Hybrid Index]
  A --> L[Ollama]
  A --> J[Jina Embeddings API]
  O --> P[PostgreSQL]
  A --> P
  AF[Airflow DAGs] --> X[arXiv API]
  AF --> D[PDF Parser / Docling]
  AF --> O
  X --> C[Local PDF Cache]
  D --> O
```

## Key Features

### RAG API

- `POST /api/v1/ask` for standard question answering
- `POST /api/v1/stream` for streaming answers
- `POST /api/v1/hybrid-search/` for direct search over indexed chunks
- `GET /api/v1/health` for service health checks

### Search

- BM25 search for keyword matching
- Vector search using Jina embeddings
- Native hybrid search with OpenSearch RRF pipeline
- Category filters for arXiv tags such as `cs.AI` and `cs.LG`
- Exact-match cache keys include query, model, top_k, hybrid mode, and categories

### LLM and UI

- Ollama generation for answer synthesis
- Gradio chat UI for interactive testing
- Streamed responses with source metadata
- Notebook helper for testing Ollama directly

### Ingestion and Workflow

- ArXiv API client for metadata and paper discovery
- Local PDF caching
- Docling-based PDF parsing
- Airflow DAGs for ingestion and workflow automation

## Tech Stack

- FastAPI
- PostgreSQL
- Redis
- OpenSearch
- Ollama
- Jina AI embeddings
- Docling
- Airflow
- Gradio

## Repository Layout

```text
src/
  main.py                 FastAPI app entry point
  routers/                API routes for ask, hybrid search, health
  services/               OpenSearch, Ollama, embeddings, cache, arXiv, PDF parsing
  schemas/                Request and response models
  db/                     Database abstractions and factories
airflow/
  dags/                   Airflow workflows and helper modules
notebooks/
  ollama_api_testing.ipynb Notebook for local Ollama validation
  arxiv_api_testing.ipynb  Notebook for arXiv API experiments
  docling_testing.ipynb    Notebook for PDF parsing checks
```

## Prerequisites

- Docker Desktop or Docker Engine
- Docker Compose v2+
- Python 3.12 if you want to run the app locally outside Docker
- A Jina API key for hybrid search
- At least one Ollama model pulled locally

## Configuration

Copy `.env.example` to `.env` and adjust the values for your machine.

Important settings:

- `OLLAMA_HOST=http://localhost:11434`
- `OLLAMA_MODEL=llama3.2:latest`
- `OPENSEARCH_HOST=http://localhost:9200`
- `POSTGRES_DATABASE_URL=postgresql+psycopg2://rag_user:rag_password@localhost:5432/rag_db`
- `JINA_API_KEY=...`

Notes:

- The Ollama model name must match the exact tag shown by `docker exec rag-ollama ollama list`.
- The Airflow container expects `PYTHONPATH=/opt/airflow` so DAG helpers can import `src.*`.
- The API and Gradio UI default to `llama3.2:latest`.

## Run The Full Stack

```bash
docker compose up -d
docker compose ps
docker compose logs -f
```

### Main Services

- API: http://localhost:8000
- Airflow: http://localhost:8081
- OpenSearch: http://localhost:9200
- OpenSearch Dashboards: http://localhost:5601
- Ollama: http://localhost:11434
- Adminer: http://localhost:8082

### Useful Commands

```bash
# Stop services but keep volumes
docker compose down

# Remove volumes and reset data
docker compose down -v

# Rebuild one service
docker compose build api

# Start only the core runtime services
docker compose up -d postgres opensearch redis ollama
```

## Run Locally Without Docker

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1
```

For the Gradio UI:

```bash
python src/gradio_app.py
```

## API Endpoints

### Health

```bash
curl http://localhost:8000/api/v1/health
```

Returns database, OpenSearch, and Ollama status.

### Ask

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are transformers in machine learning?",
    "top_k": 3,
    "use_hybrid": true,
    "model": "llama3.2:latest",
    "categories": ["cs.AI", "cs.LG"]
  }'
```

### Streaming Ask

```bash
curl -N -X POST http://localhost:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are transformers in machine learning?",
    "top_k": 3,
    "use_hybrid": true,
    "model": "llama3.2:latest",
    "categories": ["cs.AI", "cs.LG"]
  }'
```

### Hybrid Search

```bash
curl -X POST http://localhost:8000/api/v1/hybrid-search/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning neural networks",
    "size": 10,
    "use_hybrid": true,
    "categories": ["cs.AI", "cs.LG"]
  }'
```

## Ollama Model Check

If you want to confirm which models are installed:

```bash
curl http://localhost:11434/api/tags
```

If the model list shows only `llama3.2:latest`, that is the tag the app should use.

## Notebooks

The notebook [notebooks/ollama_api_testing.ipynb](notebooks/ollama_api_testing.ipynb) demonstrates how to test Ollama directly from Python.

Other notebooks cover arXiv API calls, chunking, Docling parsing, and storage connection checks.

## Airflow

Airflow is used for ingestion and workflow automation.

- DAGs live in `airflow/dags/`
- Helper modules live in `airflow/dags/arxiv_ingestion/`
- Custom plugins live in `airflow/plugins/`
- Shared app code is mounted into the Airflow container at `/opt/airflow/src`

Example DAGs included in the repo:

- `hello_world_dag.py`
- `arxiv_paper_ingestion.py`

## Troubleshooting

- If the API returns a 404 from Ollama, check `OLLAMA_MODEL` and the exact tag in `ollama list`.
- If the API cannot connect to OpenSearch, confirm `docker compose ps` shows the cluster healthy.
- If Airflow imports fail, verify the container is using `PYTHONPATH=/opt/airflow`.
- If hybrid search is degraded, confirm the Jina API key is present and valid.
- If cached answers look stale, clear the Redis volume or restart the cache service.

## License

No license has been specified yet.
