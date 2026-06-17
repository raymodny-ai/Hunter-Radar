># Hunter Radar V1.5.1 — OpenAPI Freeze v1.5.1

> **🧊 Freeze 时点:2026-06-15(M9 接力期补 freeze,W2 末 v1.5 → v1.5.1 增量)**
> 配套:本仓库后端 `app/api/*.py` 共 **56 个端点**(16 router + 2 health;v1.5 起 48 + 8 新增)
> 配套:`docs/openapi-frozen-v1.5.1.json`(机器可读,由 `scripts/m9t7_dump_openapi_v151.py` 静态扫)
> 同步:本 freeze 是 FE-010(`openapi-typescript` 自动生成)与机构版复制方的前置依赖
> 解除 freeze 流程:见 §四 变更流程
> 上一 freeze 版:v1.5(2026-06-16 M7 接力期,48 端点)→ `docs/openapi-frozen-v1.5.{json,md}`

---

## 一、概述

### 1.1 范围

- **base URL**:`http://localhost:8000`(开发)/ `https://api.hunter-radar.example`(生产)
- **OpenAPI 3.0.3**(FastAPI 0.136.3 自动生成)
- **不包含**:Sentry / Redis / Postgres 内部接口
- **包含**:`/api/v1/*` 业务端点 + `/health` 运维端点 + `/` 根描述
- **M9 增量**:8 个端点(EDGAR 2 + ETF 3 + Analytics 3)

### 1.2 自动生成命令(生产环境)

```bash
cd backend
uv run fastapi dev app/main.py   # 起服务
curl http://localhost:8000/openapi.json > docs/openapi-frozen-v1.5.1.json
# 沙箱 fallback(无 PG / Redis / asyncpg / sentry_sdk / stripe):
py -u backend/scripts/m9t7_dump_openapi_v151.py
```

> **沙箱 fallback**:
> 本仓库 `docs/openapi-frozen-v1.5.1.json` 由 `scripts/m9t7_dump_openapi_v151.py` 静态扫描
> `app/api/*.py` 的 `@router.{get,post,put,delete}` + DTO 字段产出,
> 等同于人读版 §二 / §三 的机器可读形态。生产环境务必用 `uv run` 覆盖一次。

### 1.3 OpenAPI freeze 硬约束(沿用 M3 / M4 / M5 / v1.5)

- **新增端点**:必须在 freeze 解除流程中登记,不得私下增路由
- **修改端点**(字段 / 路径 / 状态码 / 错误体):必须先 freeze 解除,改完再 freeze
- **删除端点**:必须先 freeze 解除,标 deprecated 90 天后才物理删除
- **数据缺失语义**:统一返 200 + 空数组 / 空对象,严禁 5xx 透传(Redis 沙箱降级到原函数)
- **沙箱 fallback 显式标注**(M9 加固):所有 V1.5.1 新增端点必须含 `sandbox=true` + `review_mode` 字段

---

## 二、M9 增量(v1.5 → v1.5.1)

### 2.1 新增 8 端点

| # | Method | Path | 角色 | 状态 | 关联 todo |
|---|---|---|---|---|---|
| 1 | GET | `/api/v1/edgar/search` | EDGAR full-text search(sandbox_stub) | m9t4 freeze | 4 类 category + tickers/date/category 过滤 |
| 2 | GET | `/api/v1/edgar/categories` | EDGAR 4 类 category 列表 | m9t4 freeze | 与 eight_k.py CATEGORY_KEYWORDS 同步 |
| 3 | GET | `/api/v1/etf/basket` | ETF 申赎篮子(NAV / iNAV / 成分股) | m9t5 freeze | BD-088 sandbox_stub_v15_prep |
| 4 | POST | `/api/v1/etf/orders` | 提交 ETF 申赎订单 | m9t5 freeze | Pydantic EtfOrderRequest + field_validator |
| 5 | GET | `/api/v1/etf/premium-discount` | ETF 溢价/折价 + 套利窗口 | m9t5 freeze | compute_premium_discount |
| 6 | GET | `/api/v1/analytics/events` | 读最近 N 条埋点事件 | m9t6 freeze | 10 事件名 + 时间范围过滤 |
| 7 | GET | `/api/v1/analytics/funnel` | 订阅漏斗摘要 | m9t6 freeze | signup→subscribe_start→success |
| 8 | GET | `/api/v1/analytics/event-names` | 10 事件类型 + 用途说明 | m9t6 freeze | V1.5 spec 沿用 |

### 2.2 沙箱 fallback 显式标注

| 端点 | review_mode | sandbox 标志 | disclaimer |
|---|---|---|---|
| `/api/v1/edgar/*` | `sandbox_stub` | `sandbox=true` | 基于 fetch_fulltext_sandbox 确定性合成,非真实 EDGAR 数据 |
| `/api/v1/etf/*` | `sandbox_stub_v15_prep` | `sandbox=true` | 基于 mock 篮子/订单,生产前需接 Bloomberg/BNY Mellon |
| `/api/v1/analytics/*` | `sandbox_stub_v15_prep` | `sandbox=true` | in-memory ring buffer(最近 1000 条),重启后丢失 |

> **严禁 mock 200 伪装**(M5 锁定):所有 V1.5.1 端点在响应中显式标注 `sandbox=true` + `review_mode`,
> 任何路径若 ETCD/Redis/httpx 不可达,走 sandbox fallback 而非抛 5xx。

### 2.3 行为变更(端点不变)

- 无(V1.5.1 是纯增量,不修改任何既有端点)

---

## 三、端点总数对比

| Freeze 版 | paths | endpoints | tags | router 数 | 增量来源 |
|---|---|---|---|---|---|
| v1.4(M0~M4) | 27 | 33 | 9 | 9 | 基础版 |
| v1.4.1(M5 接力期) | 36 | 44 | 12 | 12 | +push(m5t4) / +data-status(m5t6) / +auth-quota(m5t8) 6 端点 |
| v1.5(M7 接力期) | 40 | 48 | 13 | 13 | +admin 4 端点(m7t7)+ webhook 行为变更(m7t6)+ EDGAR ETL etl 层(m7t5 不暴露 API) |
| **v1.5.1(M9 接力期)** | **48** | **56** | **16** | **16** | +EDGAR 2(m9t4)+ ETF 3(m9t5)+ Analytics 3(m9t6) |

### 3.1 16 router 列表

| # | router | 前缀 | tags | 端点数 | 备注 |
|---|---|---|---|---|---|
| 1 | health | 无 | health | 2 | M0 |
| 2 | symbols | /api/v1 | symbols | 7 | M0~M3 |
| 3 | regime | /api/v1 | regime | 1 | M2 |
| 4 | screener | /api/v1 | screener | 1 | M3 |
| 5 | alerts | /api/v1 | alerts | 7 | M1~M4 |
| 6 | basket | /api/v1 | basket | 8 | M3 |
| 7 | push | /api/v1 | push | 4 | M5(m5t4) |
| 8 | data_status | /api/v1 | data-status | 1 | M5(m5t6) |
| 9 | quota | /api/v1 | auth | 1 | M5(m5t8) |
| 10 | subscriptions | /api/v1 | subscriptions | 6 | M6(m6t4 + m7t6) |
| 11 | feature_flags | /api/v1 | feature-flags | 2 | M6(m6t7) |
| 12 | eight_k | /api/v1 | events | 2 | M6(m6t8) |
| 13 | **admin** | **/api/v1** | **admin** | **4** | **M7(m7t7)** |
| 14 | **edgar** | **/api/v1/edgar** | **edgar** | **2** | **M9(m9t4)** |
| 15 | **etf** | **/api/v1/etf** | **etf** | **3** | **M9(m9t5)** |
| 16 | **analytics** | **/api/v1/analytics** | **analytics** | **3** | **M9(m9t6)** |
| **合计** | — | — | — | **56** | — |

---

## 四、变更流程(沿用 v1.5)

1. **申请**:`docs/freeze-bump-request.md` 写明:新增 / 修改 / 删除端点 + 业务理由 + review_mode(sandbox_stub / sandbox_stub_v15_prep / production)
2. **审批**:CR + Product 签字(参考 BD-086 双签)
3. **修改代码**:`app/api/*.py` 落地 + DTO 字段同步 + `main.py` 注册
4. **重 freeze**:跑 `scripts/m9t7_dump_openapi_v151.py` → `docs/openapi-frozen-v1.5.1.json` 覆盖
5. **同步前端**:FE-010 changelog v1.5.1 + `openapi-typescript` 重新生成
6. **通知**:在 `daily-standup.md` + 本 freeze md §二登记

---

## 五、风险与遗留

| ID | 风险 | 状态 | 缓解 |
|---|---|---|---|
| **R-31** | Stripe webhook 沙箱简化(无签名校验) | ✅ **v1.5 解除**(m7t6) | webhook 显式标注 signature_skipped + signature_mode=sandbox_skip |
| **R-34** | admin 端点暂免鉴权 | ✅ **v1.5.1 部分解除**(m9t1) | JWT role + ADMIN_API_KEY 备选 + IP 白名单 + sandbox fallback 显式 |
| **R-35** | admin 端点暴露内部 ETL trigger | ✅ **v1.5.1 部分解除**(m9t1) | IP 白名单 + sandbox fallback 显式(sandbox_skip_admin) |
| **R-36** | etl 层不暴露 API,前端无法直接拉 8-K 数据 | ✅ **v1.5.1 解除**(m9t4) | /api/v1/edgar/search + categories 公开端点(sandbox_stub) |
| **R-37**(新) | EDGAR 真实 SEC API 未接入 | 🟡 已知 | V1.5.2 评估 httpx → https://efts.sec.gov/LATEST/search-index |
| **R-38**(新) | ETF 真实 AP 通道未接入 | 🟡 已知 | V1.5.2 评估 BNY Mellon / JPMorgan AP API |
| **R-39**(新) | Analytics in-memory ring buffer 重启丢失 | 🟡 已知 | V1.5.2 评估 postHog / Plausible / ClickHouse |
| **R-40**(新) | ETF/EDGAR/Analytics 端点均 sandbox_stub,生产前未实装 | 🟡 已知 | V1.5.2 真实数据源接入 + review_mode 切换 |

---

## 六、本日记忆(M9-t7 关键决策)

1. **v1.5.1 freeze 落地**:56 endpoints / 48 paths / 16 tags(M9-t7)
2. **新增 8 端点**:`/api/v1/edgar/{search,categories}` + `/api/v1/etf/{basket,orders,premium-discount}` + `/api/v1/analytics/{events,funnel,event-names}`
3. **沙箱 fallback 显式标注统一**:所有 V1.5.1 新增端点响应含 `sandbox=true` + `review_mode=sandbox_stub|sandbox_stub_v15_prep`
4. **EDGAR fulltext 公开化**:R-36 解除(R-37 真实 API 留作 v1.5.2)
5. **R-34/35 admin 鉴权**:m9t1 已完成(JWT + ADMIN_API_KEY + IP 白名单)
6. **FE-010 同步**:前端 openapi-typescript 重生成 + v1.5.1 changelog 同步(m9t7 收尾)
7. **R-37/38/39/40 风险新增**:EDGAR/ETF/Analytics 真实数据源待 V1.5.2 评估

---

## 七、与 v1.5 差异详表

| 维度 | v1.5 | v1.5.1 | 增量 |
|---|---|---|---|
| paths | 40 | 48 | +8(EDGAR 2 + ETF 3 + Analytics 3) |
| endpoints | 48 | 56 | +8(同上) |
| tags | 13 | 16 | +3(edgar / etf / analytics) |
| routers | 13 | 16 | +3(edgar / etf / analytics) |
| Admin 端点 | 4 | 4 | 0(v1.5 已 freeze) |
| EDGAR 公开端点 | 0 | 2 | +2(m9t4) |
| ETF 公开端点 | 0 | 3 | +3(m9t5) |
| Analytics 公开端点 | 0 | 3 | +3(m9t6) |

---

> **下一步**:M9-t8(V1.5 final handoff 收尾文档)