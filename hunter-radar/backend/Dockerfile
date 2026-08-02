# Hunter Radar V1.6.0 — Multi-stage Dockerfile
# Build: docker buildx build --tag hunter-radar-backend --load .
# Run:   docker run -p 8000:8000 hunter-radar-backend
#
# 2026-07-22 patch: pin to python:3.12-slim (3.14 pre-GA + pyproject>=3.12 conflict;
# numpy/pandas prebuilt wheels don't ship 3.14 yet -> blow up at pip install).
#
# 2026-08-02 patch (A1 / buildkit cache mount): 拆 apt-get / pip install 到独立 stage,
# 并用 --mount=type=cache 复用 apt 和 pip 缓存. 第一次 build 跟之前一样久,
# 第二次起代码变更时 apt cache 命中(秒过), pip cache 部分命中(只重装变化依赖).
# BuildKit 必须启用 (DOCKER_BUILDKIT=1 或 buildx driver=docker, 默认即开).
# 触发方式: docker compose build backend (compose v2 + buildkit 走 buildx 路径)
# 或: docker buildx build --load -t infra-backend -f backend/Dockerfile backend/

# ---- Stage 1: System deps (cached) ----
FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS sysdeps

ENV DEBIAN_FRONTEND=noninteractive

# apt cache mount 复用: 第二次起秒过
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gcc \
        libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# ---- Stage 2: Python deps (pip cached) ----
FROM sysdeps AS pydeps

WORKDIR /app

# pip cache mount: 复用 wheel 缓存, 增量构建只装变化的包
# PIP_NO_CACHE_DIR=1 关闭 pip 自身 cache dir, 避免破坏 --mount cache
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml ./

# BuildKit cache mount: 复用 pip wheel 缓存. --prefix=/install 让 builder→runtime COPY 路径不变
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --prefix=/install .

# ---- Stage 3: Runtime (final image) ----
FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime only needs curl + libpq5 (runtime libs, no gcc/build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from pydeps stage
COPY --from=pydeps /install /usr/local

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
