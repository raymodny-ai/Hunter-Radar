# Hunter Radar — 项目说明文档

> 版本: V1.6.0 · 最后更新: 2026-06-15

---

## 目录

1. [项目概述](#1-项目概述)
2. [架构设计](#2-架构设计)
3. [技术栈](#3-技术栈)
4. [目录结构](#4-目录结构)
5. [数据库设计](#5-数据库设计)
6. [数据管道 (ETL Pipeline)](#6-数据管道-etl-pipeline)
7. [核心功能模块](#7-核心功能模块)
8. [API 接口文档](#8-api-接口文档)
9. [前端开发](#9-前端开发)
10. [CI/CD 与部署](#10-cicd-与部署)
11. [环境变量与配置](#11-环境变量与配置)
12. [开发与测试](#12-开发与测试)

---

## 1. 项目概述

### 1.1 产品定位

**Hunter Radar** 是一款面向美股投资者的**另类数据风险分析平台**。系统从 FINRA 全监管做空、SEC EDGAR 内部人交易、Yahoo Finance 期权链与日 K 线四大公开数据源自动采集数据,通过多维共振分析模型计算每只标的的 **Threat Score(威胁评分)**,帮助用户快速识别潜在的异常波动风险。

### 1.2 核心理念

- **四维共振**: 期权异常 + 做空压力 + 量价背离 + 内部人抛压,多信号叠加增强可信度
- **EMA 防毛刺**: 指数移动平均平滑(半衰期 2 交易日),杜绝单日尖峰误触发终极警报
- **市场门控**: VIX / SPX MA20 动态调整阈值,恐慌期自动上调红灯标准
- **合规红线**: 严禁输出投资建议类措辞("建议买入/卖出"等),CI 自动拦截

### 1.3 版本历史

| 版本 | 里程碑 | 核心特性 |
|------|--------|----------|
| V1.4 | 初版上线 | FastAPI + 5 模组 ETL + Threat Score + Screener + 订阅制 |
| V1.5.1 | 接力期 | EDGAR 全文搜索 + ETF 申赎代理 + Analytics 端点 |
| V1.5.9 | ATS 增强 | ATS 暗池 fallback 爬虫 + Options V2 (PCR/Gamma/OTM) + 动态权重 |
| V1.6.0 | 全面优化 | 多源冗余 + ML 权重优化 + VWMA 去噪 + 物化视图 + RAG + Docker 容器化 |

---

## 2. 架构设计

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│   TanStack Router · React Query · Tailwind · ECharts · PWA     │
│   Vite · TypeScript · i18n (zh-CN)                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │ /api/v1/*  (Vite proxy → :8000)
┌─────────────────────────▼───────────────────────────────────────┐
│                    Backend (FastAPI)                             │
│   asyncpg · SQLAlchemy 2.0 · Pydantic v2 · Redis · structlog   │
│   Sentry · Stripe · Web Push (VAPID)                            │
├──────────────┬──────────────┬───────────────┬───────────────────┤
│  /api/v1/*   │  /health     │  /docs        │  /openapi.json    │
│  REST APIs   │  Healthcheck │  Swagger UI   │  OpenAPI Schema   │
└──────┬───────┴──────────────┴───────────────┴───────────────────┘
       │                          │
┌──────▼───────┐          ┌──────▼───────┐
│  PostgreSQL  │          │    Redis     │
│  16-alpine   │          │  7-alpine    │
│  + pgvector  │          │  Cache/PubSub│
└──────────────┘          └──────────────┘
       ▲
       │
┌──────┴──────────────────────────────────────────────────────────┐
│                     ETL Pipeline                                 │
│  Airflow DAG (EOD 22:00 UTC) / CLI: python -m etl.pipeline     │
│  FINRA → Yahoo → SEC → Options → Short Ratio → Divergence      │
│  → Regime → Threat Score → Screener MV Refresh                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心设计模式

| 模式 | 应用位置 | 说明 |
|------|----------|------|
| ABC 抽象接口 | `MarketDataProvider` | 数据源热插拔,YFinance / AlphaVantage 实现统一契约 |
| Manager 降级 | `DataProviderManager` | 主源失败 → 备份源 → 缓存兜底,三级降级 |
| EMA 平滑 | `threat_score.py` | 半衰期 2 日,防止单日尖峰误触发 |
| ML 动态权重 | `weight_optimizer.py` | LinearRegression R² 自动调整各模块权重 |
| 物化视图 | `mv_screener_top100` | 预计算 Top 100,CONCURRENTLY 刷新 |
| RAG 增强 | `rag_knowledge_base.py` | pgvector + sentence-transformers,历史公告检索注入 LLM |
| 重试策略 | `retry_policy.py` | tenacity 指数退避,3 次重试,min=5s max=60s |
| 信号归因 | `attribution.py` | 各模块 weight×score 贡献度 + 瀑布图数据 |
| 数据校验 | `validation.py` | 4 类校验(日K/做空/Form4/期权),标记异常不丢弃 |

---

## 3. 技术栈

### 3.1 后端

| 领域 | 技术 | 版本 |
|------|------|------|
| Web 框架 | FastAPI | ≥ 0.115 |
| ASGI 服务器 | Uvicorn | ≥ 0.32 |
| 数据验证 | Pydantic v2 | ≥ 2.9 |
| ORM | SQLAlchemy 2.0 (asyncio) | ≥ 2.0.36 |
| 异步驱动 | asyncpg | ≥ 0.30 |
| 数据库迁移 | Alembic | ≥ 1.13 |
| 缓存 | Redis | ≥ 5.2 |
| HTTP 客户端 | httpx | ≥ 0.27 |
| 重试框架 | tenacity | ≥ 9.0 |
| 数据处理 | pandas / numpy / scipy | — |
| 行情数据 | yfinance | ≥ 0.2.50 |
| 爬虫 | Playwright + stealth | — |
| 认证 | AuthLib (OAuth/Magic Link) | ≥ 1.3 |
| 支付 | Stripe | ≥ 11.0 |
| 推送 | pywebpush (VAPID) | ≥ 2.0 |
| 监控 | Sentry SDK | ≥ 2.16 |
| 结构化日志 | structlog | ≥ 24.4 |
| JSON 序列化 | orjson | ≥ 3.10 |
| 向量搜索 | pgvector + sentence-transformers | — |

### 3.2 前端

| 领域 | 技术 | 版本 |
|------|------|------|
| 框架 | React 18 | ^18.3 |
| 路由 | TanStack Router | ^1.81 |
| 数据层 | TanStack React Query | ^5.59 |
| 样式 | Tailwind CSS 3 | ^3.4 |
| 图表 | ECharts + lightweight-charts | — |
| UI 组件 | Radix UI | — |
| 国际化 | i18next + react-i18next | — |
| 表单 | react-hook-form + zod | — |
| 状态管理 | zustand | ^4.5 |
| 构建工具 | Vite 5 | ^5.4 |
| PWA | vite-plugin-pwa + workbox | — |
| 类型生成 | openapi-typescript | ^7.4 |
| 监控 | @sentry/react | ^10.62 |

### 3.3 基础设施

| 组件 | 技术 |
|------|------|
| 数据库 | PostgreSQL 16 (Alpine) |
| 缓存 | Redis 7 (AOF 持久化) |
| 调度 | Apache Airflow 2.10 |
| 容器 | Docker 多阶段构建 |
| CI/CD | GitHub Actions |
| 测试 | pytest + vitest + Playwright E2E |
| 性能审计 | Lighthouse CI |
| 可访问性 | WCAG 审计 |

---

## 4. 目录结构

```
hunter-radar/
├── .github/workflows/         # CI/CD
│   ├── ci.yml                 # 主 CI(9 jobs)
│   ├── lighthouse-perf.yml    # Lighthouse 性能审计
│   ├── playwright-e2e.yml     # E2E 测试
│   └── wcag-audit.yml         # WCAG 可访问性审计
│
├── backend/                   # 后端(FastAPI + ETL)
│   ├── app/
│   │   ├── api/               # REST 端点(21 个模块)
│   │   │   ├── admin.py       # Admin ETL/Backtest/Webhook
│   │   │   ├── alerts.py      # 预警规则 CRUD
│   │   │   ├── analytics.py   # 分析事件
│   │   │   ├── attribution.py # 信号归因(V1.6.0)
│   │   │   ├── basket.py      # 自选篮子
│   │   │   ├── data_status.py # 数据状态灯
│   │   │   ├── edgar.py       # EDGAR 全文搜索
│   │   │   ├── eight_k.py     # 8-K 重大事件流
│   │   │   ├── etf.py         # ETF 申赎代理
│   │   │   ├── feature_flags.py # 灰度发布
│   │   │   ├── health.py      # 健康检查
│   │   │   ├── llm.py         # LLM 分析(RAG 增强)
│   │   │   ├── log_stream.py  # SSE 日志流
│   │   │   ├── push.py        # Web Push
│   │   │   ├── quota.py       # 配额查询
│   │   │   ├── regime.py      # 市场门控
│   │   │   ├── regime_timeline.py # 市场切换时间轴(V1.6.0)
│   │   │   ├── screener.py    # 猎物榜单
│   │   │   └── symbols.py     # 标的详情/Threat Score/期权/做空/背离
│   │   ├── core/
│   │   │   ├── config.py      # 全局配置(Pydantic Settings)
│   │   │   ├── database.py    # SQLAlchemy async engine
│   │   │   └── redis_client.py # Redis 客户端
│   │   ├── models/            # ORM 模型
│   │   ├── schemas/           # Pydantic DTO
│   │   ├── services/          # 业务逻辑(27 个服务)
│   │   └── main.py            # FastAPI 应用入口
│   ├── dags/                  # Airflow DAG
│   │   ├── hunter_radar_eod.py # 每日 EOD 主流水线
│   │   ├── ats_cron.py        # ATS 暗池定时任务
│   │   └── options_cron.py    # 期权轮询定时任务
│   ├── etl/                   # ETL 模块(26 个文件)
│   │   ├── pipeline.py        # 集中编排器
│   │   ├── market_data_provider.py # 多源冗余框架(V1.6.0)
│   │   ├── validation.py      # 数据校验层(V1.6.0)
│   │   ├── retry_policy.py    # 统一重试策略(V1.6.0)
│   │   ├── yfinance_pull.py   # Yahoo Finance 拉取
│   │   ├── finra_short.py     # FINRA 做空拉取
│   │   ├── sec_form4.py       # SEC Form 4 拉取
│   │   ├── ats_scraper.py     # ATS 暗池 fallback 爬虫
│   │   ├── load_*.py          # 各模块入库逻辑
│   │   ├── symbol_seed.py     # 标普 500 + 主流 ETF 种子数据
│   │   └── proxy_pool.py      # 代理池
│   ├── scripts/               # 自测脚本(73 个脚本 / 1602 测点)
│   │   ├── m8t1_test_regression.py # 回归测试聚合器
│   │   ├── m19t*.py           # V1.6.0 自测(6 脚本 × 25 测点)
│   │   ├── freeze_check.py    # OpenAPI freeze 校验
│   │   └── self_test_harness.py # 静态分析 harness
│   ├── sql/                   # SQL Schema
│   │   ├── 00_init.sql        # 初始化(20+ 张表)
│   │   ├── 01_v1.5.9_options_ats.sql
│   │   ├── 02_v1.6.0_materialized_views.sql
│   │   ├── 03_v1.6.0_rag.sql  # pgvector + RAG
│   │   └── migrations/
│   ├── tests/                 # pytest 测试
│   ├── Dockerfile             # 多阶段构建
│   ├── .dockerignore
│   └── pyproject.toml         # Python 项目配置
│
├── frontend/                  # 前端(React + Vite)
│   ├── src/
│   │   ├── components/
│   │   │   ├── common/        # 通用组件(9 个)
│   │   │   └── radar/         # 雷达专用组件(7 个)
│   │   ├── features/          # 自定义 Hooks(8 个)
│   │   ├── i18n/              # 国际化(zh-CN)
│   │   ├── lib/               # 工具库(api/queryClient/sentry)
│   │   ├── routes/            # 页面路由(8 个)
│   │   ├── router.tsx         # TanStack Router
│   │   └── main.tsx           # 应用入口
│   ├── public/
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── package.json
│
├── infra/
│   └── docker-compose.yml     # 基础设施编排(7 个服务)
│
├── docker/
│   └── control.sh             # Docker 控制脚本
│
├── docs/                      # 项目文档
├── data/                      # 数据文件
└── scripts/                   # 顶层脚本
```

---

## 5. 数据库设计

### 5.1 Schema 概览

数据库使用 PostgreSQL 16,启用 `pgcrypto` + `btree_gist` + `pgvector` 扩展。

### 5.2 核心表

#### 5.2.1 标的元信息

| 表名 | 用途 | 主键 |
|------|------|------|
| `symbol_master` | 标的元信息(ticker/name/type/exchange) | ticker (TEXT) |

支持的标的类型: `stock` / `etf` / `index` / `crypto` / `adr`

#### 5.2.2 数据采集表

| 表名 | 数据源 | 说明 |
|------|--------|------|
| `daily_price` | Yahoo Finance | 日 K 线(OHLCV + adj_close) |
| `short_volume` | FINRA | 全监管做空量(short/non_short/total) |
| `ats_short` | FINRA ATS | 暗池做空量(含 fallback source) |
| `options_chain` | Yahoo Finance | 期权链(合约/行权价/到期日/Greeks) |
| `form4_event` | SEC EDGAR | 内部人交易(buy/sell/grant/exercise) |
| `buyback_event` | SEC EDGAR | 回购公告(8-K/10-Q/10-K) |
| `etf_primary_flow` | ETF 发行商 | 一级市场申赎(V1.5 实装) |

#### 5.2.3 计算产物表

| 表名 | 计算逻辑 | 说明 |
|------|----------|------|
| `short_ratio_daily` | short/total + Z-Score 60d | 做空比例 + 暗池占比 |
| `option_anomaly` | DTE ≤ 7 末日 Put 异常 | OI 激增 + Volume/OI 比 + 信号强度 |
| `option_pcr_daily` | PCR + Gamma 聚集 + OTM 刺客 | V1.5.9 期权 V2 聚合指标 |
| `divergence_window` | 10d 价格/做空斜率 + 分位数 | 量价背离(rising/confirmed) |
| `etf_proxy_metrics` | close vs INAV + volume_vs_ma20 | ETF 折溢价代理信号 |
| `threat_score_daily` | 四维加权 + EMA 平滑 | 核心评分(0-100) + 信号灯 |
| `ultimate_alert` | 连续红灯 + 去抖 | 终极警报触发记录 |
| `daily_screener` | 全市场 Top N 排名 | 猎物榜单 |

#### 5.2.4 用户与运营表

| 表名 | 说明 |
|------|------|
| `app_user` | 用户(email/OAuth/is_pro/quota) |
| `subscription_event` | Stripe 订阅事件 |
| `basket` / `basket_member` / `basket_snapshot` | 自选篮子 |
| `alert_rule` / `alert_event` | 预警规则 + 触发事件 |
| `data_ingestion_status` | 数据状态灯(ready/pending/failed/skipped) |
| `backtest_event_goldset` / `backtest_dataset` | 回测金标集 + 数据集 |

#### 5.2.5 V1.6.0 新增

| 表/视图 | 说明 |
|---------|------|
| `mv_screener_top100` | 物化视图,预计算 Top 100,CONCURRENTLY 刷新 |
| `knowledge_documents` | RAG 知识库文档(含 pgvector embedding 列) |

### 5.3 Threat Score 信号灯规则

| 信号灯 | 条件(EMA 后总分) | 含义 |
|--------|-------------------|------|
| 🔴 Red | score ≥ 70 (normal) / ≥ 80 (panic) | 高危,多维共振强烈 |
| 🟡 Yellow | 50 ≤ score < red | 中等风险,需关注 |
| ⚪ Gray | 30 ≤ score < 50 | 低风险 |
| 🟢 Green | score < 30 | 安全 |

### 5.4 权重配置

| 标的类型 | Options | Short | Divergence | Insider |
|---------|---------|-------|------------|---------|
| Stock | 0.30 | 0.35 | 0.20 | 0.15 |
| ETF | 0.35 | 0.45 | 0.20 | — |

V1.5.9: 当某模块 signal=HIGH 时,权重提升至 0.40,剩余按比例重分配(总和恒=1.0)。
V1.6.0: ML 动态权重(LinearRegression R²)自动优化,clamp [0.10, 0.50]。

---

## 6. 数据管道 (ETL Pipeline)

### 6.1 执行流程

ETL 流水线由 `etl/pipeline.py` 中的 `run_daily_pipeline()` 统一编排,支持三种调用方式:

1. **Airflow DAG**: `dags/hunter_radar_eod.py` 每日 UTC 22:00(美东 18:00)触发
2. **CLI**: `python -m etl.pipeline 2024-02-01`
3. **Docker etl-cron**: 容器化定时任务

### 6.2 执行顺序

```
1. pull + load_daily_price      ← V1.6.0 多源降级(DataProviderManager)
       + validation             ← V1.6.0 日 K 校验(±50% 涨跌幅)
2. pull + load_short_volume     ← FINRA 全监管做空
3. pull + load_ats_short        ← ATS 暗池(主源 → fallback 爬虫)
4. pull + load_options_chain    ← Yahoo 期权链 + 校验
   └── compute_option_anomaly   ← 末日 Put 异常合约
   └── compute_pcr_gamma        ← V1.5.9 PCR + Gamma + OTM
5. pull + load_form4            ← SEC Form 4 内部人交易
   └── load_buyback             ← 回购公告
6. compute_etf_proxy            ← ETF 折溢价代理
7. compute_short_ratio          ← 做空比例 + Z-Score
8. compute_divergence           ← 量价背离(rising/confirmed)
9. compute_regime               ← 市场门控(VIX/SPX MA20)
10. compute_threat_score        ← 四维加权 + EMA 平滑 + 信号灯
11. REFRESH mv_screener_top100  ← V1.6.0 物化视图刷新
```

### 6.3 Airflow DAG 依赖图

```
pull_finra_short  ─┐
pull_finra_ats    ─┼─→ load_short_volume   ─┐
pull_yahoo_eod    ─┼─→ load_daily_price    ─┤
pull_yahoo_options─┼─→ load_options_chain  ─┼─→ compute_option_anomaly ─┐
pull_sec_form4    ─┼─→ load_form4          ─┤                          │
pull_sec_buyback  ─┘   compute_etf_proxy    ─┤                          │
                                             ├──────────────────────────┘
                                             ↓
                                    compute_threat_score
                                             ↓
                                       run_screener
```

### 6.4 V1.6.0 多源冗余框架

```
MarketDataProvider (ABC 抽象接口)
├── YFinanceProvider      ← 主源(yfinance)
├── AlphaVantageProvider  ← 备份源(Alpha Vantage API)
└── DataProviderManager   ← 统一入口,自动降级
```

降级策略: 主源异常 → 备份源 → 最近缓存,由 `DataProviderManager` 统一管理。

### 6.5 V1.6.0 重试策略

- **attempts**: 3 次
- **wait**: 指数退避 `min=5s, max=60s, multiplier=2`
- **可重试异常**: `httpx.HTTPError` / `TimeoutException` / `ConnectionError` / `OSError`
- **入口**: `etl_retry` 装饰器 / `etl_retry_async()` 函数式 / `run_stage_with_retry()` Pipeline 集成

### 6.6 V1.6.0 数据校验

四类校验,标记异常不丢弃:

| 校验 | 规则 | 严重级别 |
|------|------|----------|
| `validate_daily_price` | 日涨跌幅 > ±50% | Critical → mark_failed |
| `validate_short_volume` | 单日做空量 > 历史 99 分位 × 3 | Warning |
| `validate_form4` | 单笔金额 > 过去 1 年最大 × 5 | Warning |
| `validate_options_chain` | PCR > 10 或 < 0.1 | Warning |

---

## 7. 核心功能模块

### 7.1 期权异常检测 (Options Anomaly)

**模块目标**: 识别末日 Put 异常合约(DTE ≤ 7)与期权市场异常信号。

- **末日 Put 检测**: OI 激增 + Volume/OI 比异常 + Top 10 Notional
- **V1.5.9 PCR 分析**: Put/Call Ratio + Z-Score 极值检测(2σ)
- **Gamma 聚集**: 同一行权价 Gamma 暴露集中,可能形成磁吸效应
- **OTM 刺客**: 虚值期权异常大单,可能是知情交易
- **动态基线**: ETF 3× / Stock 5× 的成交量阈值倍数

### 7.2 做空水位分析 (Short Iceberg)

**模块目标**: 揭示隐藏的做空压力。

- **做空比例**: short_volume / total_volume
- **Z-Score 标准化**: 60 日滚动窗口 Z-Score(BD-031)
- **ATS 暗池追踪**: 暗池做空占比,V1.5.9 增加 fallback 爬虫
- **VWMA 去噪(V1.6.0)**: 成交量加权移动平均平滑做空比例,与融资余额互证

### 7.3 量价背离 (Divergence)

**模块目标**: 检测价格走势与做空趋势的背离。

- **10 日斜率**: 价格斜率 + 做空斜率
- **120 日分位数**: 斜率的历史分位数排名
- **状态机**: `none` → `rising`(上升中) → `confirmed`(确认)

### 7.4 内部人行为 (Insider)

**模块目标**: 追踪 SEC Form 4 披露的内部人交易。

- **交易分类**: buy / sell / grant / exercise
- **角色分类**: CEO / CFO / Director / 10%_holder
- **回购检测**: 8-K Item 8.01 回购公告分析

### 7.5 Threat Score 共振评分

**模块目标**: 综合四维信号输出 0-100 威胁评分。

核心流程:
1. 各模块子评分 → Z-Score/分位数 → 0-100 映射(S 形 tanh)
2. 加权求和 → 原始分 `total_raw`
3. EMA 平滑(半衰期 2 日) → 最终分 `total`
4. 信号灯判定(red/yellow/gray/green)
5. 市场门控:panic 期阈值上调至 80

### 7.6 市场门控 (Regime)

**模块目标**: 根据 VIX / SPX 判断市场状态。

- **Normal**: VIX ≤ 30 且 SPX ≥ MA20 → 红灯阈值 70
- **Panic**: VIX > 30 或 SPX < MA20 → 红灯阈值 80
- **配置可调**: `RegimeConfig` dataclass,支持回测时一行切换

### 7.7 信号归因 (Attribution, V1.6.0)

**模块目标**: 解释"为什么是红灯"。

- 计算各模块 `weight × score` 贡献
- 识别主驱动模块(贡献最大)
- 输出瀑布图数据(前端可视化)

### 7.8 ML 动态权重 (V1.6.0)

**模块目标**: 基于历史数据自动优化权重。

- 计算过去 90 天各模块对实现波动率的预测贡献度(R²)
- R² 归一化为权重,clamp [0.10, 0.50],总和 = 1.0
- 冷启动兼容:历史 < 90 天返回默认权重

### 7.9 RAG 知识库 (V1.6.0)

**模块目标**: 为 LLM 分析提供历史上下文。

- 从 form4_event / buyback_event / edgar 表提取历史公告
- sentence-transformers 生成 embedding → pgvector 存储
- Top-K 检索最相关文档 → 注入 LLM prompt context
- 降级兼容:无 embedding 时走文本匹配

### 7.10 终极警报 (Ultimate Alert)

**触发条件**:
- Threat Score ≥ 红灯阈值(EMA 后,严禁用原始分)
- 连续 ≥ 2 个交易日(OQ-02 决策)
- 去抖通过(防重复触发)

---

## 8. API 接口文档

> 基础路径: `/api/v1` · 响应格式: JSON (ORJSONResponse)
> 交互文档: 启动后访问 `http://localhost:8000/docs`(Swagger UI)或 `/redoc`

### 8.1 健康检查

| Method | Path | Tag | 说明 |
|--------|------|-----|------|
| GET | `/health` | health | 应用健康检查(DB + Redis) |

### 8.2 标的分析

| Method | Path | Tag | 说明 |
|--------|------|-----|------|
| GET | `/api/v1/symbols/lookup?q=` | symbols | 标的搜索 |
| GET | `/api/v1/symbols/{ticker}/threat` | symbols | Threat Score(含 EMA/权重/信号灯) |
| GET | `/api/v1/symbols/{ticker}/threat-history?days=90` | symbols | 90 日 Threat Score 轨迹 |
| GET | `/api/v1/symbols/{ticker}/ultimate-alert` | symbols | 终极警报状态 |
| GET | `/api/v1/symbols/{ticker}/options-anomaly?days=1` | symbols | 末日 Put 异常合约 |
| GET | `/api/v1/symbols/{ticker}/options-anomaly-v2` | symbols | Options V2(PCR/Gamma/OTM) |
| GET | `/api/v1/symbols/{ticker}/short-iceberg?days=20` | symbols | 做空水位图 |
| GET | `/api/v1/symbols/{ticker}/short-iceberg-v2?days=20` | symbols | 做空 V2(含 ATS fallback) |
| GET | `/api/v1/symbols/{ticker}/divergence?days=30` | symbols | 量价背离 |
| GET | `/api/v1/symbols/{ticker}/attribution` | attribution | 信号归因(V1.6.0) |

### 8.3 市场门控

| Method | Path | Tag | 说明 |
|--------|------|-----|------|
| GET | `/api/v1/regime` | regime | 市场状态(normal/panic + VIX/SPX) |
| GET | `/api/v1/regime/timeline` | regime-timeline | 市场切换时间轴(V1.6.0) |

### 8.4 Screener 榜单

| Method | Path | Tag | 说明 |
|--------|------|-----|------|
| GET | `/api/v1/screener?top=20&symbol_type=stock` | screener | Top N 猎物榜单 |

### 8.5 自选篮子

| Method | Path | Tag | 说明 |
|--------|------|-----|------|
| GET | `/api/v1/baskets` | basket | 篮子列表 |
| POST | `/api/v1/baskets` | basket | 创建篮子 |
| GET | `/api/v1/baskets/{id}` | basket | 篮子详情 |
| PUT | `/api/v1/baskets/{id}` | basket | 更新篮子 |
| DELETE | `/api/v1/baskets/{id}` | basket | 删除篮子 |
| GET | `/api/v1/baskets/{id}/members` | basket | 成员列表 |
| POST | `/api/v1/baskets/{id}/members` | basket | 添加成员 |
| DELETE | `/api/v1/baskets/{id}/members/{ticker}` | basket | 移除成员 |
| GET | `/api/v1/baskets/{id}/distribution?days=30` | basket | 分数分布(分位数) |

### 8.6 预警

| Method | Path | Tag | 说明 |
|--------|------|-----|------|
| GET/POST | `/api/v1/alerts` | alerts | 预警规则列表/创建 |
| GET/PUT/DELETE | `/api/v1/alerts/{id}` | alerts | 规则详情/更新/删除 |

### 8.7 数据状态

| Method | Path | Tag | 说明 |
|--------|------|-----|------|
| GET | `/api/v1/data-status` | data-status | 全局数据状态(ready/warming/stale/error) |

### 8.8 用户与订阅

| Method | Path | Tag | 说明 |
|--------|------|-----|------|
| GET | `/api/v1/quota` | auth | 当前用户配额(Free: 3 次/日, Pro: 无限) |

### 8.9 运营端点

| Method | Path | Tag | 说明 |
|--------|------|-----|------|
| GET | `/api/v1/feature-flags` | feature-flags | 灰度发布 flag 状态 |
| GET | `/api/v1/events/eight-k` | events | 8-K Item 8.01 重大事件流 |
| POST | `/api/v1/push/subscribe` | push | Web Push 订阅 |
| GET | `/api/v1/logs/stream` | log-stream | SSE 实时日志流 |

### 8.10 LLM 分析

| Method | Path | Tag | 说明 |
|--------|------|-----|------|
| POST | `/api/v1/llm/analyze` | llm | LLM 分析(含 RAG context 注入) |

### 8.11 EDGAR / ETF / Analytics

| Method | Path | Tag | 说明 |
|--------|------|-----|------|
| GET | `/api/v1/edgar/search?q=` | edgar | EDGAR 全文搜索 |
| GET | `/api/v1/etf/flows` | etf | ETF 申赎代理 |
| POST | `/api/v1/analytics/events` | analytics | 前端埋点上报 |

### 8.12 Admin

| Method | Path | Tag | 说明 |
|--------|------|-----|------|
| POST | `/api/v1/admin/etl/run` | admin | 手动触发 ETL |
| POST | `/api/v1/admin/backtest/run` | admin | 触发回测 |
| GET | `/api/v1/admin/backtest/result` | admin | 回测结果 |
| POST | `/api/v1/admin/webhook/replay` | admin | Webhook 重放 |

---

## 9. 前端开发

### 9.1 技术选型

- **React 18** + **TypeScript** + **Vite 5** 构建现代化 SPA
- **TanStack Router** 类型安全路由,**TanStack React Query** 数据层
- **Tailwind CSS 3** 暗色主题(slate 色系)
- **ECharts** + **lightweight-charts** 金融图表
- **i18next** 国际化(默认 zh-CN)
- **PWA** 离线支持(workbox + vite-plugin-pwa)

### 9.2 页面路由

| 路由 | 文件 | 说明 |
|------|------|------|
| `/` | `routes/index.tsx` | 首页:搜索 + Top 10 预览 |
| `/symbol/$ticker` | `routes/symbol.$ticker.tsx` | 标的详情:Threat Score + 模块信号灯 + 历史图 + Options V2 + LLM |
| `/screener` | `routes/screener.tsx` | 每日猎物榜单(Top 50) |
| `/basket` | `routes/basket.tsx` | 自选篮子管理 |
| `/alerts` | `routes/alerts.tsx` | 预警规则管理 |
| `/subscribe` | `routes/subscribe.tsx` | 订阅升级(Free → Pro) |

### 9.3 核心组件

#### 通用组件 (`components/common/`)

| 组件 | 说明 |
|------|------|
| `DataStatusBanner` | 全局数据状态横幅(ready/warming/stale/error) |
| `Disclaimer` | 合规免责声明(非投资建议) |
| `GrayReleaseBanner` | 灰度发布功能提示 |
| `LlmPanel` | LLM 分析侧边面板(RAG 增强) |
| `LogPanel` | SSE 实时日志面板 |
| `ProBadge` | Pro 用户标识 |
| `PWAInstallBanner` | PWA 安装提示 |
| `QuotaBanner` | 配额使用提示(Free: 3 次/日) |
| `UpgradePrompt` | 升级 Pro 提示弹窗 |

#### 雷达组件 (`components/radar/`)

| 组件 | 说明 |
|------|------|
| `ThreatScoreGauge` | Threat Score 仪表盘(0-100 环形图) |
| `ModuleSignalLight` | 模块信号灯(4 维子评分可视化) |
| `SignalLifecycleBadge` | 信号生命周期徽章(red/yellow/gray/green) |
| `ThreatHistoryChart` | 90 日 Threat Score 轨迹折线图 |
| `UltimateAlertOverlay` | 终极警报全屏覆盖(仅新警报弹出) |
| `RegimeBanner` | 市场状态横幅(normal/panic) |

### 9.4 自定义 Hooks (`features/`)

| Hook | 说明 |
|------|------|
| `useApiQuota` | API 配额查询 |
| `useDataStatus` | 数据状态轮询 |
| `useFeatureFlag` | 灰度 flag 查询 |
| `usePrefersReducedMotion` | 无障碍动画偏好检测 |
| `usePWAInstall` | PWA 安装流程 |
| `useSignalLifecycle` | 信号生命周期(连续天数 + EMA) |
| `useThreatHistory` | 90 日历史轨迹 |
| `useUltimateAlert` | 终极警报状态 |

### 9.5 API 客户端

`lib/api.ts` 封装所有后端调用,基础路径 `/api/v1`(Vite 代理到 `:8000`):

- 统一错误处理(`ApiError` 类)
- credentials: include(跨域 Cookie)
- 类型安全(泛型 + DTO 类型)
- openapi-typescript 自动生成类型(`pnpm run openapi:gen`)

---

## 10. CI/CD 与部署

### 10.1 GitHub Actions CI (9 Jobs)

| Job | 说明 |
|-----|------|
| `backend` | pytest + m7t1 回归 + m7t6 Stripe + m7t7 OpenAPI |
| `openapi-drift` | OpenAPI freeze 检测 |
| `frontend` | pnpm build + Lighthouse + PWA 资产验证 |
| `secrets-check` | VAPID + Sentry 密钥验证 |
| `webhook` | Stripe Webhook 集成测试 |
| `docs` | 文档完整性校验(M5/M6/BD-086/BD-087) |
| `freeze_check` | V1.5.7 OpenAPI freeze 自动化校验 |
| `self_test_harness` | 静态分析 harness |
| `m8t1_full_regression` | 73 脚本 / 1602 测点全量回归 |

### 10.2 Docker 部署

```bash
# 一键启动所有服务
cd infra && docker compose up -d

# 服务清单(7 个):
# - postgres:5432        (PostgreSQL 16)
# - redis:6379           (Redis 7)
# - airflow-webserver:8080 (Airflow UI)
# - airflow-scheduler    (Airflow 调度器)
# - backend:8000         (FastAPI 后端)
# - etl-cron             (ETL 定时任务)
```

### 10.3 Docker 控制脚本

```bash
docker/control.sh start    # 启动所有服务
docker/control.sh stop     # 停止所有服务
docker/control.sh restart  # 重启
docker/control.sh logs     # 查看日志
docker/control.sh migrate  # 运行数据库迁移
docker/control.sh seed     # 导入种子数据
docker/control.sh status   # 查看服务状态
```

### 10.4 Backend Dockerfile

多阶段构建:
- **base**: python:3.14-slim
- **builder**: pip install 依赖
- **runtime**: 非 root 用户(hunter) + HEALTHCHECK `/health`

---

## 11. 环境变量与配置

### 11.1 核心配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ENV` | development | 环境(development/staging/production) |
| `DEBUG` | true | 调试模式 |
| `LOG_LEVEL` | INFO | 日志级别 |
| `DATABASE_URL` | postgresql+asyncpg://hunter:hunter@localhost:5432/hunter_radar | 异步 DB DSN |
| `DATABASE_URL_SYNC` | postgresql+psycopg2://... | 同步 DB DSN(ETL/Alembic) |
| `REDIS_URL` | redis://localhost:6379/0 | Redis URL |
| `SECRET_KEY` | dev-only-change-me-in-prod | JWT 密钥 |
| `CORS_ORIGINS` | localhost:5173,localhost:3000 | CORS 允许域 |

### 11.2 数据源配置

| 变量 | 说明 |
|------|------|
| `FINRA_SHORT_URL` | FINRA 做空数据 CSV URL |
| `SEC_EDGAR_BASE` | SEC EDGAR 基础 URL |
| `SEC_USER_AGENT` | SEC 请求 UA(合规要求) |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage API Key(空=不启用备份源) |

### 11.3 Threat Score 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `THREAT_RED_THRESHOLD` | 70 | 红灯阈值(normal) |
| `THREAT_RED_THRESHOLD_PANIC` | 80 | 红灯阈值(panic) |
| `EMA_HALFLIFE_DAYS` | 2 | EMA 半衰期(交易日) |

### 11.4 付费配置

| 变量 | 说明 |
|------|------|
| `STRIPE_SECRET_KEY` | Stripe 密钥 |
| `STRIPE_WEBHOOK_SECRET` | Stripe Webhook 签名 |
| `STRIPE_PRICE_PRO_MONTHLY` | Pro 月付价格 ID |
| `STRIPE_PRICE_PRO_YEARLY` | Pro 年付价格 ID |
| `FREE_TIER_DAILY_QUOTA` | 免费用户每日配额(3) |
| `PRO_TIER_DAILY_QUOTA` | Pro 用户每日配额(9999) |

### 11.5 V1.6.0 新增

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ALPHA_VANTAGE_API_KEY` | "" | 备份数据源 API Key |
| `DATA_PROVIDER_FALLBACK_ENABLED` | true | 是否启用备份源降级 |

---

## 12. 开发与测试

### 12.1 本地开发

```bash
# 后端
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
pnpm install
pnpm dev      # http://localhost:5173
```

### 12.2 测试体系

| 类型 | 工具 | 说明 |
|------|------|------|
| 单元测试 | pytest + pytest-asyncio | `cd backend && pytest` |
| 自测脚本 | 73 脚本 / 1,602 测点 | `python -m scripts.m8t1_test_regression` |
| 前端测试 | vitest | `cd frontend && pnpm test` |
| E2E 测试 | Playwright | `.github/workflows/playwright-e2e.yml` |
| 性能审计 | Lighthouse CI | `.github/workflows/lighthouse-perf.yml` |
| WCAG 审计 | axe-core | `.github/workflows/wcag-audit.yml` |

### 12.3 自测脚本覆盖(V1.6.0: 73 脚本 / 1,602 测点)

| 脚本组 | 数量 | 测点 | 覆盖范围 |
|--------|------|------|----------|
| M1-M7 | 基础 | ~1000 | API/ETL/前端/订阅/OpenAPI/Admin |
| M8 | 聚合 | ~200 | freeze_check / self_test_harness |
| M9-M15 | 接力期 | ~277 | EDGAR/ETF/Analytics/灰度/V1.5.7-V1.5.9 |
| M19 (V1.6.0) | 6 脚本 | 150 | ML权重/VWMA/物化视图/归因/RAG/Docker/Handoff |

### 12.4 ETL CLI 运行

```bash
# 指定日期运行
python -m etl.pipeline 2026-06-15

# 跳过 Yahoo / SEC
python -m etl.pipeline 2026-06-15 --skip-yahoo --skip-sec
```

### 12.5 数据库初始化

```bash
# 创建 schema
psql -U hunter -d hunter_radar -f backend/sql/00_init.sql
psql -U hunter -d hunter_radar -f backend/sql/01_v1.5.9_options_ats.sql
psql -U hunter -d hunter_radar -f backend/sql/02_v1.6.0_materialized_views.sql
psql -U hunter -d hunter_radar -f backend/sql/03_v1.6.0_rag.sql

# 导入种子数据(标普 500 + 主流 ETF)
python -c "from etl.symbol_seed import DEFAULT_SEEDS; print(len(DEFAULT_SEEDS), 'seeds')"
```

---

> **免责声明**: Hunter Radar 仅基于公开数据的统计分析,不构成任何投资建议。所有数据来源于 FINRA、SEC EDGAR、Yahoo Finance 等公开渠道。投资有风险,决策需谨慎。
