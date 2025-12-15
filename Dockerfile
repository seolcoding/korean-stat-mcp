# KOSIS MCP Server - Production Dockerfile
# Multi-stage build for smaller image size

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.12-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency files first (cache layer)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.12-slim as runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY src/ src/

# Note: Metadata is now loaded into PostgreSQL, not from JSON files
# kosis_data/ directory is no longer needed

# Create artifact directories
RUN mkdir -p /app/artifacts/charts /app/artifacts/reports /app/artifacts/data \
    && chown -R appuser:appuser /app

# Environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Default environment (can be overridden)
ENV FASTMCP_STATELESS_HTTP=true
ENV ARTIFACT_STORAGE=auto

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: HTTP server with uvicorn
CMD ["uvicorn", "mcp_server.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2"]
