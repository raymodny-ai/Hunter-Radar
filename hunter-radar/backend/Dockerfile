# Hunter Radar V1.6.0 — Multi-stage Dockerfile
# Build: docker build -t hunter-radar-backend .
# Run:   docker run -p 8000:8000 hunter-radar-backend

# ---- Stage 1: Base ----
FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ---- Stage 2: Builder ----
FROM base AS builder

COPY pyproject.toml ./
RUN pip install --prefix=/install .

# ---- Stage 3: Runtime ----
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ ./app/
COPY etl/ ./etl/
COPY sql/ ./sql/

# Non-root user
RUN groupadd -r hunter && useradd -r -g hunter hunter
USER hunter

# Expose
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
