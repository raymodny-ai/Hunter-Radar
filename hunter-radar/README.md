# Hunter Radar — 项目说明文档

> **美股盘后另类数据雷达**  
> 基于期权异常分布 / 全监管做空 / 量价背离 / SEC 内部行为的多维度共振分析系统  
> Version: 1.4.0 | License: Proprietary (Internal)

---

## 目录

1. [项目概述](#1-项目概述)
2. [核心功能](#2-核心功能)
3. [系统架构](#3-系统架构)
4. [数据管道](#4-数据管道)
5. [API 接口文档](#5-api-接口文档)
6. [数据库设计](#6-数据库设计)
7. [前端开发](#7-前端开发)
8. [部署运维](#8-部署运维)
9. [开发路线图](#9-开发路线图)

---

## 1. 项目概述

### 1.1 项目定位

Hunter Radar 是一个面向专业量化交易员和风控分析师的美股盘后数据雷达系统。系统的核心思想是**多维共振**：只有多个独立信号源同时对同一标的发出警报时，才视为有效风险信号。

### 1.2 数据源

| 数据源 | 用途 | 获取方式 |
|--------|------|----------|
| **FINRA** | 全监管做空数据(short_volume, ATS 暗池做空) | CSV 下载 |
| **SEC EDGAR** | Form 4 (内部人交易) / 8-K (重大事件) / Buyback | 网页抓取 + XBRL 解析 |
| **Yahoo Finance** | 日线价格、期权链数据 | yfinance 库 |
| **DeepSeek / Gemini** | 自然语言摘要与分析 | API 代理 |

### 1.3 技术栈

| 层 | 技术选型 |
|----|----------|
| **后端框架** | FastAPI (Python 3.12) + uvicorn |
| **数据库** | PostgreSQL 16 + pgcrypto + btree_gist |
| **缓存 / 消息** | Redis (读写缓存 + 会话管理) |
| **ORM** | SQLAlchemy 2.0 (asyncpg) |
| **前端** | React 18 + TypeScript + Vite |
| **路由** | TanStack Router |
| **状态管理** | TanStack Query + Zustand |
| **图表** | ECharts + Lightweight Charts |
| **PWA** | vite-plugin-pwa + Workbox |
| **国际化** | i18next (zh-CN / en 双语文案) |
| **包管理** | uv (Python) / npm (前端) |
| **产物体积** | 后端 ~46,000 loc / 前端 ~3,400 loc / SQL ~450 loc |

---

## 2. 核心功能

### 2.1 市场门控 (Market Regime) — §3.5

基于 VIX 水平和 SPX 与 20 日均线偏离度判定市场状态：

- **Normal (正常)**: Threat Score 红灯阈值 = 70
- **Panic (恐慌)**: 阈值自动上调至 80，所有看空信号权重放大，看多信号权重降低

判定逻辑实现于 `app/services/regime.py` 和 `regime_history.py`，VIX 缺失或 SPX 数据不全时默认走 Normal 容忍分支。

### 2.2 四大风险模块

#### 模块一：期权异常分布 (Options Anomaly) — §3.1

监控末日 Put 期权的异常建仓行为，过滤条件：

- DTE ≤ 3 个交易日
- 虚值 > 10% (个股) 或 > 5% (ETF)
- Volume > 5 × Open Interest
- OI 日增幅 > 50%
- 按名义金额取 Top 10

服务端实现于 `app/services/options_anomaly.py`。

#### 模块二：做空水位 (Short Iceberg) — §3.2

追踪机构做空力量的隐蔽聚集程度：

- **Short Ratio**: 做空量 / 总成交量
- **60 日滚动 Z-Score**: 衡量当前做空比例相对历史分布的极端程度
- **ATS Dark Pool Penetration**: 暗池做空占总量比例

服务端实现于 `app/services/short_metrics.py`，ETL 落库于 `etl/load_short_ratio.py`。

#### 模块三：量价背离 (Divergence) — §3.3

监控价格与做空量斜率之间的背离：

- **状态机**: `none` → `rising` (量升价横/价微跌) → `confirmed` (连续 2 日确认)
- **价格分位 (P_price)**: 10 日价格斜率的历史分位
- **做空量分位 (P_short)**: 10 日做空量斜率的历史分位

服务端实现于 `app/services/divergence.py`，ETL 落库于 `etl/load_divergence.py`。

#### 模块四：内部人行为 (Insider) — §3.4

解析 SEC Form 4 中 C-Level / Director / 10% Holder 的买卖行为，按方向与金额打分。服务端实现于 `app/services/insider.py`。

### 2.3 Threat Score — §3.5

四大模块的加权合成评分 (0–100)：

| 标的类型 | Options | Short | Divergence | Insider |
|----------|---------|-------|------------|---------|
| **个股** | 30% | 35% | 20% | 15% |
| **ETF** | 35% | 45% | 20% | — |

EMA 平滑 (半衰期 2 交易日) 防毛刺。信号生命周期 5 色灯：

- 🔴 Red ≥ 阈值 (Normal 70 / Panic 80)
- 🟡 Yellow ≥ 50
- ⬜ Gray ≥ 30
- 🟢 Green < 30
- 🔵 Init (冷启动期)

### 2.4 终极警报 (Ultimate Alert) — §3.5

当多个模块在同一天发生共振时触发，条件：

1. Threat Score EMA ≥ regime 阈值
2. 至少 1 个核心模块连续 ≥ 2 个交易日同向高分
3. 24h 防抖 (同标的至多触发 1 次)
4. 严禁基于单日原始分触发

实现于 `app/services/ultimate_alert.py`。

### 2.5 Screener — 每日猎物榜单

按 Threat Score 降序排列所有监控标的，展示活跃模块标记和信号生命周期颜色。支持 12h Redis 缓存 (`cache_ttl_report_seconds = 43200`)。

### 2.6 LLM 分析面板

前端集成 DeepSeek / Gemini 分析面板，默认使用量化风控分析师提示词。用户可切换快捷标签或自由编辑提示词。后端通过 `app/api/llm.py` 代理请求。

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                       前端 (Vite + React 18 + TS)         │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │Regime   │ │Screener  │ │Symbol    │ │LLM Panel    │ │
│  │Banner   │ │榜单      │ │指标详情   │ │AI 分析      │ │
│  └─────────┘ └──────────┘ └──────────┘ └─────────────┘ │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │Basket   │ │Alerts    │ │Data      │ │Threat       │ │
│  │自选篮   │ │预警规则   │ │Status    │ │Gauge/Chart  │ │
│  └─────────┘ └──────────┘ └──────────┘ └─────────────┘ │
├─────────────────────────────────────────────────────────┤
│                  API Gateway (FastAPI)                    │
│  /api/v1/regime  /api/v1/screener  /api/v1/symbols/*    │
│  /api/v1/baskets  /api/v1/alert-rules  /api/v1/llm/*    │
├─────────────────────────────────────────────────────────┤
│                     Service Layer                         │
│  threat_score  regime  divergence  short_metrics         │
│  options_anomaly  insider  ultimate_alert  etf_proxy     │
├─────────────────────────────────────────────────────────┤
│                  ETL Pipeline (etl/)                      │
│  yfinance_pull → finra_short → sec_form4                 │
│  → load_short_ratio → load_divergence → load_threat_score│
├─────────────────────────────────────────────────────────┤
│               Data Stores                                │
│  ┌──────────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ PostgreSQL 16    │  │ Redis    │  │ Static Files   │  │
│  │ (hunter_radar)   │  │ (cache)  │  │ (Vite dist/)   │  │
│  └──────────────────┘  └──────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 3.1 后端分层

```
backend/
├── app/
│   ├── api/            # 路由控制器 (21 个路由文件)
│   │   ├── symbols.py      # 标的核心数据 (threat / divergence / options / short / 8k)
│   │   ├── regime.py       # 市场门控
│   │   ├── screener.py     # 每日猎物榜单
│   │   ├── basket.py       # 自选篮子 CRUD
│   │   ├── alerts.py       # 预警规则
│   │   ├── llm.py          # AI 分析代理
│   │   ├── admin.py        # 管理端点 (ETL / backtest / webhook replay)
│   │   ├── push.py         # Web Push 订阅
│   │   ├── etf.py          # ETF 申赎代理
│   │   ├── edgar.py        # EDGAR 查询
│   │   ├── eight_k.py      # 8-K 事件流
│   │   ├── analytics.py    # 埋点分析
│   │   ├── data_status.py  # 数据状态灯
│   │   ├── health.py       # 健康检查
│   │   └── ...
│   ├── core/           # 基础设施
│   │   ├── config.py       # pydantic-settings 配置中心
│   │   ├── database.py     # SQLAlchemy async engine + session
│   │   ├── auth.py         # JWT / Magic Link 鉴权
│   │   └── redis_client.py # Redis 连接池
│   ├── services/       # 业务逻辑 (纯计算，依赖数据库)
│   │   ├── threat_score.py      # Threat Score 计算 + EMA
│   │   ├── regime.py            # 市场门控判定
│   │   ├── divergence.py        # 量价背离
│   │   ├── options_anomaly.py   # 末日 Put 异常
│   │   ├── short_metrics.py     # 做空水位 Z-Score / ATS
│   │   ├── ultimate_alert.py    # 终极警报触发
│   │   ├── insider.py           # Form 4 内部人
│   │   ├── etf_proxy.py         # ETF 代理指标
│   │   └── ...
│   └── models/          # ORM 模型定义
├── etl/                # ETL 数据采集 + 落库 (12 个文件)
│   ├── pipeline.py          # 集中编排器
│   ├── yfinance_pull.py     # Yahoo Finance 拉取
│   ├── finra_short.py       # FINRA 做空数据抓取
│   ├── sec_form4.py         # SEC Form 4 抓取
│   ├── load_daily_price.py  # 日线落库
│   ├── load_short_ratio.py  # 做空比例计算
│   ├── load_divergence.py   # 背离计算
│   ├── load_options_chain.py # 期权链落库
│   ├── load_threat_score.py # Threat Score 汇总
│   └── ...
├── sql/
│   ├── 00_init.sql          # 完整 Schema
│   └── migrations/          # Alembic 迁移
├── dags/                    # Airflow DAG (预留)
├── pyproject.toml           # 依赖 + 工具链配置
└── control.sh               # 启动/停止/重启/日志脚本
```

### 3.2 前端分层

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
│   │   └── common/       # 通用组件
│   │       ├── LlmPanel.tsx          # AI 分析面板
│   │       ├── LogPanel.tsx          # 实时日志流
│   │       ├── DataStatusBanner.tsx  # 数据状态灯
│   │       └── ...
│   ├── routes/           # 页面路由 (TanStack Router)
│   │   ├── __root.tsx          # 根布局
│   │   ├── index.tsx           # 首页
│   │   ├── screener.tsx        # 猎物榜单
│   │   ├── symbol.$ticker.tsx  # 标的详情页
│   │   ├── alerts.tsx          # 预警规则配置
│   │   └── basket.tsx          # 自选篮子
│   ├── features/         # 自定义 Hooks
│   │   ├── useSignalLifecycle.ts  # 信号生命周期
│   │   ├── useThreatHistory.ts    # Threat Score 历史
│   │   ├── useUltimateAlert.ts    # 终极警报
│   │   └── ...
│   ├── lib/              # 工具层
│   │   ├── api.ts          # API 客户端
│   │   └── queryClient.ts  # React Query 配置
│   └── i18n/             # 国际化文案 (zh-CN / en)
└── package.json
```

---

## 4. 数据管道

### 4.1 ETL 执行顺序

```
┌─────────────────────────────────────────────────────────┐
│              run_daily_pipeline(trade_date)              │
├─────────────────────────────────────────────────────────┤
│ 1. yfinance EOD bars → load_daily_price                 │
│                                                         │
│ 2. FINRA short_volume → load_short_volume               │
│                                                         │
│ 3. FINRA ATS → load_ats_short (M2 后接入)               │
│                                                         │
│ 4. yfinance options_chain → load_options_chain          │
│    → compute_option_anomaly (末日 Put 异常过滤)          │
│                                                         │
│ 5. SEC Form 4 → load_form4 + load_buyback               │
│                                                         │
│ 6. compute_etf_proxy (折溢价指标)                        │
│                                                         │
│ 7. 派生计算:                                             │
│    compute_short_ratio → short_ratio_daily               │
│    compute_divergence → divergence_window                │
│                                                         │
│ 8. compute_regime (市场门控)                             │
│    → compute_threat_scores (Threat Score 汇总)           │
│    → backfill regime 到 threat_score_daily               │
│                                                         │
│ 9. refresh_data_status (全局数据状态灯)                   │
└─────────────────────────────────────────────────────────┘
```

### 4.2 冷启动 (数据累积)

- 需要至少 **30 个交易日**的历史数据才能产生完整的 Threat Score
- Z-Score (60 日滚动) 前 60 天为 null
- 所有 API 返回均带 `data_warmup` 标记表示冷启动状态

### 4.3 运行方式

```bash
# CLI 单次运行
cd hunter-radar/backend
uv run python -m etl.pipeline 2026-06-26

# 服务管理
cd hunter-radar
./control.sh start   # 启动 API Server (端口 8000)
./control.sh stop
./control.sh restart
./control.sh log     # 查看日志

# 开发模式
cd hunter-radar/frontend && npm run dev   # 前端开发 (端口 5173)
cd hunter-radar/backend && uv run uvicorn app.main:app --reload  # 后端热重载
```

---

## 5. API 接口文档

### 5.1 基础信息

| 项目 | 值 |
|------|-----|
| Base URL | `http://<host>:8000` |
| OpenAPI 文档 | `/docs` (Swagger UI) 或 `/redoc` |
| OpenAPI JSON | `/openapi.json` |
| Content-Type | `application/json` |
| 缓存 | Screener / Threat Score 等读端点 12h Redis 缓存 |

### 5.2 市场状态

| 方法 | 路径 | 说明 | 返回值 |
|------|------|------|--------|
| GET | `/api/v1/regime` | 市场门控 | `trade_date`, `regime` (normal/panic), `vix`, `spx_close`, `spx_ma20`, `threshold_red`, `banner_text` |
| GET | `/health` | 健康检查 | `status: "ok"`, `version`, `db`, `redis` |

### 5.3 标的核心数据

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/symbols/{ticker}/threat` | 最新 Threat Score (4 模块分解 + 权重 + lifecycle) |
| GET | `/api/v1/symbols/{ticker}/threat-history` | 90 日 Threat Score 轨迹 (12h 缓存) |
| GET | `/api/v1/symbols/{ticker}/options-anomaly` | 末日 Put 异常合约列表 |
| GET | `/api/v1/symbols/{ticker}/short-iceberg` | 做空水位图 (short_ratio + ats_short_pct + z_score_60d) |
| GET | `/api/v1/symbols/{ticker}/divergence` | 量价背离 (价格/做空斜率 + 状态机) |
| GET | `/api/v1/symbols/{ticker}/ultimate-alert` | 最近一条终极警报 |
| GET | `/api/v1/symbols/{ticker}/8k` | 8-K Item 8.01 重大事件 |
| GET | `/api/v1/symbols/lookup` | 搜素自动补全 |

### 5.4 猎物榜单 & 数据状态

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/screener` | 每日 Threat Score 排名 (Top N, 12h 缓存) |
| GET | `/api/v1/data-status` | 全局数据状态 (ETL 覆盖情况) |

### 5.5 用户功能

| 方法 | 路径 | 说明 |
|------|------|------|
| POST / GET | `/api/v1/baskets` | 创建 / 列表自选篮子 |
| GET / PUT / DELETE | `/api/v1/baskets/{basket_id}` | 篮子详情 / 修改 / 删除 |
| POST / GET | `/api/v1/baskets/{basket_id}/members` | 增 / 查篮子成员 |
| DELETE | `/api/v1/baskets/{basket_id}/members/{ticker}` | 删除篮子成员 |
| GET | `/api/v1/baskets/{basket_id}/distribution` | 篮子风险分布快照 |

### 5.6 预警推送

| 方法 | 路径 | 说明 |
|------|------|------|
| POST / GET | `/api/v1/alert-rules` | 创建 / 列表预警规则 |
| GET / PUT / DELETE | `/api/v1/alert-rules/{rule_id}` | 规则详情 / 修改 / 删除 |
| POST | `/api/v1/alert-rules/{rule_id}/eval` | 规则评估 + 推送 (已落地 email) |
| POST / GET | `/api/v1/push/subscriptions` | 新增 / 列表 Web Push 订阅 |
| DELETE | `/api/v1/push/subscriptions/{sub_id}` | 软删订阅 |
| GET | `/api/v1/push/vapid-public-key` | VAPID 公钥 (无需鉴权) |

### 5.7 AI 分析

| 方法 | 路径 | 说明 | 请求体 |
|------|------|------|--------|
| POST | `/api/v1/llm/analyze` | LLM 分析标的 (代理 DeepSeek/Gemini) | `{ticker, model, prompt, context?}` |

**请求示例**:

```json
{
  "ticker": "INTC",
  "model": "deepseek-v4-pro",
  "prompt": "你现在是一位拥有20年经验的华尔街量化风控分析师...",
  "context": "{\"symbol\":\"INTC\",\"threat_score\":63.81,...}"
}
```

### 5.8 管理端点

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/admin/etl/run` | 触发 ETL (BD-085) | admin |
| POST | `/api/v1/admin/backtest/run` | 触发回测 (v3.0) | admin |
| GET | `/api/v1/admin/backtest/result` | 读回测结果 | admin |
| POST | `/api/v1/admin/webhook/replay` | 重放 sandbox webhook | super_admin |

### 5.9 其他端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/events/8k` | 全市场 8-K 事件流 |
| POST | `/api/v1/events/8k/classify` | 8-K 文本分类 |
| GET | `/api/v1/edgar/categories` | EDGAR 4 类 category |
| GET | `/api/v1/edgar/search` | EDGAR 全文搜索 |
| GET | `/api/v1/etf/premium-discount` | ETF 溢价/折价 (真实代理) |
| GET / POST | `/api/v1/etf/basket` `/orders` | ETF 申赎 (sandbox stub) |
| GET | `/api/v1/analytics/events` | 埋点事件 |
| GET | `/api/v1/feature-flags` | 灰度开关 |
| GET | `/api/v1/auth/quota` | 配额查询 |
| GET | `/api/v1/logs/history` `/stream` | 日志查询 / SSE 流 |

---

## 6. 数据库设计

### 6.1 数据库概览

- **数据库**: PostgreSQL 16, 库名 `hunter_radar`
- **扩展**: `pgcrypto` (UUID 生成), `btree_gist` (复合索引)
- **初始化**: `psql -U hunter -d hunter_radar -f sql/00_init.sql`
- **迁移**: Alembic (推荐), 或手动执行 `sql/migrations/`

### 6.2 核心表结构

#### 标的元信息

| 表名 | 说明 | 主键 |
|------|------|------|
| `symbol_master` | 标的元信息 (ticker, name, type, exchange, is_universe) | ticker (TEXT) |

#### 数据源原始表

| 表名 | 数据源 | 关键字段 |
|------|--------|----------|
| `short_volume` | FINRA | trade_date, symbol, short_volume, non_short_volume, total_volume |
| `ats_short` | FINRA ATS | trade_date, symbol, ats_short_volume, venue_pool |
| `daily_price` | Yahoo Finance | trade_date, symbol, open, high, low, close, adj_close, volume |
| `options_chain` | Yahoo Finance | trade_date, symbol, contract, expiry, strike, right, volume, open_interest, implied_vol |
| `form4_event` | SEC EDGAR | symbol, insider_name, insider_role, txn_date, direction, qty, price |

#### 计算产物表

| 表名 | 派生自 | 关键字段 |
|------|--------|----------|
| `short_ratio_daily` | short_volume + ats_short | short_ratio, z_score_60d, ats_short_pct |
| `option_anomaly` | options_chain | dte, oi_increase_pct, volume_oi_ratio, notional |
| `divergence_window` | daily_price + short_volume | price_slope_10d, short_slope_10d, p_price, p_short, divergence_state |
| `etf_proxy_metrics` | daily_price | close, inav, premium_pct, volume_vs_ma20, proxy_signal |
| `threat_score_daily` | 四个模块汇总 | module_options, module_short, module_divergence, module_insider, total, total_raw, ema_halflife, signal_lifecycle, regime |
| `ultimate_alert` | threat_score_daily | triggered_at, threat_score, modules_active, regime, consecutive_days |

#### 用户功能表

| 表名 | 说明 |
|------|------|
| `app_user` | 用户 (id UUID, email, auth_provider, is_pro, quota) |
| `subscription_event` | Stripe 订阅事件 |
| `basket` | 用户自选篮子 |
| `basket_member` | 篮子成员 |
| `basket_snapshot` | 篮子风险分布快照 |
| `daily_screener` | 每日猎物榜单排名 |
| `alert_rule` | 预警规则 (DSL + channels) |
| `alert_event` | 预警触发历史 |
| `data_ingestion_status` | 数据状态灯 |

### 6.3 关键索引策略

```sql
-- 做空数据按日期+标的查询
CREATE INDEX idx_short_volume_date_sym ON short_volume (trade_date DESC, symbol);

-- Threat Score 按日期+分数排名 (Screener 查询)
CREATE INDEX idx_threat_date_score ON threat_score_daily (trade_date DESC, total DESC);

-- 期权按标的+到期日 (末日 Put 过滤)
CREATE INDEX idx_options_sym_expiry ON options_chain (symbol, expiry);

-- 自选篮子唯一约束
UNIQUE (basket_id, symbol)
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

### 7.2 核心组件

#### ThreatScoreGauge

半圆形仪表盘，展示 0–100 的 Threat Score。颜色随 `signal_lifecycle` 变化，中间显示平滑前/后两个分值。

#### ModuleSignalLight

四格信号灯矩阵，每格对应一个模块分值，颜色渐变：绿色 (0–30) → 灰色 (30–50) → 黄色 (50–70) → 红色 (70–100)。

#### ThreatHistoryChart

ECharts 时序折线图，显示 90 个交易日的 Threat Score EMA 轨迹 + 红线阈值标注。

#### UltimateAlertOverlay

全屏弹窗，展示终极警报的触发标的、得分、活跃模块、连续天数。按 `trade_date:triggered_at` 去重，用户关闭后才可再次弹出。

#### LlmPanel

AI 分析面板，默认加载量化风控分析师完整提示词模板。支持 DeepSeek 和 Gemini 双模型，5 个快捷提示词标签，输入框可自由编辑。后端 API 代理转发。

### 7.3 PWA 支持

前端使用 `vite-plugin-pwa` + Workbox 实现：

- **离线缓存**: 10 个预缓存条目 (~380 KB)
- **Web Push**: 使用 VAPID 协议，管理员可向订阅用户推送预警
- **Service Worker**: 自动注册 + 更新提示

### 7.4 国际化

双语文案 (zh-CN / en) 使用 i18next：

```typescript
// 组件中
const { t } = useTranslation();
t("modules.options");  // → "期权分布" / "Options"
```

文案文件位于 `src/i18n/zh-CN.json`。

---

## 8. 部署运维

### 8.1 环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | ≥ 3.12 | 后端运行时 |
| Node.js | ≥ 18 | 前端构建 |
| PostgreSQL | 16 | 主数据库 |
| Redis | ≥ 6 | 缓存 + 会话 |

### 8.2 环境变量

后端读取 `.env` 文件 (pydantic-settings)。关键配置项：

```ini
# 数据库
DATABASE_URL=postgresql+asyncpg://hunter:hunter@localhost:5432/hunter_radar
REDIS_URL=redis://localhost:6379/0

# API Keys
DEEPSEEK_API_KEY=sk-***
GEMINI_API_KEY=***

# Sentry
SENTRY_DSN=https://***@sentry.io/***

# Web Push
VAPID_PRIVATE_KEY=***
VAPID_PUBLIC_KEY=***

# Stripe
STRIPE_SECRET_KEY=sk_live_***
```

### 8.3 服务端口

| 服务 | 端口 | 绑定 |
|------|------|------|
| FastAPI Backend | 8000 | 0.0.0.0 |
| Vite Dev Server | 5173 | localhost |

### 8.4 生产构建

```bash
# 1. 初始化数据库
psql -U hunter -d hunter_radar -f backend/sql/00_init.sql

# 2. 前端构建 (产物至 dist/)
cd hunter-radar/frontend && npm run build

# 3. 启动后端 (自动 serve 前端静态文件)
cd hunter-radar/backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. 运行 ETL (可选, cron 或 Airflow)
uv run python -m etl.pipeline
```

---

## 9. 开发路线图

### 已完成 (M0–M7)

- [x] M0: 项目骨架 + FastAPI 应用入口
- [x] M1: 数据库 Schema + 种子数据 + 沙箱 ETL
- [x] M2: 真实数据 ETL (FINRA / Yahoo / SEC) + 派生计算
- [x] M3: Threat Score / 信号生命周期 / 终极警报
- [x] M4: 篮子系统 + Screener 榜单
- [x] M5: 预警规则 + 推送 (Email + Web Push)
- [x] M6: 灰度系统 + 8-K 事件流
- [x] M7: V1.5 接力 (ETF 代理 / EDGAR / 管理端点 / LLM 面板)

### 当前版本 (V1.4.0 → V1.5.x)

- [x] PWA 离线支持
- [x] LLM 分析面板 (DeepSeek / Gemini)
- [x] ETF 折溢价代理指标 (真实数据)
- [x] 管理端点 (Admin Role)
- [x] SEC Form 4 内部人 + 8-K 事件

### 待办 / 路线图

- [ ] CI/CD 流水线 (GitHub Actions)
- [ ] Airflow DAG 正式编排 ETL
- [ ] 暗池 ATS 真实周报接入
- [ ] EDGAR XBRL Full-Text 搜索
- [ ] 回测框架 v3.0 全量 Goldset 评估
- [ ] 移动端 React Native / PWA 增强

---

> **Disclaimer**: Hunter Radar 仅供研究参考，不构成任何投资建议。  
> 所有数据来自公开金融监管源与市场数据供应商，项目不承担因数据延迟、丢失或解读而产生的任何责任。

---

_最后更新: 2026-06-28 | Version: V1.4.0_
