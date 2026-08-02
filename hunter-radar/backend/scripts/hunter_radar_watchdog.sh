#!/bin/bash
# Hunter-Radar watchdog — OpenClaw cron 每 30min 调用
# 职责(hybrid 部署: 裸 uvicorn + docker PG/Redis, 无 supervisord):
#   1) 后端存活: /health 非 200 → 拉起 docker 依赖 + nohup 重启
#   2) ETL 新鲜度: daily_price 缺最近完成交易日 → 跑 etl.pipeline 补
# 幂等、可重复执行, 失败只在 cron runner 侧日志, 不扔异常(除 schema 严重错误)。
set -u

BACKEND_DIR="/vol1/@apphome/trim.openclaw/data/workspace/Hunter-Radar/hunter-radar/backend"
VENV_PY="$BACKEND_DIR/.venv/bin/python"
BACKEND_LOG="/tmp/hunter-radar-backend.log"
ETL_LOG="/tmp/hunter-radar-etl-watchdog.log"
HEALTH_URL="http://localhost:8000/health"

log() { echo "[$(date '+%F %T %Z')] $*"; }

# ---------- 1) 后端存活 ----------
restart_backend() {
  log "WARN backend down → restarting"
  # 确保 docker 依赖(PG 5433 / Redis 6379)先 up
  docker start hunter_postgres hunter_redis >/dev/null 2>&1
  # 等 PG ready
  for i in $(seq 1 15); do
    if $VENV_PY -c "from app.core.database import check; import asyncio; asyncio.run(check())" >/dev/null 2>&1 \
       && $VENV_PY -c "import redis,os; from app.core.config import settings; redis.from_url(settings.redis_url).ping()" >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  # 杀旧进程(若有) 再 nohup 起
  pkill -f "app.static_serve" 2>/dev/null
  sleep 1
  (cd "$BACKEND_DIR" && nohup "$VENV_PY" -u -m app.static_serve > "$BACKEND_LOG" 2>&1 &)
  sleep 5
  if curl -sS -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null | grep -q 200; then
    log "OK backend restarted (health 200)"
  else
    log "ERROR backend failed to start after restart; tail log:"
    tail -5 "$BACKEND_LOG" >&2
  fi
}

if ! curl -sS -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null | grep -q 200; then
  restart_backend
else
  log "OK backend up"
fi

# ---------- 2) ETL 新鲜度 ----------
# 目标交易日 = 最近一个已完成工作日(ET)。周一~周五: 昨天; 周六/日: 上周五。
TODAY=$(TZ=America/New_York date +%F)
DOW=$(TZ=America/New_York date +%u)   # 1=Mon .. 7=Sun
case "$DOW" in
  6) TARGET=$(TZ=America/New_York date -d "yesterday" +%F) ;;                # Sat → Fri
  7) TARGET=$(TZ=America/New_York date -d "2 days ago" +%F) ;;               # Sun → Fri
  1) TARGET=$(TZ=America/New_York date -d "3 days ago" +%F) ;;               # Mon → Fri
  *) TARGET=$(TZ=America/New_York date -d "yesterday" +%F) ;;                # Tue-Fri → yesterday
esac

log "ETL 检查: target=$TARGET (today=$TODAY dow=$DOW)"

# daily_price / short_volume 是否已含 target?(任一缺即触发, pipeline 一次跑全量补)
HAVE_P=$("$VENV_PY" -c "
import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
async def m():
    async with AsyncSessionLocal() as s:
        v = await s.scalar(text(\"SELECT MAX(trade_date) FROM daily_price\"))
        print(v.isoformat() if v else '')
asyncio.run(m())
" 2>/dev/null)

HAVE_S=$("$VENV_PY" -c "
import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
async def m():
    async with AsyncSessionLocal() as s:
        v = await s.scalar(text(\"SELECT MAX(trade_date) FROM short_volume\"))
        print(v.isoformat() if v else '')
asyncio.run(m())
" 2>/dev/null)

NEED_ETL=0
for HAVE in "$HAVE_P" "$HAVE_S"; do
  if [ "$HAVE" = "" ] || [ "$(date -d "$HAVE" +%s)" -lt "$(date -d "$TARGET" +%s)" ]; then
    NEED_ETL=1
  fi
done

if [ $NEED_ETL -eq 1 ]; then
  log "WARN 数据缺 $TARGET (daily_price=$HAVE_P short_volume=$HAVE_S) → 跑 ETL pipeline"
  (cd "$BACKEND_DIR" && timeout 900 "$VENV_PY" -u -m etl.pipeline "$TARGET" >> "$ETL_LOG" 2>&1)
  RC=$?
  if [ $RC -eq 0 ]; then
    log "OK ETL pipeline $TARGET 完成"
  else
    log "ERROR ETL pipeline $TARGET 失败 rc=$RC"
  fi
else
  log "OK 数据已覆盖 $TARGET (daily_price=$HAVE_P short_volume=$HAVE_S)"
fi

exit 0
