#!/bin/bash
# Hunter Radar 本地部署控制脚本
# 使用: bash control.sh start|stop|status|logs
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/hunter-radar/backend"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"
SERVER_LOG="$PROJECT_DIR/server.log"

export LD_LIBRARY_PATH="$PROJECT_DIR/hunter-radar/.redis-bundle/redis-root/usr/lib/x86_64-linux-gnu"

case "${1:-status}" in
  start)
    echo "Starting Hunter Radar..."
    # 确保 PG 已启动
    if ! /usr/lib/postgresql/15/bin/pg_ctl -D "$PROJECT_DIR/.pg-data" status >/dev/null 2>&1; then
      echo "Starting PostgreSQL..."
      /usr/lib/postgresql/15/bin/pg_ctl -D "$PROJECT_DIR/.pg-data" -l "$PROJECT_DIR/.pg-data/logfile" start
      sleep 2
    fi
    # 确保 Redis 已启动
    if ! pgrep -f "redis-server.*127.0.0.1:6379" >/dev/null; then
      echo "Starting Redis..."
      nohup "$PROJECT_DIR/hunter-radar/.redis-bundle/redis-root/usr/bin/redis-server" "$PROJECT_DIR/hunter-radar/.redis-config.conf" > "$PROJECT_DIR/hunter-radar/.redis-data/redis.log" 2>&1 &
      sleep 1
    fi
    # 启动后端(切到 backend 目录,让 pydantic-settings 能读到 .env)
    cd "$BACKEND_DIR"
    nohup "$VENV_PYTHON" -u -m app.static_serve > "$SERVER_LOG" 2>&1 &
    BACKEND_PID=$!
    cd "$PROJECT_DIR"
    echo "PID: $BACKEND_PID"
    sleep 2
    if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
      echo "✅ Hunter Radar running at http://localhost:8000"
      echo "   API docs: http://localhost:8000/docs"
    else
      echo "❌ Server failed to start. Check: tail -50 $SERVER_LOG"
    fi
    ;;
  stop)
    echo "Stopping Hunter Radar..."
    pkill -f "app.static_serve" 2>/dev/null || true
    echo "Stopped."
    ;;
  status)
    if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
      echo "✅ Hunter Radar is running"
      curl -s http://127.0.0.1:8000/health | python3 -m json.tool 2>/dev/null || true
    else
      echo "❌ Hunter Radar is not running"
    fi
    /usr/lib/postgresql/15/bin/pg_ctl -D "$PROJECT_DIR/.pg-data" status 2>/dev/null && echo "✅ PostgreSQL running" || echo "❌ PostgreSQL not running"
    pgrep -f "redis-server.*127.0.0.1:6379" >/dev/null && echo "✅ Redis running" || echo "❌ Redis not running"
    ;;
  logs)
    tail -f "$SERVER_LOG"
    ;;
  *)
    echo "Usage: $0 {start|stop|status|logs}"
    exit 1
    ;;
esac
