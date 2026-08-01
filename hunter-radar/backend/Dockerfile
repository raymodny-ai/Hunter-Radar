# Hunter Radar V1.6.0 — Multi-stage Dockerfile
# Build: docker build -t hunter-radar-backend .
# Run:   docker run -p 8000:8000 hunter-radar-backend
#
# 2026-07-22 patch: pin to python:3.12-slim (3.14 pre-GA + pyproject>=3.12 conflict;
# numpy/pandas prebuilt wheels don't ship 3.14 yet -> blow up at pip install).

# ---- Stage 1: Base ----
FROM python:3.12-slim AS base

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
FROM python:3.12-slim AS runtime

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

# 2026-07-23 patch: 将前端 dist 烘进镜像，让容器重建后 SPA 仍然可用。
# 需在 backend/frontend_dist/ 里先存好 dist（build context 内，不跨目录）。
# 部署流程: cd frontend && npm run build && cp -r dist/* ../backend/frontend_dist/
COPY frontend_dist/ ./frontend/dist/

# Non-root user
RUN groupadd -r hunter && useradd -r -g hunter hunter
USER hunter

# Expose
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
# 2026-07-23 patch: use static_serve (which mounts /assets + SPA fallback) instead of bare main.
# Without this the frontend SPA routes (/) all 404, and the @app.get("/{full_path:path}") in
# static_serve.py never registers.
CMD ["python", "-m", "uvicorn", "app.static_serve:app", "--host", "0.0.0.0", "--port", "8000"]
