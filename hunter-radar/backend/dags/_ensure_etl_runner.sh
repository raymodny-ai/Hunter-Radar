#!/bin/bash
# Ensure etl_runner.py exists in hunter_backend container.
# Mounted from host into airflow container at /opt/airflow/dags/_ensure_etl_runner.sh.
# Idempotent: skips copy if already in place with same content.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE="$SCRIPT_DIR/../scripts/etl_runner.py"
# airflow container can't see host paths. The runner source must be embedded or fetched.
# Easiest: read it via docker exec against hunter_backend (which has the host bind via its own mounts? NO, backend is image-COPY).
# Cleanest: ship the runner INLINE inside this script. But it's 7KB — too long for env var.
# Pragmatic: every BashOperator that runs ETL will mount the runner via this ensure step.
# We use `docker cp` from AIRFLOW → BACKEND. Source comes from THIS script's directory via /opt/airflow/dags.
# But airflow container's /opt/airflow/dags is the HOST mount of backend/dags/, NOT backend/scripts/.
# Solution: also mount backend/scripts/ into airflow container.

RUNNER_HOST="/opt/airflow/scripts/etl_runner.py"

if [ ! -f "$RUNNER_HOST" ]; then
    echo "ERROR: etl_runner.py not found at $RUNNER_HOST" >&2
    exit 1
fi

# Check if backend already has the same file (compare sha256)
LOCAL_HASH=$(sha256sum "$RUNNER_HOST" | cut -d' ' -f1)
REMOTE_HASH=$(sg docker -c "docker exec hunter_backend sha256sum /app/etl_runner.py" 2>/dev/null | cut -d' ' -f1 || echo "missing")

if [ "$LOCAL_HASH" = "$REMOTE_HASH" ]; then
    echo "etl_runner.py already up to date (sha=$LOCAL_HASH[:8])"
    exit 0
fi

echo "Updating etl_runner.py in hunter_backend container (sha ${REMOTE_HASH:-missing} -> $LOCAL_HASH)"
# 2026-07-23 patch: airflow 容器通过 group_add=994 获得 docker socket 权限,
# 不再用 sg (容器内无 docker 组)。直接调 docker CLI 即可。
# 不要 chmod +x (backend 容器以非 root hunter 用户跑, chmod 不允许)。
docker cp "$RUNNER_HOST" hunter_backend:/app/etl_runner.py
echo "Done."