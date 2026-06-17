# Backend

Python 3.12 + FastAPI + SQLAlchemy 2 (async) + PostgreSQL 16 + Redis 7 + Airflow 2.10.

## 启动

```bash
# 1. 基础设施
cd infra && docker compose up -d

# 2. 安装依赖(推荐 uv)
cd backend
uv sync --extra dev --extra airflow

# 3. 初始化数据库表
uv run python -c "import asyncio; from app.core.database import engine, Base; import app.models; asyncio.run(Base.metadata.create_all(engine))"

# 4. 导入种子标的
uv run python -m etl.symbol_seed

# 5. 跑后端
uv run fastapi dev app/main.py
# 或 uvicorn app.main:app --reload

# 6. 跑测试
uv run pytest -q
```

## 目录

- `app/` — FastAPI 应用
  - `api/` — REST 路由(health / symbols / regime / screener / alerts)
  - `core/` — 配置 / DB / Redis
  - `models/` — SQLAlchemy ORM
  - `services/` — 业务服务(Threat Score / EMA 平滑 — OQ-02 已落地)
- `etl/` — 数据采集(FINRA / SEC / Yahoo)
- `dags/` — Airflow DAG
- `sql/00_init.sql` — 数据库 schema 初始化
- `tests/` — pytest 单元测试

## 关键设计

- **OQ-02 决策已落地**:`app/services/threat_score.py` 提供 `ema_smooth` / `consecutive_business_days_above` / `compute_threat_score`,配套 `tests/test_threat_score.py` 覆盖三种曲线 + 严格连续 2 交易日窗口。
- **数据缺失兜底**:`data_ingestion_status` 视图,API 永不返回昨日数据伪装实时(BD-081 红线)。
- **CR-010 合规红线**:`forbidden_recommendation_words` 在 settings 中预置,CI 通过 `scripts/compliance_check.py` 拦截禁词。
- **OpenAPI freeze**:所有端点契约先立住(M0 阶段部分返 501),前端用 `openapi-typescript` 自动生成类型(BD-078 → FE-010)。
