# arXiv Paper RAG - Kubernetes Helm Chart

This umbrella Helm chart packages all microservices and infrastructure components for local development and testing on Kubernetes (e.g., **Kind**, Minikube, k3d).

## Stack Overview

- **App Services**:
  - `api`: FastAPI RAG Application Server (Port 8000)
  - `airflow`: Apache Airflow Workflow Engine (Port 8080)
  - `adminer`: PostgreSQL DB Admin UI (Port 8080)
- **Infrastructure Data Stores**:
  - `postgres`: PostgreSQL 16 DB (Port 5432)
  - `redis`: Redis 7 Cache (Port 6379)
  - `opensearch`: OpenSearch 2.19.0 Vector & Text Search (Port 9200)
  - `opensearch-dashboards`: OpenSearch UI (Port 5601)
  - `ollama`: Ollama LLM Runtime (Port 11434)
- **Observability / Tracing (Langfuse v3)**:
  - `clickhouse`: Analytics Database (Port 8123 / 9000)
  - `langfuse-postgres`: PostgreSQL 17 for Langfuse (Port 5432)
  - `langfuse-redis`: Dedicated Redis instance (Port 6379)
  - `langfuse-minio`: S3-compatible Blob Storage (Ports 9000 / 9001)
  - `langfuse-web`: Langfuse Web UI (Port 3000)
  - `langfuse-worker`: Background Job Engine (Port 3030)

---

## Quickstart with Kind (Kubernetes in Docker)

Run the automated setup script:

```bash
./scripts/kind-setup.sh
```

This script will:

1. Provision a local Kind cluster (`arxiv-rag-cluster`) with port mappings.
2. Build local Docker images (`arxiv-rag-api:0.1.0` and `arxiv-rag-airflow:latest`).
3. Load images into Kind.
4. Deploy the Helm release in namespace `arxiv-rag`.

---

## Manual Helm Deployment

### 1. Build and load images into Kind

```bash
docker build -t arxiv-rag-api:0.1.0 .
docker build -t arxiv-rag-airflow:latest ./airflow

kind load docker-image arxiv-rag-api:0.1.0 --name arxiv-rag-cluster
kind load docker-image arxiv-rag-airflow:latest --name arxiv-rag-cluster
```

### 2. Install the Chart

```bash
kubectl create namespace arxiv-rag

helm install arxiv-paper-rag ./helm/arxiv-paper-rag \
  --namespace arxiv-rag
```

### 3. Check Pod Status

```bash
kubectl get pods -n arxiv-rag -w
```

---

## Accessing Services via Port Forwarding

If NodePort mappings are not configured on your cluster, use `kubectl port-forward`:

```bash
# FastAPI RAG API
kubectl port-forward svc/arxiv-paper-rag-api 8000:8000 -n arxiv-rag

# OpenSearch Dashboards
kubectl port-forward svc/arxiv-paper-rag-opensearch-dashboards 5601:5601 -n arxiv-rag

# Airflow Web UI
kubectl port-forward svc/arxiv-paper-rag-airflow 8081:8080 -n arxiv-rag

# Langfuse Web UI
kubectl port-forward svc/arxiv-paper-rag-langfuse-web 3001:3000 -n arxiv-rag

# MinIO Console
kubectl port-forward svc/arxiv-paper-rag-langfuse-minio 9091:9001 -n arxiv-rag

# Adminer PostgreSQL UI
kubectl port-forward svc/arxiv-paper-rag-adminer 8082:8080 -n arxiv-rag
```

---

## Useful Helm Operations

```bash
# Upgrade chart after making changes
helm upgrade arxiv-paper-rag ./helm/arxiv-paper-rag -n arxiv-rag

# Uninstall chart
helm uninstall arxiv-paper-rag -n arxiv-rag

# Render manifests without applying (dry run)
helm template arxiv-paper-rag ./helm/arxiv-paper-rag
```
