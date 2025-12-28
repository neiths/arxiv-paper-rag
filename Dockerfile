# Build stage - use UV for fast dependency installation
FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS builder

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Configure UV for optimal build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Install dependencies with cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Copy application source
COPY src /app/src

# Final stage - minimal runtime image
FROM python:3.12.8-slim AS final

# Metadata labels
ARG VERSION=0.1.0
LABEL maintainer="nieths.huynh@gmail.com" \
      version="${VERSION}" \
      description="RAG API Service for Arxiv Paper Processing"

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    APP_VERSION=${VERSION} \
    WORKERS=4 \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

# Create non-root user for security
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1000 appuser && \
    chown -R appuser:appuser /app

# Copy application and virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/papers').read()" || exit 1

# Expose application port
EXPOSE 8000

# Run the application with configurable workers
CMD uvicorn src.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers ${WORKERS}
