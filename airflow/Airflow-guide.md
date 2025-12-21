## Airflow Deep Dive

### Directory Structure

```
airflow/
├── Dockerfile             # Custom Airflow image
├── entrypoint.sh          # Initialization script
├── requirements.txt       # Python dependencies
├── README.md              # Airflow-specific docs
├── init-db.sql            # Database setup (if needed)
├── dags/                  # DAG definitions
│   └── hello_world_dag.py # Test DAG
└── plugins/               # Custom operators/hooks
```

### Dockerfile Breakdown

The Airflow Dockerfile (`airflow/Dockerfile`) performs:

1. **Base Image**: Python 3.12 slim
2. **System Dependencies**: Build tools, PostgreSQL libs, Poppler (PDF), Tesseract (OCR)
3. **Airflow Installation**: Version 2.10.3 with PostgreSQL support
4. **User Setup**: Creates `airflow` user (UID/GID 50000)
5. **Project Dependencies**: Installs from `requirements.txt`
6. **Entrypoint**: Copies and executes `entrypoint.sh`

### Entrypoint Script (`entrypoint.sh`)

The entrypoint script handles:

1. **Cleanup**: Kills existing Airflow processes and removes stale PID files
2. **Database Init**: Runs `airflow db init` to create metadata tables
3. **Admin User**: Creates `admin/admin` user (idempotent)
4. **Service Start**: Launches webserver (daemon) and scheduler (foreground)

> **Note**: The script now uses Unix line endings (LF) to prevent the "no such file or directory" error on Linux containers.

### Python Dependencies

From `requirements.txt`:

| Package | Purpose |
|---------|---------|
| `httpx` | HTTP client for API calls |
| `sqlalchemy` | Database ORM |
| `pydantic` | Data validation |
| `docling` | PDF processing |
| `opensearch-py` | OpenSearch client |
| `psycopg2-binary` | PostgreSQL driver |

### Sample DAG: Hello World

The `hello_world_dag.py` demonstrates:

**Tasks**:
1. **hello_world**: Prints a test message
2. **check_services**: Verifies connectivity to API and PostgreSQL

**Schedule**: Manual trigger only (`schedule=None`)

**Tags**: `week1`, `testing`

**Running the DAG**:
```bash
# Via CLI
docker exec -it rag-airflow airflow dags trigger hello_world_week1

# Via Web UI
# 1. Go to http://localhost:8081
# 2. Find "hello_world_week1" DAG
# 3. Click play button
```

### Airflow Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `AIRFLOW_HOME` | `/opt/airflow` | Airflow installation directory |
| `PYTHONPATH` | `/opt/airflow/src` | Include shared source code |
| `POSTGRES_DATABASE_URL` | `postgresql+psycopg2://...` | Database connection |
| `OPENSEARCH_HOST` | `http://opensearch:9200` | Search engine endpoint |
| `OLLAMA_HOST` | `http://ollama:11434` | LLM server endpoint |

### Creating New DAGs

1. **Create DAG file** in `airflow/dags/`:

```python
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

def my_task():
    print("My custom task")

with DAG(
    'my_dag',
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
) as dag:
    task = PythonOperator(
        task_id='my_task',
        python_callable=my_task,
    )
```

2. **Wait for auto-detection** (Airflow scans `dags/` every 30 seconds)

3. **Trigger via UI or CLI**

### Accessing Shared Code

DAGs can import from `src/` directory:

```python
# In your DAG
import sys
sys.path.insert(0, '/opt/airflow/src')

from your_module import your_function
```

The `src/` directory is mounted as a volume: `./src:/opt/airflow/src`

---



## Troubleshooting

### Issue: Airflow Entrypoint Error

**Error**: `exec /entrypoint.sh: no such file or directory`

**Cause**: Windows line endings (CRLF) in `entrypoint.sh`

**Solution**: Script has been fixed with Unix line endings (LF). Rebuild:
```bash
docker compose build airflow
docker compose up -d airflow
```

### Issue: Port Already in Use

**Error**: `Bind for 0.0.0.0:8080 failed: port is already allocated`

**Solution**: Change port mapping in `compose.yml`:
```yaml
ports:
  - "8081:8080"  # Use 8081 instead of 8080
```

### Issue: Services Not Connecting

**Symptoms**: API can't reach PostgreSQL, Airflow can't reach OpenSearch

**Solution**: Ensure all services are on the same network:
```bash
docker network ls
docker network inspect arxiv-paper-curator_rag-network
```

### Issue: Airflow Scheduler Not Running

**Symptoms**: DAGs don't execute even when triggered

**Debug**:
```bash
# Check scheduler logs
docker compose logs -f airflow | grep scheduler

# Restart Airflow
docker compose restart airflow

# Check scheduler process
docker exec -it rag-airflow ps aux | grep scheduler
```

### Issue: OpenSearch Memory Errors

**Error**: `max virtual memory areas vm.max_map_count [65530] is too low`

**Solution**: Increase memory limits (Linux/WSL):
```bash
sudo sysctl -w vm.max_map_count=262144
```

For Docker Desktop (Mac/Windows): Increase Docker memory to at least 4GB in settings.

### Issue: Volume Permission Denied

**Symptoms**: Airflow can't write logs, PostgreSQL can't create files

**Solution**: Check volume permissions:
```bash
# Linux/WSL: Set proper ownership
sudo chown -R 50000:50000 ./airflow/logs

# Or uncomment user line in compose.yml for Airflow
```
