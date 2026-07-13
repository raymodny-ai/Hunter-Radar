#!/bin/bash
# Hunter Radar — 本地用户空间部署控制脚本
# 数据栈:PostgreSQL 5433 / Redis 6379 / FastAPI 8000
# sudo 不需要,所有东西都在用户目录下。
#
# 用法:
#   ./control.sh start    启动所有服务(后台)
#   ./control.sh stop     停止后端
#   ./control.sh restart  重启后端
#   ./control.sh status   状态
#   ./control.sh logs     tail 后端日志
#   ./control.sh db       psql shell
#   ./control.sh redis    redis-cli shell
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
HR="$ROOT/hunter-radar"
BACK="$HR/backend"
PG_BIN=/usr/lib/postgresql/15/bin
PG_DATA="$HR/.pg-data"
PG_RUN="$PG_DATA/run"
PG_PORT=5433
REDIS_BIN="$HR/.redis-bundle/redis-root/bin/redis-server"
REDIS_CLI="$HR/.redis-bundle/redis-root/bin/redis-cli"
REDIS_CONF="$HR/.redis-config.conf"
REDIS_LOG="$HR/.redis-data/redis.log"
SERVER_LOG="$ROOT/server.log"
VENV="$BACK/.venv"

cmd="${1:-status}"

start_pg() {
  if pgrep -f "postgres.*$PG_DATA" >/dev/null; then return 0; fi
  echo "[pg] starting on port $PG_PORT"
  $PG_BIN/pg_ctl -D "$PG_DATA" -l "$PG_DATA/logfile" start >/dev/null
  sleep 2
}
start_redis() {
  if pgrep -f "redis-server.*$REDIS_CONF\|redis-server 127.0.0.1:6379" >/dev/null; then return 0; fi
  echo "[redis] starting on port 6379"
  nohup "$REDIS_BIN" "$REDIS_CONF" >/dev/null 2>&1 &
  sleep 1
}
start_backend() {
  if pgrep -f "app.static_serve" >/dev/null; then echo "[backend] already running"; return 0; fi
  echo "[backend] starting on 0.0.0.0:8000"
  cd "$BACK"
  nohup "$VENV/bin/python" -u -m app.static_serve > "$SERVER_LOG" 2>&1 &
  sleep 4
  if curl -sf http://127.0.0.1:8000/health >/dev/null; then
    echo "[backend] ✅ http://localhost:8000"
    echo "         docs:  http://localhost:8000/docs"
  else
    echo "[backend] ❌ 启动失败,tail -50 $SERVER_LOG"
  fi
}

case "$cmd" in
  start)
    start_pg
    start_redis
    start_backend
    ;;
  stop)
    pkill -f "app.static_serve" 2>/dev/null && echo "[backend] stopped" || echo "[backend] not running"
    ;;
  restart)
    pkill -f "app.static_serve" 2>/dev/null || true
    sleep 1
    start_backend
    ;;
  status)
    curl -sf http://127.0.0.1:8000/health | python3 -m json.tool 2>/dev/null || echo "[backend] ❌ down"
    pgrep -f "postgres.*$PG_DATA" >/dev/null && echo "[pg]      ✅ port $PG_PORT" || echo "[pg]      ❌ down"
    pgrep -f "redis-server.*6379" >/dev/null && echo "[redis]   ✅ port 6379" || echo "[redis]   ❌ down"
    ;;
  logs)  tail -f "$SERVER_LOG" ;;
  db)    $PG_BIN/psql -U hunter -h "$PG_RUN" -p 5433 -d hunter_radar "$@" ;;
  redis) $REDIS_CLI "$@" ;;
  *) echo "Usage: $0 {start|stop|restart|status|logs|db|redis}"; exit 1 ;;
esac
