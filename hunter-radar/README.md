# Hunter Radar V1.4

> 「穿透暗池做空,捕获机构绞杀前夜」— 美股盘后另类数据雷达

## 项目结构

```
hunter-radar/
├── backend/                  # Python + FastAPI + Airflow
│   ├── app/                  # 应用代码
│   │   ├── api/              # REST 端点
│   │   ├── core/             # 配置/日志/数据库/缓存
│   │   ├── models/           # SQLAlchemy ORM
│   │   ├── schemas/          # Pydantic 契约
│   │   └── services/         # 业务服务(评分/筛选/预警)
│   ├── etl/                  # 爬虫与离线计算
│   ├── dags/                 # Airflow DAG
│   ├── sql/                  # 初始化/迁移 SQL
│   └── tests/                # pytest
├── frontend/                 # Vite + React 18 + TS
│   ├── src/
│   └── public/
├── infra/                    # docker-compose / 反代 / 监控配置
├── docs/                     # 校准报告/部署SOP
└── scripts/                  # 本地辅助脚本
```

## 快速启动

```bash
# 1. 启动基础设施(数据库/缓存/调度)
cd infra && docker compose up -d

# 2. 后端
cd backend && uv sync && uv run fastapi dev app/main.py

# 3. 前端
cd frontend && pnpm install && pnpm dev

# 4. 打开浏览器
# 后端: http://localhost:8000/docs
# 前端: http://localhost:5173
```

## 文档

- PRD:`../Hunter Radar-v1.3-1.4-merged-reference.md`
- 前端计划:`../frontend-plan.md`
- 实施 Todo:`../Hunter-Radar-v1.4-implementation-todo.md`
- 每日站会:`../daily-standup.md`
