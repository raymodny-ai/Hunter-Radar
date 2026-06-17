># Hunter Radar V1.5.2 — OpenAPI Freeze v1.5.2

> **🧊 Freeze 时点:2026-06-15(M10 接力期补 freeze,W2 末 v1.5.1 → v1.5.2 增量)**
> 配套:本仓库后端 `app/api/*.py` 共 **56 个端点**(V1.5.1 freeze 沿用,无新端点)
> 配套:`docs/openapi-frozen-v1.5.2.json`(机器可读,记录 V1.5.2 增量变更)
> 同步:本 freeze 是 FE-010(`openapi-typescript` 自动生成)与机构版复制方的前置依赖
> 解除 freeze 流程:见 §四 变更流程
> 上一 freeze 版:v1.5.1(2026-06-15 M9 接力期,56 端点)→ `docs/openapi-frozen-v1.5.1.{json,md}`

---

## 一、概述

### 1.1 范围

- **base URL**:`http://localhost:8000`(开发)/ `https://api.hunter-radar.example`(生产)
- **OpenAPI 3.0.3**(FastAPI 0.136.3 自动生成)
- **不包含**:Sentry / Redis / Postgres 内部接口
- **包含**:`/api/v1/*` 业务端点 + `/health` 运维端点 + `/` 根描述
- **M10 增量**:**0 新增端点,3 端点响应字段增强** + 4 admin 端点文档化

### 1.2 自动生成命令(生产环境)

```bash
cd backend
uv run fastapi dev app/main.py   # 起服务
curl http://localhost:8000/openapi.json > docs/openapi-frozen-v1.5.2.json
# 沙箱 fallback(无 PG / Redis / asyncpg / sentry_sdk / stripe):
py -u backend/scripts/m7t7_dump_openapi.py  # 沿用 V1.5 / V1.5.1 dump
```

> **沙箱 fallback**:
> 本仓库 `docs/openapi-frozen-v1.5.2.json` 由 V1.5.1 dump 脚本基础 + 手工记录 V1.5.2 增量变更。
> 生产环境务必用 `uv run` 覆盖一次。

### 1.3 OpenAPI freeze 硬约束(沿用 M3 / M4 / M5 / v1.5 / v1.5.1)

- **新增端点**:必须在 freeze 解除流程中登记,不得私下增路由
- **修改端点**(字段 / 路径 / 状态码 / 错误体):必须先 freeze 解除,改完再 freeze
- **删除端点**:必须先 freeze 解除,标 deprecated 90 天后才物理删除
- **数据缺失语义**:统一返 200 + 空数组 / 空对象,严禁 5xx 透传
- **沙箱 fallback 显式标注**(M9 加固,V1.5.2 沿用):所有 V1.5.2 端点必须含 `sandbox=true` + `review_mode` 字段
- **真实数据源 fetch_source 显式标注**(V1.5.2 新增):EDGAR/ETF/Analytics 端点必须含 `fetch_source` + `http_status` + `latency_ms` + `warning` 4 字段

---

## 二、M10 增量(v1.5.1 → v1.5.2)

### 2.1 端点响应字段增强(3 端点)

| # | Method | Path | 增强字段 | 关联 todo | freeze_mode |
|---|---|---|---|---|---|
| 1 | GET | `/api/v1/edgar/search` | + `fetch_source` / `http_status` / `latency_ms` / `warning` | m10t1 | sandbox → production_real 双轨 |
| 2 | GET | `/api/v1/etf/premium-discount` | + `inav_deviation` / `volume_5d_avg` / `volume_30d_avg` / `volume_spike_ratio` / `fetch_source` / `http_latency_ms` / `warning`(同时 `price` 参数改可选) | m10t2 | sandbox → production_real 双轨 |
| 3 | GET | `/api/v1/analytics/events` | + `fetch_source` / `http_status` / `latency_ms` / `warning` | m10t3 | sandbox → production_real 双轨 |

### 2.2 行为变更(端点不变)

| # | Method | Path | 变更内容 | 关联 todo |
|---|---|---|---|---|
| 1 | GET | `/api/v1/edgar/search` | 默认查询从 sandbox_stub 切换为 httpx → SEC API(`SEC_API_USER_AGENT` 必填),失败 fallback sandbox_stub | m10t1 |
| 2 | GET | `/api/v1/etf/premium-discount` | `price` 缺省时走 yfinance 真实代理数据(15 字段),提供时仍走 V1.5.1 行为 | m10t2 |
| 3 | GET | `/api/v1/analytics/events` | 默认查询从 in-memory ring buffer 切换为 postHog(优先)/ Plausible(次选)真实事件库,失败 fallback sandbox_stub_v15_prep | m10t3 |

### 2.3 文档化(无 schema 变化)

| # | Method | Path | 文档化 | 关联 todo |
|---|---|---|---|---|
| 1-4 | POST/GET | `/api/v1/admin/{etl,backtest,webhook}/*`(4 端点) | 公开评审 + 3 项 V1.5.3 待优化 | m10t4 |

### 2.4 已弃用 / 替换(无 API 端点变化)

| 项 | 状态 | 关联 todo |
|---|---|---|
| `m7t2_sign_goldset.py` | ⚠️ DEPRECATED(评审期 docstring 警告,V1.5.3 起物理删除) | m10t5 |
| `_mann_whitney_u` 简化版 | ⚠️ DEPRECATED 内部(优先走 scipy.stats.mannwhitneyu) | m10t6 |

---

## 三、fetch_source 字段统一规范(V1.5.2 新增)

为与 m10t1 / m10t2 / m10t3 真实数据源接入保持一致,所有 V1.5.2 端点响应必含 `fetch_source` 字段:

| fetch_source 值 | 含义 | 适用端点 |
|---|---|---|
| `sec_httpx` | EDGAR 真实 SEC API(httpx OK) | `/api/v1/edgar/search` |
| `yfinance` | ETF 真实 AP 代理数据源 | `/api/v1/etf/premium-discount` |
| `user_provided_price` | 用户提供 price(沿用 V1.5.1 行为) | `/api/v1/etf/premium-discount` |
| `posthog` | postHog 真实事件库 | `/api/v1/analytics/events` |
| `plausible` | Plausible 真实事件库 | `/api/v1/analytics/events` |
| `sandbox_stub` | 沙箱 stub fallback(无真实 API 可调) | edgar / etf / analytics |
| `sandbox_stub_v15_prep` | V1.5 prep 沙箱 stub(in-memory ring buffer) | analytics |
| `sandbox_skip_admin` | admin 鉴权沙箱 fallback | 4 admin 端点 |

**显式标注规则**(沿用 M9):
- 严禁 mock 200 伪装(数据缺失返 200+空 + warning,不静默)
- 沙箱 fallback 必含 `sandbox=true` 标记
- 真实 API 失败 → 标 `fetch_source="sandbox_stub"` + `warning` 字段说明

---

## 四、变更流程(沿用 V1.5 / V1.5.1)

1. **申请 freeze 解除**:在 M11+ 接力期开始前提交变更清单
2. **评审**:CR + Product 双签(走 `reviewer_cli` 真实签,弃用 m7t2 sandbox_stub)
3. **修改**:严格按清单实施,不得 scope creep
4. **新 freeze**:覆盖 `docs/openapi-frozen-v1.5.2.{json,md}`,标注 freeze 时点
5. **回滚**:若新 freeze 引入回归,回滚到 v1.5.2 + 重新走流程

---

## 五、freeze 校验

`m10t8_test_v152_finalize.py` 25 测点覆盖:
- V1.5.2-handoff.md 存在 + 8/8 todo 完整
- OpenAPI v1.5.2 freeze md + json 存在
- 3 端点响应字段增强清单
- fetch_source 8 值显式标注
- 7 项 V1.5.3 待优化项记录
- 评审依据文件引用 ≥5

---

**V1.5.2 freeze:🧊 ONLINE-READY**

freeze 评审:m10t8 接力期 / 状态:V1.5.2-ONLINE-READY / 日期:2026-06-15
