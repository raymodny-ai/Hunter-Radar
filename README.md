# Hunter Radar

> **美股盘后另类数据雷达**  
> 基于期权异常分布 / 全监管做空 / 量价背离 / SEC 内部行为的多维度共振分析系统  
> Version: V1.6.0 (Frontend V2.0 in development) | License: Proprietary (Internal)

---

## 项目简介

Hunter Radar 是一个面向专业量化交易员和风控分析师的美股盘后数据雷达系统。核心思想是**多维共振**：只有多个独立信号源同时对同一标的发出警报时，才视为有效风险信号。

### 数据源

| 数据源 | 用途 | 获取方式 |
|--------|------|----------|
| **FINRA** | 全监管做空数据(short_volume, ATS 暗池做空) | CSV 下载 |
| **SEC EDGAR** | Form 4 (内部人交易) / 8-K (重大事件) / Buyback | 网页抓取 + XBRL 解析 |
| **Yahoo Finance** | 日线价格、期权链数据 | yfinance 库 |
| **DeepSeek / Gemini** | 自然语言摘要与分析 | API 代理 |

### 技术栈

| 层 | 技术选型 |
|----|----------|
| **后端框架** | FastAPI (Python 3.12) + uvicorn |
| **数据库** | PostgreSQL 16 + Redis 7 |
| **ORM** | SQLAlchemy 2.0 (asyncpg) |
| **前端** | React 18 + TypeScript + Vite 5 |
| **路由 / 状态** | TanStack Router + TanStack Query + Zustand |
| **图表** | ECharts 5 (hunter-dark theme) |
| **PWA** | vite-plugin-pwa + Workbox |
| **国际化** | i18next (zh-CN / en 双语文案) |
| **测试** | Playwright + axe-core (WCAG AA) + pytest |
| **代码规模** | 后端 ~46K loc / 前端 ~6.7K loc / SQL ~450 loc |

---

## 项目结构

```
Hunter Radar/
├── hunter-radar/              # 主项目目录
│   ├── backend/               # FastAPI 后端
│   │   ├── app/
│   │   │   ├── api/           # 21 个 REST 路由
│   │   │   ├── core/          # 配置 / DB / Redis
│   │   │   ├── models/        # SQLAlchemy ORM
│   │   │   └── services/      # Threat Score / EMA / Regime
│   │   ├── etl/               # FINRA / Yahoo / SEC 数据采集
│   │   ├── dags/              # Airflow DAG
│   │   ├── sql/               # 完整 Schema + 迁移
│   │   ├── tests/             # pytest 单元测试
│   │   └── pyproject.toml
│   ├── frontend/              # React 前端 (V2.0)
│   │   ├── src/
│   │   │   ├── routes/        # 7 个页面路由
│   │   │   ├── components/    # radar/ + common/ + charts/
│   │   │   ├── features/      # 自定义 Hooks
│   │   │   ├── store/         # Zustand 状态
│   │   │   ├── lib/           # API 客户端 + Query 配置
│   │   │   └── i18n/          # zh-CN.json
│   │   ├── e2e/               # Playwright E2E
│   │   └── package.json
│   ├── infra/                 # Docker Compose (Postgres + Redis + Airflow)
│   ├── docs/                  # 项目文档 (M0-M7 / V1.4-V1.6 handoff)
│   ├── scripts/               # 工具脚本
│   ├── control.sh             # 服务管理脚本
│   └── Makefile               # 开发命令
├── frontend-v2-architecture.canvas.tsx  # Canvas 可视化架构总览
└── README.md                  # 本文件
```

---

## 快速开始

### 环境要求

| 依赖 | 版本 |
|------|------|
| Python | ≥ 3.12 |
| Node.js | ≥ 18 |
| PostgreSQL | 16 |
| Redis | ≥ 6 |
| Docker / Docker Compose | 最新 |

### 1. 启动基础设施

```bash
cd hunter-radar/infra
docker compose up -d
```

### 2. 启动后端

```bash
cd hunter-radar/backend
uv sync --extra dev --extra airflow
uv run python -c "import asyncio; from app.core.database import engine, Base; import app.models; asyncio.run(Base.metadata.create_all(engine))"
uv run python -m etl.symbol_seed
uv run fastapi dev app/main.py
# 服务运行于 http://localhost:8000
# OpenAPI: http://localhost:8000/docs
```

### 3. 启动前端

```bash
cd hunter-radar/frontend
npm install
npm run dev
# 开发服务器运行于 http://localhost:5173
```

### 4. 运行 ETL（每日数据刷新）

```bash
cd hunter-radar/backend
uv run python -m etl.pipeline $(date +%F)
```

### 5. 运行测试

```bash
# 后端
cd hunter-radar/backend && uv run pytest -q

# 前端单元 + E2E
cd hunter-radar/frontend && npm run test
cd hunter-radar/frontend && npx playwright test
```

---

## 核心功能

### 多维共振评分（Threat Score 0–100）

四个独立信号模块加权合成，EMA 平滑（半衰期 2 交易日）防毛刺：

| 标的类型 | 期权异常 | 做空水位 | 量价背离 | 内部人 |
|----------|---------|---------|---------|--------|
| **个股** | 30% | 35% | 20% | 15% |
| **ETF** | 35% | 45% | 20% | — |

**信号生命周期**：🔴 Red ≥ 阈值（Normal 70 / Panic 80）→ 🟡 Yellow → ⬜ Gray → 🟢 Green → 🔵 Init

### 市场门控（Regime）

基于 VIX 水平和 SPX 与 20 日均线偏离度：
- **Normal**：红灯阈值 = 70
- **Panic**：阈值自动上调至 80，所有看空信号权重放大

### 终极警报（Ultimate Alert）

多模块同日共振 + 至少 1 个核心模块连续 ≥ 2 交易日同向高分 + 24h 防抖。实现于 `app/services/ultimate_alert.py`。

### LLM 分析面板

集成 DeepSeek / Gemini 双模型，默认使用量化风控分析师提示词，后端 `app/api/llm.py` 代理转发，SSE 流式输出。

### Web Push 预警

VAPID + ServiceWorker，前端订阅 → 后端推送 → 浏览器原生通知。

---

## 前端 V2.0 架构

四个里程碑（M1-M4）已全部交付，共 58 个 FE 任务：

| 里程碑 | 内容 | Commit |
|--------|------|--------|
| **M1** | 四区布局 / 搜索 / Sidebar / ECharts 主题 / Zustand Store | `7b12346` |
| **M2** | 7 个核心图表组件 / Screener 虚拟列表 / 跨图同步 | `d7005cf` |
| **M3** | Regime 页 / 篮子雷达 / 预警中心 / LLM SSE | `460a8ef` |
| **M4** | 响应式 / 无障碍 / Admin / E2E / 性能探针 | `d85a2ed` |

**5 区拓扑**：
- **TopNav** — Logo / 导航 / 搜索 / 状态灯
- **Banners** — EventTicker (8-K) / Regime / DataStatus / Quota
- **LeftToolbar** — AnalyzerLenses (OPT/SHT/DIV/INS)
- **Main Canvas** — 7 个核心路由
- **RightSidebar** — Watchlist / Alerts / AI Copilot 三 Tab

**3 档断点**：xl (>1280px) 三栏 / md (768-1280px) overlay drawer / mobile 单列

**10 个 ECharts**：Waterfall / 4D Radar / 90-Day Trajectory / Options Heatmap / Short Iceberg V2 / Volume-Price Divergence / Insider Timeline / Regime Timeline / BasketHistogram / SparkRadar

可视化架构总览：[frontend-v2-architecture.canvas.tsx](frontend-v2-architecture.canvas.tsx)

---

## 部署

### 生产构建

```bash
# 1. 初始化数据库
psql -U hunter -d hunter_radar -f hunter-radar/backend/sql/00_init.sql

# 2. 前端构建
cd hunter-radar/frontend && npm run build

# 3. 启动后端（自动 serve 静态文件）
cd hunter-radar/backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. 定时 ETL（cron 或 Airflow）
cd hunter-radar/backend && uv run python -m etl.pipeline
```

### 服务端口

| 服务 | 端口 | 绑定 |
|------|------|------|
| FastAPI Backend | 8000 | 0.0.0.0 |
| Vite Dev Server | 5173 | localhost |
| PostgreSQL | 5432 | localhost |
| Redis | 6379 | localhost |

### PWA 离线支持

- **预缓存**：核心 shell (~1.2 MB)
- **运行时缓存**：报告接口 12h TTL，威胁评分 5 命中率
- **navigateFallback**：`/offline.html`（断网时跳转）
- **denylist**：`/api/*`、`/docs`、`/openapi.json`
- **Web Push**：VAPID 协议

---

## 文档导航

| 文档 | 路径 |
|------|------|
| 完整项目说明 | [hunter-radar/README.md](hunter-radar/README.md) |
| 后端开发文档 | [hunter-radar/backend/README.md](hunter-radar/backend/README.md) |
| 前端开发文档 | [hunter-radar/frontend/README.md](hunter-radar/frontend/README.md) |
| 前端 V2.0 TODO | [hunter-radar/docs/frontend-v2.0-todo.md](hunter-radar/docs/frontend-v2.0-todo.md) |
| V1.6.0 接力报告 | [hunter-radar/docs/V1.6.0-handoff.md](hunter-radar/docs/V1.6.0-handoff.md) |
| 历次 Handoff | `hunter-radar/docs/M0-handoff.md` ~ `M7-handoff.md` |
| OpenAPI Freeze | `hunter-radar/docs/openapi-frozen-v1.5*.{md,json}` |
| BD-087 校准 | `hunter-radar/docs/BD-087-calibration-report-v3.0-final.md` |

---

## 版本历史

| 版本 | 日期 | 关键交付 |
|------|------|----------|
| **V1.6.0** | 2026-07 | Frontend V2.0 (M1-M4) + 重新部署 + 回归测试 7 轮迭代 |
| **V1.5.8** | 2026-06-28 | Initial commit (307 文件, 68160 行, ONLINE-READY) |
| **V1.5.x** | 2026-04~06 | ETF 代理 / EDGAR / 管理端点 / LLM 面板 |
| **V1.4.0** | 2026-Q1 | PWA + LLM + ETF + Admin + Form 4 + 8-K |
| **V1.3.0** | 2025-Q4 | Threat Score / Regime / 终极警报 |
| **M0-M7** | 2025-Q3~Q4 | 项目骨架至预警推送完整链路 |

---

## 开发路线图

### 已完成

- [x] M0–M7 全链路（FastAPI + ETL + Threat Score + 篮子系统 + 预警推送）
- [x] V1.4–V1.6 多轮迭代（PWA / LLM / ETF / Frontend V2.0）
- [x] 前端 V2.0：4 里程碑 58 任务全部完成

### 进行中

- [ ] Frontend V2.0 性能调优 + Lighthouse 审计
- [ ] E2E 测试覆盖率提升（Playwright + axe-core）
- [ ] OpenAPI v1.6 冻结与 CI 集成

### 待办

- [ ] Airflow DAG 正式编排 ETL
- [ ] 暗池 ATS 真实周报接入
- [ ] EDGAR XBRL Full-Text 搜索
- [ ] 回测框架 v3.0 Goldset 全量评估
- [ ] 移动端 PWA 增强（Push / Offline 写入）

---

## 合规与免责

> **Disclaimer**: Hunter Radar 仅供研究参考，不构成任何投资建议。  
> 所有数据来自公开金融监管源（FINRA / SEC EDGAR）与市场数据供应商（Yahoo Finance），项目不承担因数据延迟、丢失或解读而产生的任何责任。

### 合规红线

- **BD-078**：前端类型从 `/openapi.json` 自动生成，禁止手写类型覆盖后端契约
- **BD-081**：API 永不返回昨日数据伪装实时（`data_ingestion_status` 兜底）
- **BD-085**：ETL 必须 admin 鉴权 + 审计日志
- **CR-010**：禁用 `forbidden_recommendation_words`（buy/sell/strong buy/强卖 等），CI 通过 `scripts/compliance_check.py` 拦截

---

_最后更新: 2026-07-13 | Version: V1.6.0 + Frontend V2.0_