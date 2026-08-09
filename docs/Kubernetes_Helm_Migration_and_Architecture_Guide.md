# Comprehensive Kubernetes & Helm Migration Guide

This document explains the Kubernetes (K8s) architecture, Helm chart design, and local deployment strategy created for the **arXiv Paper RAG** system. It serves as an educational guide to help you transition from Docker Compose to Kubernetes.

---

## Table of Contents

1. [Docker Compose vs. Kubernetes Concepts](#1-docker-compose-vs-kubernetes-concepts)
2. [Helm Chart Architecture Overview](#2-helm-chart-architecture-overview)
3. [Kubernetes Resource Types Explained](#3-kubernetes-resource-types-explained)
   - [Deployments vs. StatefulSets](#deployments-vs-statefulsets)
   - [ConfigMaps vs. Secrets](#configmaps-vs-secrets)
   - [Services & Networking](#services--networking)
   - [Persistent Volume Claims (PVCs)](#persistent-volume-claims-pvcs)
4. [Deep Dive into Service Manifests](#4-deep-dive-into-service-manifests)
5. [Local Development Lifecycle with Kind & Helm](#5-local-development-lifecycle-with-kind--helm)
6. [Essential Debugging & Operations Cheat Sheet](#6-essential-debugging--operations-cheat-sheet)

---

## 1. Docker Compose vs. Kubernetes Concepts

When migrating from Docker Compose to Kubernetes, concepts map as follows:

| Docker Compose Concept         | Kubernetes / Helm Equivalent                     | Explanation                                                                                    |
| :----------------------------- | :----------------------------------------------- | :--------------------------------------------------------------------------------------------- |
| `docker-compose.yaml`          | **Helm Chart** (`helm/arxiv-paper-rag`)          | Package manager & template bundle defining your entire multi-service application.              |
| `service:`                     | **Deployment** or **StatefulSet** + **Service**  | K8s separates workload execution (`Deployment`/`StatefulSet`) from network access (`Service`). |
| `environment:` / `env_file:`   | **ConfigMap** & **Secret**                       | Configuration data and sensitive credentials are store separately from container specs.        |
| `volumes:`                     | **PersistentVolumeClaim (PVC)**                  | Requests persistent disk storage from the cluster storage provisioner.                         |
| `ports:`                       | **Service (ClusterIP / NodePort)**               | Controls network access inside and outside the cluster.                                        |
| `depends_on:` + `healthcheck:` | **Liveness / Readiness Probes** & InitContainers | K8s continuously checks container health rather than relying on static startup order.          |

---

## 2. Helm Chart Architecture Overview

The generated Helm chart is structured as a **Unified Umbrella Chart**:

```
helm/arxiv-paper-rag/
├── Chart.yaml              # Chart metadata (Name, Version, AppVersion)
├── values.yaml             # Single source of truth for configurable parameters
├── README.md               # Quickstart guide
└── templates/
    ├── _helpers.tpl        # Reusable Go template snippets (labels, names)
    ├── configmap.yaml      # Cluster-wide non-sensitive settings
    ├── secret.yaml         # Encrypted/Opaque credentials & API keys
    ├── api.yaml            # FastAPI application
    ├── postgres.yaml       # Main PostgreSQL DB
    ├── redis.yaml          # Redis cache
    ├── opensearch.yaml     # OpenSearch hybrid vector DB
    ├── opensearch-dashboards.yaml # OpenSearch UI
    ├── ollama.yaml         # Ollama LLM service
    ├── adminer.yaml        # Adminer DB management UI
    ├── airflow.yaml        # Apache Airflow orchestrator
    ├── clickhouse.yaml     # ClickHouse DB for Langfuse analytics
    ├── langfuse-postgres.yaml   # Langfuse PostgreSQL instance
    ├── langfuse-redis.yaml      # Langfuse Redis instance
    ├── langfuse-minio.yaml      # Langfuse MinIO object storage
    ├── langfuse-web.yaml        # Langfuse Web UI
    └── langfuse-worker.yaml     # Langfuse Background worker
```

### Key Components

- **`Chart.yaml`**: Standard metadata file identifying the chart name, version (`0.1.0`), and API version (`v2`).
- **`values.yaml`**: Defines default values for image repositories, tags, ports, feature flags (`enabled: true`), and storage sizes. You can override any value at runtime using `--set key=value`.
- **`templates/_helpers.tpl`**: Contains reusable functions, such as `arxiv-paper-rag.fullname` and `arxiv-paper-rag.labels`, ensuring consistent resource naming and standard Kubernetes labels across all components.

---

## 3. Kubernetes Resource Types Explained

### Deployments vs. StatefulSets

- **`Deployment`**: Used for **stateless** applications (e.g., `api`, `adminer`, `airflow`, `langfuse-web`, `langfuse-worker`, `redis`).
  - Pods can be created, restarted, or rescheduled on any node without worrying about local persistent disk identity.
  - Scaling up or down is instant.

- **`StatefulSet`**: Used for **stateful** databases and stores (e.g., `postgres`, `opensearch`, `ollama`, `clickhouse`, `langfuse-postgres`, `langfuse-minio`).
  - Provides stable, unique network identifiers (e.g., `pod-0`, `pod-1`).
  - Uses `volumeClaimTemplates` to provision persistent storage dedicated to each specific replica.

### ConfigMaps vs. Secrets

- **`ConfigMap` (`templates/configmap.yaml`)**:
  Stores non-sensitive variables such as search parameters (`ARXIV__MAX_RESULTS`), host URLs (`OPENSEARCH_HOST`), chunk sizes, and debug flags.

- **`Secret` (`templates/secret.yaml`)**:
  Stores sensitive strings such as database passwords (`POSTGRES_PASSWORD`), encryption keys (`LANGFUSE_ENCRYPTION_KEY`), and external API keys (`JINA_API_KEY`).
  > **Note**: In Helm templates, values are injected via `stringData` or base64-encoded `data`.

### Services & Networking

Kubernetes Pods are assigned ephemeral IP addresses that change on restart. A **Service** provides a permanent IP and DNS name inside the cluster.

- **`ClusterIP` (Default)**: Exposes the service on an internal cluster IP (e.g., `arxiv-paper-rag-postgres:5432`). Pods inside the cluster communicate using this internal DNS name.
- **`NodePort`**: Exposes the service on each Kubernetes node's IP at a static port (in the range 30000–32767). Used in local dev environments like Kind to map host ports directly to cluster services.

### Persistent Volume Claims (PVCs)

Rather than hardcoding local host paths (`./data:/data`), Kubernetes uses **Storage Classes** and **PVCs**. When a `StatefulSet` requests storage:

1. It submits a `PersistentVolumeClaim`.
2. The cluster's storage provisioner (e.g., Kind's built-in `standard` / `local-path-provisioner`) automatically creates a `PersistentVolume` (PV) on disk and binds it to the pod.

---

## 4. Deep Dive into Service Manifests

### OpenSearch Special Handling (InitContainers)

Elasticsearch/OpenSearch requires Linux kernel memory settings (`vm.max_map_count >= 262144`) to function properly. In `templates/opensearch.yaml`, an **`initContainer`** runs before OpenSearch starts:

```yaml
initContainers:
  - name: init-sysctl
    image: busybox:latest
    command: ["sysctl", "-w", "vm.max_map_count=262144"]
    securityContext:
      privileged: true
```

This guarantees that the node settings are adjusted automatically when the pod boots.

### Health Probes (Liveness & Readiness)

In Kubernetes, health checks are split into two complementary probes:

- **`readinessProbe`**: Determines if the pod is ready to accept user traffic. If it fails, traffic is routed away from the pod.
- **`livenessProbe`**: Determines if the container is alive. If it fails, Kubernetes kills the container and starts a fresh instance.

Example from `api.yaml`:

```yaml
readinessProbe:
  httpGet:
    path: /api/v1/health
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 10
```

---

## 5. Local Development Lifecycle with Kind & Helm

### How Kind Works with Local Images

When developing locally without pushing images to Docker Hub or Docker Registry:

1. Docker builds the local image:
   ```bash
   docker build -t arxiv-rag-api:0.1.0 .
   ```
2. Kind copies the image directly into the internal container runtime of the Kind control-plane node:
   ```bash
   kind load docker-image arxiv-rag-api:0.1.0 --name arxiv-rag-cluster
   ```
3. Kubernetes sets `imagePullPolicy: IfNotPresent` to use the loaded local image without attempting a network download.

### Running the Automated Script

The repository includes a script [`scripts/kind-setup.sh`](file:///home/thienhb/Workspace/arxiv-paper-rag/scripts/kind-setup.sh) that automates this workflow end-to-end:

```bash
./scripts/kind-setup.sh
```

---

## 6. Essential Debugging & Operations Cheat Sheet

Here are common commands for inspecting, debugging, and managing your Kubernetes cluster and Helm deployments:

### Inspecting Pods & Workloads

```bash
# View all pods in namespace with status and restart count
kubectl get pods -n arxiv-rag

# Watch pod status changes in real-time
kubectl get pods -n arxiv-rag -w

# View detailed information, events, and failure reasons for a pod
kubectl describe pod <pod-name> -n arxiv-rag
```

### Viewing Logs

```bash
# View live logs for a container
kubectl logs -f deployment/arxiv-paper-rag-api -n arxiv-rag

# View logs from a specific container in a multi-container or stateful pod
kubectl logs statefulset/arxiv-paper-rag-opensearch -n arxiv-rag

# Inspect previous container logs (if the pod crashed)
kubectl logs <pod-name> -n arxiv-rag --previous
```

### Accessing Containers

```bash
# Open an interactive bash shell inside a running pod
kubectl exec -it deployment/arxiv-paper-rag-api -n arxiv-rag -- /bin/bash

# Run a quick psql query inside PostgreSQL
kubectl exec -it statefulset/arxiv-paper-rag-postgres -n arxiv-rag -- psql -U rag_user -d rag_db
```

### Managing Helm Releases

```bash
# List installed Helm releases
helm list -n arxiv-rag

# Re-render templates locally to inspect generated YAML
helm template arxiv-paper-rag ./helm/arxiv-paper-rag

# Upgrade release after updating values.yaml or templates
helm upgrade arxiv-paper-rag ./helm/arxiv-paper-rag -n arxiv-rag

# Completely remove the application stack
helm uninstall arxiv-paper-rag -n arxiv-rag
```
