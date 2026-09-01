FROM python:3.12-slim

# Set environment variables
ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW_VERSION=2.10.3
ENV PYTHON_VERSION=3.12
ENV CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libgl1 \
        libglib2.0-0 \
        libpq-dev \
        poppler-utils \
        tesseract-ocr \
        && rm -rf /var/lib/apt/lists/*

# Create airflow user with UID/GID 50000 for cross-platform compatibility
RUN groupadd -r -g 50000 airflow && useradd -r -u 50000 -g airflow -d ${AIRFLOW_HOME} -s /bin/bash airflow

# Create airflow directories with proper ownership
RUN mkdir -p ${AIRFLOW_HOME} && \
    mkdir -p ${AIRFLOW_HOME}/dags && \
    mkdir -p ${AIRFLOW_HOME}/logs && \
    mkdir -p ${AIRFLOW_HOME}/plugins && \
    chown -R 50000:50000 ${AIRFLOW_HOME} && \
    chmod -R 755 ${AIRFLOW_HOME}

# Install uv for fast, reliable package installations with parallel downloads & retry
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install Airflow with PostgreSQL support
RUN uv pip install --system \
    "apache-airflow[postgres]==${AIRFLOW_VERSION}" \
    --constraint "${CONSTRAINT_URL}" \
    psycopg2-binary

# Copy requirements and install project dependencies with CUDA PyTorch support
COPY requirements.txt /tmp/requirements.txt
RUN uv pip install --system --torch-backend cu124 -r /tmp/requirements.txt

# Copy and set up entrypoint script
COPY entrypoint.sh /entrypoint.sh
# Fix line endings (convert CRLF to LF) and set executable permissions
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Switch to airflow user and set working directory
USER airflow
WORKDIR ${AIRFLOW_HOME}

# Expose port
EXPOSE 8080

CMD ["/entrypoint.sh"]
