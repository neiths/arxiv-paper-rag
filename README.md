# arxiv-paper-rag

# Docker Compose & Airflow Setup Guide

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Services Explained](#services-explained)
- [Running the Stack](#running-the-stack)
- [Testing Individual Components](#testing-individual-components)
- [Airflow Deep Dive](#airflow-deep-dive)
- [Troubleshooting](#troubleshooting)

---

## Overview

This project uses **Docker Compose** to orchestrate a complete RAG (Retrieval-Augmented Generation) system with Apache Airflow for workflow orchestration. The stack includes:

- **API Service**: FastAPI backend for the RAG application
- **PostgreSQL**: Relational database for structured data and Airflow metadata
- **OpenSearch**: Vector search engine for document embeddings
- **OpenSearch Dashboards**: UI for OpenSearch visualization
- **Ollama**: Local LLM inference server
- **Apache Airflow**: Workflow orchestration for data pipelines

---

## Architecture

### Network Configuration

All services run on a **bridge network** called `rag-network`, enabling inter-service communication using container names as hostnames.

### Data Persistence

The following Docker volumes ensure data persists across container restarts:

| Volume | Purpose |
|--------|---------|
| `postgres_data` | PostgreSQL database files |
| `opensearch_data` | OpenSearch indices and data |
| `ollama_data` | Downloaded LLM models |
| `airflow_logs` | Airflow task execution logs |

---

## Services Explained

### 1. **API Service** (`rag-api`)

**Purpose**: Main FastAPI application providing RAG functionality

**Configuration**:
- **Port**: `8000:8000`
- **Build Context**: Root directory (`.`)
- **Dependencies**: Waits for PostgreSQL and OpenSearch to be healthy
- **Health Check**: HTTP GET to `/api/v1/health`

**Environment Variables**:
```bash
OPENSEARCH_HOST=http://opensearch:9200
OLLAMA_HOST=http://ollama:11434
POSTGRES_DATABASE_URL=postgresql+psycopg2://rag_user:rag_password@postgres:5432/rag_db
```

### Test API Service

```bash
# 1. Start dependencies first
docker compose up -d postgres opensearch ollama

# 2. Start API service
docker compose up -d api

# 3. Check health endpoint
curl http://localhost:8000/api/v1/health

# 4. View API logs
docker compose logs -f api
```

---

### 2. **PostgreSQL** (`rag-postgres`)

**Purpose**: Primary database for application data and Airflow metadata

**Configuration**:
- **Image**: `postgres:16-alpine`
- **Port**: `5432:5432`
- **Database**: `rag_db`
- **User**: `rag_user`
- **Password**: `rag_password`

**Health Check**: `pg_isready` command checks database availability

### Test PostgreSQL

```bash
# 1. Start only PostgreSQL
docker compose up -d postgres

# 2. Connect to database
docker exec -it rag-postgres psql -U rag_user -d rag_db

# 3. Run a test query
SELECT version();

# list all databases
\l

# check connect to a specific database
\c rag_db

# check extensions
\dx

# create vector extension
CREATE EXTENSION IF NOT EXISTS vector;

# check extensions again
\dx vector

# 4. Exit
\q
```

---

### 3. **OpenSearch** (`rag-opensearch`)

**Purpose**: Vector search engine for document embeddings and semantic search

**Configuration**:
- **Image**: `opensearchproject/opensearch:2.19.0`
- **Ports**: `9200` REST API (search, index, vector queries), `9600` performance metrics
- **Mode**: Single-node cluster
- **Security**: Disabled for development (`DISABLE_SECURITY_PLUGIN=true`)

**Memory Settings**:
- Java heap: 512MB min/max (`-Xms512m -Xmx512m`)
- Memory lock: Unlimited (prevents swapping)

rule of thumb:
- Heap size should be set to 50% of available RAM, but not exceed 32GB.

**discovery.type**: Set to `single-node` for standalone operation

**disable_security_plugin**: Set to `true` to disable security features for local development

**bootstrap.memory_lock**: Set to `true` to prevent memory swapping, improving performance

- OpenSearch runs on java (JVM) that java stores its data in RAM (heap memory). 
- If the OS starts swapping memory to disk, it can severely degrade performance.
- **Memory locking** is dangerous if abused, so a process could lock all RAM. that limit is controlled by ulimit settings.

**ulimit settings**: Configured to allow unlimited memory locking and increase file descriptors for better performance

- `ulimit` = how much the OS allows a process to use or lock

    | Value  | Meaning              |
    | ------ | -------------------- |
    | `soft` | Default usable limit |
    | `hard` | Absolute max limit   |
    | `-1`   | Unlimited            |

### Test OpenSearch

```bash
# 1. Start OpenSearch
docker compose up -d opensearch

# 2. Check cluster health
curl http://localhost:9200/_cluster/health?pretty

# 3. List indices
curl http://localhost:9200/_cat/indices?v

# 4. Create a test index
curl -X PUT http://localhost:9200/test-index

# PowerShell
iwr -Method PUT -Uri "http://localhost:9200/test-index"

# 5. Delete test index
curl -X DELETE http://localhost:9200/test-index

# PowerShell
iwr -Method DEL -Uri "http://localhost:9200/test-index"
```

---

### 4. **OpenSearch Dashboards** (`rag-dashboards`)

**Purpose**: Web UI for visualizing and managing OpenSearch data

**Configuration**:
- **Image**: `opensearchproject/opensearch-dashboards:2.19.0`
- **Port**: `5601:5601`
- **Connected to**: `opensearch:9200`

**Access**: http://localhost:5601

### Test OpenSearch Dashboards

```bash
# 1. Start OpenSearch and Dashboards
docker compose up -d opensearch opensearch-dashboards

# 2. Access UI
# Open browser to: http://localhost:5601

# 3. Check status via API
curl http://localhost:5601/api/status
```

---

### 5. **Ollama** (`rag-ollama`)

**Purpose**: Local LLM inference server for running open-source models

**Configuration**:
- **Image**: `ollama/ollama:0.11.2`
- **Port**: `11434:11434`
- **Models Storage**: Persisted in `ollama_data` volume

**Health Check**: `ollama list` command

### Test Ollama

```bash
# 1. Start Ollama
docker compose up -d ollama

# 2. List available models
docker exec -it rag-ollama ollama list

# 3. Pull a model (example: smollm2) - small model for testing
docker exec -it rag-ollama ollama pull smollm2:135m

# 4. Test inference
docker exec -it rag-ollama ollama run smollm2:135m "Hello, how are you?"

# 5. Check API
curl http://localhost:11434/api/tags
```

---

### 6. **Apache Airflow** (`rag-airflow`)

**Purpose**: Orchestrate data pipelines, PDF processing, and arXiv paper fetching

**Configuration**:
- **Build Context**: `./airflow`
- **Port**: `8081:8080` (mapped to avoid conflict with default 8080)
- **User**: UID/GID `50000` (configurable via `user` parameter)
- **Dependencies**: PostgreSQL (for metadata), OpenSearch, API

**Volumes**:
```yaml
- ./airflow/dags:/opt/airflow/dags          # DAG definitions
- airflow_logs:/opt/airflow/logs            # Task logs
- ./airflow/plugins:/opt/airflow/plugins    # Custom plugins
- ./src:/opt/airflow/src                    # Shared source code
```

**Access**: http://localhost:8081
**Credentials**: `admin` / `admin` (set in `entrypoint.sh`)

### Test Airflow

```bash
# 1. Start dependencies
docker compose up -d postgres opensearch

# 2. Start Airflow
docker compose up -d airflow

# 3. Watch initialization logs
docker compose logs -f airflow

# 4. Access web UI
# Open browser to: http://localhost:8081
# Login: admin / admin

# 5. Test CLI access
docker exec -it rag-airflow airflow version

# 6. List DAGs
docker exec -it rag-airflow airflow dags list

# 7. Trigger test DAG
docker exec -it rag-airflow airflow dags trigger hello_world_week1
```

---

## Running the Stack

### Prerequisites

- Docker Desktop or Docker Engine installed
- Docker Compose v2+
- At least 4GB RAM available for containers

### Full Stack Startup

```bash
# 1. Start all services
docker compose up -d

# 2. Check service status
docker compose ps

# 3. View logs for all services
docker compose logs -f

# 4. View logs for a specific service
docker compose logs -f airflow
```

### Service Startup Order

Docker Compose automatically handles dependencies with health checks:

1. **PostgreSQL** starts first (required by API and Airflow)
2. **OpenSearch** starts in parallel
3. **Ollama** starts independently
4. **OpenSearch Dashboards** waits for OpenSearch
5. **API** waits for PostgreSQL and OpenSearch
6. **Airflow** waits for PostgreSQL, OpenSearch, and optionally API

### Shutdown

```bash
# Stop all services (keeps data)
docker compose down

# Stop and remove volumes (deletes all data)
docker compose down -v
```

## Quick Reference

### Common Commands

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Rebuild specific service
docker compose build airflow

# Restart service
docker compose restart airflow

# View logs
docker compose logs -f airflow

# Execute command in container
docker exec -it rag-airflow bash

# Check service health
docker compose ps
```

---


### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f airflow

# Last N lines
docker compose logs --tail=100 airflow

# With timestamps
docker compose logs -f -t airflow
```

### Resetting Everything

```bash
# Stop and remove containers, networks
docker compose down

# Remove all volumes (deletes data)
docker compose down -v

# Remove images (force rebuild)
docker compose down --rmi all

# Start fresh
docker compose up -d --build
```

---

### Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| **Airflow Web UI** | http://localhost:8081 | admin / admin |
| **API** | http://localhost:8000 | N/A |
| **OpenSearch** | http://localhost:9200 | N/A |
| **OpenSearch Dashboards** | http://localhost:5601 | N/A |
| **Ollama** | http://localhost:11434 | N/A |
| **PostgreSQL** | `localhost:5432` | rag_user / rag_password |

### Database Connection String

```
postgresql://rag_user:rag_password@localhost:5432/rag_db
```

From within containers:
```
postgresql://rag_user:rag_password@postgres:5432/rag_db
```

---

## Next Steps

1. **Explore Airflow UI**: http://localhost:8081
2. **Trigger Test DAG**: Run `hello_world_week1` to verify setup
3. **Create Custom DAGs**: Add new workflow files to `airflow/dags/`
4. **Monitor Logs**: Watch execution with `docker compose logs -f`
5. **Scale Up**: Add more workers or services as needed

For more details, see:
- [Airflow Documentation](https://airflow.apache.org/docs/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [OpenSearch Documentation](https://opensearch.org/docs/)
