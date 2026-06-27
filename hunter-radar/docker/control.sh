#!/bin/bash
# Hunter Radar V1.6.0 Docker 控制脚本
# 使用: bash docker/control.sh start|stop|restart|logs|migrate|seed|status
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_DIR/infra/docker-compose.yml"

case "${1:-status}" in
  start)
    echo "Starting Hunter Radar (Docker)..."
    docker compose -f "$COMPOSE_FILE" up -d
    echo "Waiting for health checks..."
    sleep 10
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
      echo "✅ Hunter Radar running at http://localhost:8000"
      echo "   API docs: http://localhost:8000/docs"
    else
      echo "⚠️  Backend may still be starting. Check: docker compose -f $COMPOSE_FILE ps"
    fi
    ;;
  stop)
    echo "Stopping Hunter Radar (Docker)..."
    docker compose -f "$COMPOSE_FILE" down
    echo "Stopped."
    ;;
  restart)
    echo "Restarting Hunter Radar (Docker)..."
    docker compose -f "$COMPOSE_FILE" restart backend
    sleep 5
    echo "Restarted."
    ;;
  logs)
    SERVICE="${2:-backend}"
    docker compose -f "$COMPOSE_FILE" logs -f "$SERVICE"
    ;;
  migrate)
    echo "Running SQL migrations..."
    for sql_file in "$PROJECT_DIR"/backend/sql/*.sql; do
      echo "  Applying: $(basename "$sql_file")"
      docker compose -f "$COMPOSE_FILE" exec -T postgres \
        psql -U hunter -d hunter_radar < "$sql_file" 2>/dev/null || true
    done
    echo "Migrations complete."
    ;;
  seed)
    echo "Running seed data..."
    docker compose -f "$COMPOSE_FILE" exec -T backend \
      python -m etl.pipeline 2>/dev/null || echo "Seed skipped or failed."
    ;;
  status)
    docker compose -f "$COMPOSE_FILE" ps
    echo ""
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
      echo "✅ Backend healthy"
    else
      echo "❌ Backend not responding"
    fi
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|logs [service]|migrate|seed|status}"
    exit 1
    ;;
esac
