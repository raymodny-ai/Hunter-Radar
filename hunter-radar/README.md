# Hunter Radar

> **美股盘后另类数据雷达**
> 基于期权异常分布 / 全监管做空 / 量价背离 / SEC 内部人行为的多维度共振分析系统
> Version: 1.6.1 | License: Proprietary (Internal)

---

## 目录

1. [项目概述](#1-项目概述)
2. [核心功能](#2-核心功能)
3. [系统架构](#3-系统架构)
4. [数据管道](#4-数据管道)
5. [API 接口文档](#5-api-接口文档)
6. [数据库设计](#6-数据库设计)
7. [前端开发](#7-前端开发)
8. [安全与运维加固](#8-安全与运维加固)
9. [部署运维](#9-部署运维)
10. [开发路线图](#10-开发路线图)

---

## 1. 项目概述

### 1.1 项目定位

Hunter Radar 是一个面向专业量化交易员和风控分析师的美股盘后数据雷达系统。系统的核心思想是**多维共振**：只有多个独立信号源同时对同一标的发出警报时，才视为有效风险信号。

### 1.2 数据源

| 数据源 | 用途 | 获取方式 |
|--------|------|----------|
| **FINRA** | 全监管做空数据 (short_volume, ATS 暗池做空) | CSV 下载 |
| **SEC EDGAR** | Form 4 (内部人交易) / 8-K (重大事件) / Buyback | 网页抓取 + XBRL 解析 |
| **Yahoo Finance** | 日线价格、期权链数据 | yfinance 库 |
| **DeepSeek / Gemini** | 自然语言摘要与分析 | API 代理 (双模型) |

### 1.3 技术栈

| 层 | 技术选型 |
|----|----------|
| **后端框架** | FastAPI (Python 3.12) + uvicorn |
| **数据库** | PostgreSQL 16 + pgcrypto + btree_gist |
| **缓存 / 消息** | Redis 7 (缓存 + 会话 + 速率限制 + 配额计数) |
| **ORM** | SQLAlchemy 2.0 (asyncpg) |
| **前端** | React 18 + TypeScript + Vite 5 |
| **路由** | TanStack Router |
| **状态管理** | TanStack Query + Zustand |
| **图表** | ECharts 5 (hunter-dark 主题) + Lightweight Charts |
| **PWA** | vite-plugin-pwa + Workbox |
| **国际化** | i18next (zh-CN / en 双语文案) |
| **ETL 编排** | Airflow 2.10 (LocalExecutor) |
| **安全** | structlog 审计日志 + detect-secrets + JWT Refresh 轮换 |
| **包管理** | uv (Python) / npm (前端) |
| **容器化** | Docker Compose (postgres + redis + airflow + backend + etl-cron) |

---

## 2. 核心功能

### 2.1 市场门控 (Market Regime)

基于 VIX 水平和 SPX 与 20 日均线偏离度判定市场状态：

- **Normal (正常)**: Threat Score 红灯阈值 = 70
- **Panic (恐慌)**: 阈值自动上调至 80，所有看空信号权重放大

判定逻辑实现于 `app/services/regime.py`，VIX 缺失或 SPX 数据不全时默认走 Normal 容忍分支。

### 2.2 四大风险模块

| 模块 | 说明 | 实现 |
|------|------|------|
| **期权异常 (Options Anomaly)** | 末日 Put 异常建仓 (DTE≤3, OTM>10%, Vol>5×OI) | `app/services/options_anomaly.py` |
| **做空水位 (Short Iceberg)** | Short Ratio + 60 日 Z-Score + ATS 暗池穿透 | `app/services/short_metrics.py` |
| **量价背离 (Divergence)** | 价格/做空斜率分位 + 状态机 (none→rising→confirmed) | `app/services/divergence.py` |
| **内部人行为 (Insider)** | SEC Form 4 C-Level/Director 买卖方向与金额打分 | `app/services/insider.py` |

### 2.3 Threat Score

四大模块的加权合成评分 (0–100)：

| 标的类型 | Options | Short | Divergence | Insider |
|----------|---------|-------|------------|---------|
| **个股** | 30% | 35% | 20% | 15% |
| **ETF** | 35% | 45% | 20% | — |

**V1.6.1 增强**：
- **NULL≠0 处理**：模块返回 None 时从加权平均中排除并重新归一化权重
- **EMA 尖峰覆盖**：raw_score ≥ panic_threshold (80) 时直接判定 "red"，绕过 EMA 平滑
- **数据质量标记**：API 响应携带 `data_quality: "complete" | "degraded" | "stale"`

信号生命周期 5 色灯：🔴 Red ≥ 阈值 | 🟡 Yellow ≥ 50 | ⬜ Gray ≥ 30 | 🟢 Green < 30 | 🔵 Init (冷启动)

### 2.4 终极警报 (Ultimate Alert)

多模块同日共振触发条件：
1. Threat Score EMA ≥ regime 阈值
2. 至少 1 个核心模块连续 ≥ 2 个交易日同向高分
3. 24h 防抖 (同标的至多触发 1 次)

### 2.5 LLM 分析面板

集成 DeepSeek / Gemini 双模型，SSE 流式输出。**V1.6.1 安全加固**：
- 固定 system prompt 模板（用户输入永远不作为 system prompt）
- Model 白名单 + 输入长度限制 (prompt ≤ 2000, context ≤ 8000)
- Redis 速率限制 (5 req/min/user) + 每日 token 预算 (free 50k / pro 500k)
- 输出敏感词过滤（合规红线词拦截）

### 2.6 Screener 每日猎物榜单

按 Threat Score 降序排列所有监控标的，展示活跃模块标记和信号生命周期颜色。12h Redis 缓存。

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                  前端 (Vite 5 + React 18 + TS)           │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │Regime   │ │Screener  │ │Symbol    │ │LLM Panel    │ │
│  │Banner   │ │榜单      │ │指标详情   │ │AI 分析      │ │
│  └─────────┘ └──────────┘ └──────────┘ └─────────────┘ │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │Basket   │ │Alerts    │ │Data      │ │Threat       │ │
│  │自选篮   │ │预警规则   │ │Status    │ │Gauge/Chart  │ │
│  └─────────┘ └──────────┘ └──────────┘ └─────────────┘ │
├─────────────────────────────────────────────────────────┤
│               API Gateway (FastAPI + JWT Auth)            │
│  /api/v1/regime  /screener  /symbols/*  /llm/*  /auth/* │
│  Rate Limiting + Quota Enforcement + Admin Audit Log     │
├─────────────────────────────────────────────────────────┤
│                     Service Layer                         │
│  threat_score  regime  divergence  short_metrics         │
│  options_anomaly  insider  ultimate_alert  etf_proxy     │
├─────────────────────────────────────────────────────────┤
│              ETL Pipeline (etl/ + Airflow)                │
│  Extract → Validate (gate + quarantine) → Load (UPSERT)  │
│  reconcile_batch() 行数对账 + ATSCircuitBreaker 熔断      │
├─────────────────────────────────────────────────────────┤
│               Data Stores                                │
│  ┌──────────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ PostgreSQL 16    │  │ Redis 7  │  │ Static Files   │  │
│  │ (hunter_radar)   │  │ (cache + │  │ (Vite dist/)   │  │
│  │ + quarantine     │  │  ratelimit│  │               │  │
│  └──────────────────┘  └──────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 3.1 后端目录结构

```
backend/
├── app/
│   ├── api/            # 路由控制器
│   │   ├── symbols.py      # 标的核心数据 (threat / divergence / options / short)
│   │   ├── regime.py       # 市场门控
│   │   ├── screener.py     # 每日猎物榜单
│   │   ├── basket.py       # 自选篮子 CRUD
│   │   ├── alerts.py       # 预警规则
│   │   ├── llm.py          # AI 分析代理 (安全加固)
│   │   ├── auth.py         # JWT Refresh 轮换端点
│   │   ├── quota.py        # 配额查询 + enforce_quota 依赖
│   │   ├── admin.py        # 管理端点 (审计日志)
│   │   ├── push.py         # Web Push 订阅
│   │   └── ...
│   ├── core/           # 基础设施
│   │   ├── config.py       # pydantic-settings + 生产环境启动守卫
│   │   ├── database.py     # SQLAlchemy async engine + session
│   │   ├── auth.py         # JWT 签发 / Magic Link 鉴权
│   │   └── redis_client.py # Redis 连接池
│   ├── services/       # 业务逻辑
│   │   ├── threat_score.py      # Threat Score (NULL≠0 + 尖峰覆盖)
│   │   ├── regime.py            # 市场门控判定
│   │   ├── divergence.py        # 量价背离
│   │   ├── options_anomaly.py   # 末日 Put 异常
│   │   ├── short_metrics.py     # 做空水位 Z-Score / ATS
│   │   ├── ultimate_alert.py    # 终极警报触发
│   │   └── insider.py           # Form 4 内部人
│   └── models/          # ORM 模型定义
├── etl/                # ETL 数据采集 + 落库
│   ├── pipeline.py          # 编排器 (_load_with_gate + --force-refresh)
│   ├── validation.py        # 验证门控 + reconcile_batch() 对账
│   ├── ats_scraper.py       # ATS 暗池抓取 + ATSCircuitBreaker 熔断
│   ├── yfinance_pull.py     # Yahoo Finance 拉取
│   ├── finra_short.py       # FINRA 做空数据
│   ├── load_daily_price.py  # 日线落库 (UPSERT)
│   ├── load_short_volume.py # 做空量落库 (UPSERT)
│   ├── load_options_chain.py # 期权链落库 (UPSERT)
│   ├── load_threat_score.py # Threat Score 汇总 (审计日志)
│   └── ...
├── sql/
│   ├── 00_init.sql          # 完整 Schema
│   └── migrations/          # 增量迁移脚本
├── dags/                    # Airflow DAG
└── tests/                   # pytest 测试
```

### 3.2 前端目录结构

```
frontend/
├── src/
│   ├── components/
│   │   ├── radar/        # 核心雷达组件
│   │   │   ├── ThreatScoreGauge.tsx       # 威胁评分仪表盘
│   │   │   ├── ModuleSignalLight.tsx      # 四模块信号灯
│   │   │   ├── SignalLifecycleBadge.tsx   # 生命周期徽章
│   │   │   ├── ThreatHistoryChart.tsx     # 90 日历史走势
│   │   │   ├── UltimateAlertOverlay.tsx   # 终极警报弹窗
│   │   │   └── RegimeBanner.tsx           # 市场状态横幅
│   │   └── common/       # 通用组件 (LlmPanel / LogPanel / DataStatus)
│   ├── routes/           # 页面路由 (TanStack Router)
│   ├── features/         # 自定义 Hooks
│   ├── lib/              # 工具层 (api.ts / queryClient.ts)
│   ├── store/            # Zustand 状态
│   └── i18n/             # 国际化文案 (zh-CN / en)
├── e2e/                  # Playwright E2E 测试
└── tests/wcag/           # axe-core 无障碍测试
```

---

## 4. 数据管道

### 4.1 ETL 执行流程 (V1.6.1 加固)

```
┌─────────────────────────────────────────────────────────┐
│         run_daily_pipeline(trade_date, force_refresh)     │
├─────────────────────────────────────────────────────────┤
│ 1. yfinance EOD bars → _load_with_gate(load_daily_price)│
│ 2. FINRA short_volume → _load_with_gate(load_short_vol) │
│ 3. FINRA ATS → ats_circuit_breaker.call(load_ats_short) │
│ 4. yfinance options → _load_with_gate(load_options_chain)│
│ 5. SEC Form 4 → load_form4 + load_buyback               │
│ 6. 派生计算: short_ratio / divergence / etf_proxy        │
│ 7. compute_regime → compute_threat_scores                │
│    → 评分审计日志 (structlog + weights_json)              │
│ 8. reconcile_batch() 行数对账 (actual/expected < 0.8 → PARTIAL) │
│ 9. refresh_data_status (全局数据状态灯)                   │
└─────────────────────────────────────────────────────────┘
```

**关键机制**：
- **验证门控** (`_load_with_gate`)：critical 错误 → 写入 quarantine 表 → 中止批次
- **UPSERT 可修正性**：daily_price / options_chain / short_volume 使用 `on_conflict_do_update`
- **--force-refresh**：DELETE 当日数据后重新插入（数据纠错场景）
- **ATS 熔断器**：连续 3 次失败 → 30 分钟熔断 → 半开探测恢复

### 4.2 运行方式

```bash
# CLI 单次运行
cd backend && uv run python -m etl.pipeline 2026-06-15

# 强制刷新（删除当日数据后重跑）
cd backend && uv run python -m etl.pipeline 2026-06-15 --force-refresh

# Airflow 编排（生产）
docker compose -f infra/docker-compose.yml up -d airflow-webserver airflow-scheduler
```

### 4.3 冷启动

- 需要至少 **30 个交易日**历史数据才能产生完整 Threat Score
- Z-Score (60 日滚动) 前 60 天为 null
- API 返回 `data_warmup: true` + `data_quality: "stale"` 标记冷启动状态

---

## 5. API 接口文档

### 5.1 基础信息

| 项目 | 值 |
|------|-----|
| Base URL | `http://<host>:8000` |
| OpenAPI 文档 | `/docs` (Swagger UI) / `/redoc` |
| 认证 | JWT Bearer (access 30min + refresh 7d 轮换) |
| 缓存 | Screener / Threat Score 等读端点 12h Redis 缓存 |

### 5.2 核心端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/regime` | 市场门控状态 |
| GET | `/api/v1/screener` | 每日 Threat Score 排名 |
| GET | `/api/v1/symbols/{ticker}/threat` | 最新 Threat Score (含 data_quality) |
| GET | `/api/v1/symbols/{ticker}/threat-history` | 90 日 Threat Score 轨迹 |
| GET | `/api/v1/symbols/{ticker}/options-anomaly` | 末日 Put 异常合约 |
| GET | `/api/v1/symbols/{ticker}/short-iceberg` | 做空水位 (ratio + ATS + z_score) |
| GET | `/api/v1/symbols/{ticker}/divergence` | 量价背离状态机 |
| GET | `/api/v1/symbols/{ticker}/ultimate-alert` | 最近终极警报 |
| GET | `/api/v1/data-status` | 全局数据状态灯 |

### 5.3 用户功能

| 方法 | 路径 | 说明 |
|------|------|------|
| POST/GET | `/api/v1/baskets` | 自选篮子 CRUD |
| POST/GET | `/api/v1/alert-rules` | 预警规则管理 |
| POST/GET | `/api/v1/push/subscriptions` | Web Push 订阅 |
| GET | `/api/v1/push/vapid-public-key` | VAPID 公钥 |

### 5.4 AI 分析 (安全加固)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/llm/analyze` | LLM 分析 (需 JWT, 5 req/min, 每日 token 预算) |

### 5.5 认证 (V1.6.1)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/refresh` | Refresh Token 轮换 (旧 jti 撤销 + 新 pair 签发) |
| GET | `/api/v1/auth/quota` | 配额查询 (需 JWT) |

### 5.6 管理端点 (审计日志)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/admin/etl/run` | 触发 ETL |
| POST | `/api/v1/admin/backtest/run` | 触发回测 |
| POST | `/api/v1/admin/webhook/replay` | 重放 webhook |

所有 admin 端点记录 structlog 审计日志 (who / when / endpoint / params)。

---

## 6. 数据库设计

### 6.1 概览

- **数据库**: PostgreSQL 16, 库名 `hunter_radar`
- **扩展**: `pgcrypto` (UUID), `btree_gist` (复合索引)
- **初始化**: `psql -U hunter -d hunter_radar -f sql/00_init.sql`

### 6.2 核心表

| 分类 | 表名 | 说明 |
|------|------|------|
| **元信息** | `symbol_master` | 标的元信息 (ticker, type, exchange) |
| **原始数据** | `daily_price` | 日线 OHLCV (UPSERT) |
| | `short_volume` | FINRA 做空量 (UPSERT) |
| | `ats_short` | ATS 暗池做空 |
| | `options_chain` | 期权链 (UPSERT) |
| | `form4_event` | SEC 内部人交易 |
| **计算产物** | `short_ratio_daily` | 做空比例 + Z-Score |
| | `option_anomaly` | 末日 Put 异常 |
| | `divergence_window` | 量价背离状态 |
| | `threat_score_daily` | 四维评分 + weights_json |
| | `ultimate_alert` | 终极警报记录 |
| **V1.6.1 新增** | `etl_quarantine` | 验证失败隔离区 |
| **用户功能** | `app_user` / `basket` / `alert_rule` | 用户 / 篮子 / 预警 |

### 6.3 V1.6.1 Schema 变更

```sql
-- 评分审计: weights_json 列
ALTER TABLE threat_score_daily
  ADD COLUMN IF NOT EXISTS weights_json JSONB DEFAULT NULL;

COMMENT ON COLUMN threat_score_daily.weights_json
  IS '评分时各模块权重快照 (审计用)';

-- 验证隔离区
CREATE TABLE IF NOT EXISTS etl_quarantine (
    id          BIGSERIAL PRIMARY KEY,
    stage       TEXT NOT NULL,
    trade_date  DATE NOT NULL,
    row_count   INTEGER NOT NULL DEFAULT 0,
    errors      JSONB NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 7. 前端开发

### 7.1 路由结构

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | 首页 | 项目简介 + 快速入口 |
| `/screener` | 猎物榜单 | Threat Score 排名表 |
| `/symbol/$ticker` | 标的详情 | 仪表盘 + 历史走势 + AI 分析 |
| `/alerts` | 预警规则 | 规则配置 + 评估 |
| `/basket` | 自选篮子 | 篮子管理 |
| `/logs` | 日志流 | 实时 SSE 日志面板 |

### 7.2 核心组件

- **ThreatScoreGauge** — 半圆仪表盘 (0–100)，颜色随 signal_lifecycle 变化
- **ModuleSignalLight** — 四格信号灯矩阵，绿→灰→黄→红渐变
- **ThreatHistoryChart** — ECharts 90 日 EMA 轨迹 + 阈值标注
- **UltimateAlertOverlay** — 全屏终极警报弹窗 (去重 + 手动关闭)
- **LlmPanel** — AI 分析面板 (双模型 + 快捷标签 + 流式输出)
- **RegimeBanner** — 市场状态横幅 (Normal / Panic)

### 7.3 PWA 支持

- 离线预缓存 (Workbox precache ~1.2 MB)
- Web Push (VAPID 协议)
- Service Worker 自动注册 + 更新提示

### 7.4 常用命令

```bash
cd frontend
npm run dev          # 开发服务器 (端口 5173)
npm run build        # 生产构建 (tsc + vite build)
npm run typecheck    # TypeScript 类型检查
npm run lint         # ESLint
npm run test         # Vitest 单元测试
```

---

## 8. 安全与运维加固

> V1.6.1 四阶段全量优化 (2026-06)

### 8.1 关键安全 (P0)

| 措施 | 说明 |
|------|------|
| **生产启动守卫** | `model_validator` 校验 secret_key ≥ 32 字符 + 不含 "dev-only" + CORS 白名单 |
| **LLM 代理锁定** | 固定 system prompt / model 白名单 / 输入长度限制 / 输出过滤 |
| **速率限制** | Redis sliding window 5 req/min/user |
| **每日 token 预算** | free 50k / pro 500k，超额 429 |
| **配额强制执行** | `enforce_quota` 依赖注入 (Redis 计数器，沙箱降级内存) |
| **UPSERT 可修正性** | 可变数据表 `on_conflict_do_update` + `--force-refresh` |

### 8.2 数据完整性 (P1)

| 措施 | 说明 |
|------|------|
| **行数对账** | `reconcile_batch()` actual/expected < 0.8 → PARTIAL 告警 |
| **验证硬门禁** | `_load_with_gate()` critical → quarantine 隔离 + 批次中止 |
| **NULL≠0 评分** | 模块 None 排除 + 权重归一化 |
| **EMA 尖峰覆盖** | raw_score ≥ 80 直接 "red" 旁路 |

### 8.3 运维加固 (P2)

| 措施 | 说明 |
|------|------|
| **Pre-commit 钩子** | detect-secrets + OpenAPI freeze-check + 合规禁词拦截 |
| **Wipe 脚本防护** | `--confirm` / `--env` / `--dry-run`，生产 10s 中止窗口 |
| **Admin 审计日志** | structlog 记录 who / when / endpoint / params |
| **评分审计日志** | `bind_contextvars` 完整分解 + `weights_json` 列持久化 |
| **JWT 轮换** | access 30min + refresh 7d + jti 撤销 + `/auth/refresh` |
| **CORS 生产守卫** | 生产环境拒绝 localhost origin |

### 8.4 韧性与可观测性 (P3)

| 措施 | 说明 |
|------|------|
| **ATS 熔断器** | `ATSCircuitBreaker` (3 次失败 → 30min 熔断 → 半开探测) |
| **数据质量字段** | API 响应 `data_quality: "complete" | "degraded" | "stale"` |

### 8.5 日志规范

统一使用 structlog 风格：

```python
log.warning("etl.validation.partial_batch", stage="short_volume", ratio=0.72)
log.info("admin.audit.access", who=user_id, endpoint="/admin/etl/run")
```

---

## 9. 部署运维

### 9.1 环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | ≥ 3.12 | 后端运行时 |
| Node.js | ≥ 18 | 前端构建 |
| PostgreSQL | 16 | 主数据库 |
| Redis | ≥ 6 | 缓存 + 限流 + 配额 |
| Docker | latest | 容器化部署 |

### 9.2 快速启动

```bash
# 1. 基础设施 (PostgreSQL + Redis + Airflow)
make up              # 或 cd infra && docker compose up -d

# 2. 数据库初始化
make migrate         # Alembic 迁移
make seed            # 种子数据 (symbol_master)

# 3. 后端开发
cd backend && uv run uvicorn app.main:app --reload --port 8000

# 4. 前端开发
cd frontend && npm run dev

# 5. 运行 ETL
cd backend && uv run python -m etl.pipeline $(date +%F)
```

### 9.3 Makefile 命令

| 命令 | 说明 |
|------|------|
| `make up` | 启动 Docker 基础设施 |
| `make down` | 停止所有容器 |
| `make psql` | 进入 PostgreSQL CLI |
| `make redis-cli` | 进入 Redis CLI |
| `make migrate` | 执行 Alembic 迁移 |
| `make seed` | 导入种子数据 |
| `make test` | 运行 pytest |
| `make lint` | Ruff 代码检查 |
| `make fmt` | Ruff 格式化 |

### 9.4 环境变量

后端读取 `.env` 文件 (pydantic-settings)：

```ini
# 核心
DATABASE_URL=postgresql+asyncpg://hunter:hunter@localhost:5432/hunter_radar
REDIS_URL=redis://localhost:6379/0
ENV=development            # development | staging | production
SECRET_KEY=your-32+char-secret   # 生产必须覆盖

# API Keys
DEEPSEEK_API_KEY=sk-***
GEMINI_API_KEY=***

# Web Push
VAPID_PRIVATE_KEY=***
VAPID_PUBLIC_KEY=***

# Sentry
SENTRY_DSN=https://***@sentry.io/***
```

### 9.5 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| FastAPI Backend | 8000 | API + 静态文件 |
| Vite Dev Server | 5173 | 前端开发 |
| PostgreSQL | 5432 | 主数据库 |
| Redis | 6379 | 缓存/限流 |
| Airflow Webserver | 8080 | ETL 编排 UI (绑定 127.0.0.1) |

### 9.6 生产构建

```bash
# 前端构建
cd frontend && npm run build

# 后端启动 (自动 serve 前端 dist/)
cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# 或使用 control.sh
bash control.sh start    # 启动 (PG + Redis + Backend)
bash control.sh status   # 状态检查
bash control.sh stop     # 停止
bash control.sh logs     # 查看日志
```

---

## 10. 开发路线图

### 已完成

- [x] M0: 项目骨架 + FastAPI 应用入口
- [x] M1: 数据库 Schema + 种子数据 + 沙箱 ETL
- [x] M2: 真实数据 ETL (FINRA / Yahoo / SEC) + 派生计算
- [x] M3: Threat Score / 信号生命周期 / 终极警报
- [x] M4: 篮子系统 + Screener 榜单
- [x] M5: 预警规则 + 推送 (Email + Web Push)
- [x] M6: 灰度系统 + 8-K 事件流
- [x] M7: V1.5 接力 (ETF 代理 / EDGAR / 管理端点 / LLM 面板)
- [x] V1.6.0: Docker Compose 全栈编排 + 多源冗余 + ATS Fallback
- [x] **V1.6.1: 四阶段全量优化** (安全加固 / 数据完整性 / 运维加固 / 韧性)

### 待办

- [ ] CI/CD 流水线 (GitHub Actions)
- [ ] Airflow DAG 正式编排 ETL (生产调度)
- [ ] 暗池 ATS 真实周报接入
- [ ] EDGAR XBRL Full-Text 搜索
- [ ] 回测框架 v3.0 全量 Goldset 评估
- [ ] 移动端 PWA 增强

---

> **Disclaimer**: Hunter Radar 仅供研究参考，不构成任何投资建议。
> 所有数据来自公开金融监管源与市场数据供应商，项目不承担因数据延迟、丢失或解读而产生的任何责任。

---

_最后更新: 2026-06-15 | Version: V1.6.1_
