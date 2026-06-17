># FE-010 Changelog — V1.5.1 (M9 接力期)

> **同步对象**:前端团队 / openapi-typescript 自动生成
> **Freeze 时点**:2026-06-15(M9 接力期)
> **freeze 文件**:`docs/openapi-frozen-v1.5.1.{json,md}`
> **增量来源**:v1.5 (48 endpoints) → v1.5.1 (56 endpoints)
> **新增 8 端点**:EDGAR 2(m9t4) + ETF 3(m9t5) + Analytics 3(m9t6)
> **同步 freeze**:v1.5(48 endpoints)全保留,无破坏

---

## 一、新增 8 端点(三个新 tag)

### 1.1 EDGAR tag — 2 端点(m9t4)

#### 1.1.1 GET /api/v1/edgar/search

- **角色**:EDGAR full-text search(V1.5.1 sandbox_stub)
- **请求 query**:
  - `query` (str, 可空):关键词(沙箱 stub 不解析)
  - `tickers` (str, 可空):逗号分隔 ticker,空=默认 11 ticker
  - `from_date` (str, 可空):filed_at 下界 YYYY-MM-DD
  - `to_date` (str, 可空):filed_at 上界 YYYY-MM-DD
  - `category` (Literal, 可空):share-repurchase / material-agreement / press-release / other
  - `limit` (int, 默认 20):最多 filing 数(1-50)
- **响应 200**:
  ```json
  {
    "summary": { "fetched_at": "...", "filings_count": N, "tickers_count": N, "sandbox": true },
    "filings": [
      { "ticker": "AAPL", "form_type": "8-K", "filed_at": "2026-06-15T...",
        "category": "press-release", "title": "...", "url": "..." }
    ],
    "sandbox": true,
    "review_mode": "sandbox_stub",
    "query_meta": { "query": "...", "tickers": [...], "from_date": "...", "to_date": "...", "category": "...", "limit": 20 },
    "disclaimer": "Sandbox stub:基于确定性合成,非真实 EDGAR 数据。V1.5.1 起仅供 dev/sandbox,生产前需替换为真实 SEC EDGAR API。"
  }
  ```
- **前端**:EDGAR 全文搜索页(Week 3 计划)
- **沙箱**:stub 模式(fetch_fulltext_sandbox)

#### 1.1.2 GET /api/v1/edgar/categories

- **角色**:EDGAR 8-K Item 8.01 4 类 category 关键词表
- **请求**:无 query
- **响应 200**:
  ```json
  {
    "categories": ["share-repurchase", "material-agreement", "press-release", "other"],
    "keywords": {
      "share-repurchase": ["repurchase", "buyback", "share repurchase"],
      "material-agreement": ["agreement", "contract", "material agreement"],
      "press-release": ["press release", "announcement"],
      "other": []
    },
    "review_mode": "sandbox_stub"
  }
  ```
- **前端**:EDGAR 搜索页 category 下拉框数据源

### 1.2 ETF tag — 3 端点(m9t5, BD-088)

#### 1.2.1 GET /api/v1/etf/basket

- **角色**:拉 ETF 申赎篮子(NAV / iNAV / 成分股清单)
- **请求 query**:
  - `etf` (str, 必填, 1-10):ETF ticker
- **响应 200**:
  ```json
  {
    "basket": {
      "etf_ticker": "SPY", "nav": 450.0, "inav": 450.05,
      "shares_per_unit": 50000, "cash_component": 1000.0,
      "components": [ { "ticker": "AAPL", "shares": 100, "weight": 0.07 } ]
    },
    "sandbox": true,
    "review_mode": "sandbox_stub_v15_prep",
    "disclaimer": "Sandbox stub:基于 mock 篮子,非真实 NAV/iNAV/成分股数据。V1.5.1 起仅供 dev/sandbox,生产前需替换为 Bloomberg/ETF.com 实时数据。"
  }
  ```
- **前端**:ETF 详情页(Week 3 计划)

#### 1.2.2 POST /api/v1/etf/orders

- **角色**:提交 ETF 申赎订单(沙箱 stub,不发真实 AP 请求)
- **请求 body**:
  ```json
  {
    "etf": "SPY",                     // str, 1-10
    "order_type": "creation",          // str, creation|redemption
    "settlement_mode": "cash",         // str, cash|in_kind
    "units": 100,                      // int, 1-10000
    "ap": "BNY Mellon"                 // str, 可空, ≤64
  }
  ```
- **响应 200**:
  ```json
  {
    "order": {
      "order_id": "uuid-...",
      "etf_ticker": "SPY",
      "order_type": "creation",
      "settlement_mode": "cash",
      "units": 100,
      "status": "submitted",
      "submitted_at": "2026-06-15T..."
    },
    "sandbox": true,
    "review_mode": "sandbox_stub_v15_prep",
    "disclaimer": "Sandbox stub:仅构造订单对象,未发真实 AP 请求。V1.5.1 起仅供 dev/sandbox,生产前需接入 BNY Mellon / JPMorgan AP API。"
  }
  ```
- **错误码**:
  - `400`:参数错(etf 长度越界 / units 越界)
  - `422`:order_type / settlement_mode 字段值不合法(Pydantic field_validator)
- **前端**:ETF 申赎下单表单(Week 3 计划)

#### 1.2.3 GET /api/v1/etf/premium-discount

- **角色**:计算 ETF 市价相对 NAV 的溢价/折价 + 套利窗口
- **请求 query**:
  - `etf` (str, 必填, 1-10):ETF ticker
  - `price` (float, 必填, >0, ≤10000):市场实时价
- **响应 200**:
  ```json
  {
    "etf": "SPY",
    "market_price": 450.0,
    "nav": 450.0,
    "premium": 0.0,
    "premium_pct": 0.0,
    "arb_opportunity": false,
    "sandbox": true,
    "review_mode": "sandbox_stub_v15_prep"
  }
  ```
- **前端**:ETF 套利机会监控(Week 4 计划)

### 1.3 Analytics tag — 3 端点(m9t6)

#### 1.3.1 GET /api/v1/analytics/events

- **角色**:读最近 N 条埋点事件(沙箱 in-memory ring buffer)
- **请求 query**:
  - `event_name` (str, 可空, ≤64):10 事件名之一
  - `from_ts` (str, 可空):时间下界 ISO 8601 UTC
  - `to_ts` (str, 可空):时间上界 ISO 8601 UTC
  - `limit` (int, 默认 50):最多返多少条(1-100)
- **响应 200**:
  ```json
  {
    "events": [
      { "event_name": "user_signup", "timestamp": "2026-06-15T...",
        "user_id_hash": "sha256:...", "props": {} }
    ],
    "count": N,
    "sandbox": true,
    "review_mode": "sandbox_stub_v15_prep",
    "query_meta": { "event_name": "...", "from_ts": "...", "to_ts": "...", "limit": 50 },
    "disclaimer": "Sandbox stub:基于 in-memory ring buffer(最近 1000 条),重启后丢失。V1.5.1 起仅供 dev/sandbox,生产前需接 postHog / Plausible / ClickHouse。"
  }
  ```
- **错误码**:`400`(event_name 不在 10 类中 / ISO 8601 格式错)
- **前端**:Admin Analytics 仪表板(Week 3 计划)

#### 1.3.2 GET /api/v1/analytics/funnel

- **角色**:订阅漏斗摘要
- **请求**:无 query
- **响应 200**:
  ```json
  {
    "unique_users_signup": 100,
    "unique_users_subscribe_start": 30,
    "unique_users_subscribe_success": 12,
    "signup_to_subscribe_start": 0.30,
    "subscribe_start_to_success": 0.40,
    "sandbox": true,
    "review_mode": "sandbox_stub_v15_prep",
    "sample_size": 500
  }
  ```
- **前端**:Admin Analytics 订阅漏斗图

#### 1.3.3 GET /api/v1/analytics/event-names

- **角色**:10 事件类型 + 用途说明
- **请求**:无 query
- **响应 200**:
  ```json
  {
    "event_names": [
      "user_signup", "user_login", "subscribe_start", "subscribe_success", "subscribe_cancel",
      "screener_view", "basket_create", "alert_rule_create", "push_opt_in", "feature_flag_view"
    ],
    "descriptions": {
      "user_signup": "新用户注册",
      "user_login": "用户登录",
      "subscribe_start": "订阅流程开始(进入 /subscribe 页)",
      "subscribe_success": "订阅成功(Stripe webhook confirmed)",
      "subscribe_cancel": "订阅取消",
      "screener_view": "Screener 页查询触发",
      "basket_create": "创建新 Basket",
      "alert_rule_create": "创建告警规则",
      "push_opt_in": "Web Push 订阅成功",
      "feature_flag_view": "灰度发布 flag 触发曝光"
    },
    "sandbox": true,
    "review_mode": "sandbox_stub_v15_prep"
  }
  ```
- **前端**:Admin Analytics 事件类型选择器

---

## 二、行为变更

**无** — V1.5.1 是纯增量,所有既有 v1.5 端点路径 / 方法 / 请求体 / 响应体 schema 不变。

---

## 三、端点总数对比

| 维度 | v1.4.1 | v1.5 | v1.5.1 |
|---|---|---|---|
| paths | 36 | 40 | **48** |
| endpoints | 44 | 48 | **56** |
| tags | 12 | 13 | **16** |
| routers | 12 | 13 | **16** |
| 新增 tag | — | admin | **edgar / etf / analytics** |

---

## 四、自动生成命令

```bash
cd backend
npx openapi-typescript docs/openapi-frozen-v1.5.1.json \
  --output src/types/api-v1.5.1.ts
# 或
npx openapi-typescript-codegen --input docs/openapi-frozen-v1.5.1.json \
  --output src/types/api-v1.5.1
```

---

## 五、向后兼容性

- ✅ **所有 v1.5 端点保留**:路径 / 方法 / 请求体 / 响应体 schema 不变
- ✅ **新增 8 端点独立三个新 tag**:`edgar` / `etf` / `analytics`,不影响既有 v1.5 TypeScript 类型
- ⚠️ **`api-v1.5.ts` → `api-v1.5.1.ts`** 重生成:类型定义合并而非覆盖

---

## 六、前端集成 checklist

### 6.1 EDGAR(m9t4)

- [ ] `useEdgarSearch` hook(Week 3 计划)
- [ ] EDGAR 全文搜索页:`/edgar?q=...&tickers=AAPL,MSFT&from_date=...&to_date=...&category=...`
- [ ] Category 下拉框数据源:GET `/api/v1/edgar/categories`

### 6.2 ETF(m9t5)

- [ ] `useEtfBasket` hook
- [ ] `useEtfPremiumDiscount` hook
- [ ] ETF 详情页:`/etf/SPY` 展示 basket / premium-discount
- [ ] ETF 申赎下单表单:POST `/api/v1/etf/orders`(Week 3)

### 6.3 Analytics(m9t6)

- [ ] `useAnalyticsEvents` hook
- [ ] `useAnalyticsFunnel` hook
- [ ] Admin Analytics 仪表板:
  - 订阅漏斗图(GET `/funnel`)
  - 事件流(GET `/events`)
  - 事件类型过滤(GET `/event-names`)
- [ ] 时间范围选择器支持 ISO 8601 UTC

---

## 七、QA checklist

- [ ] 前端 `pnpm dev` 重启后,`src/types/api-v1.5.1.ts` 含 56 endpoints
- [ ] EDGAR search 在 sandbox 模式下响应含 `sandbox: true` + `review_mode: "sandbox_stub"`
- [ ] ETF orders POST 在 sandbox 模式下仅构造订单对象,未发真实 AP 请求
- [ ] Analytics events / funnel / event-names 三端点响应含 `sandbox: true` + `review_mode: "sandbox_stub_v15_prep"`
- [ ] 既有 v1.5 端点(48 个)在 `api-v1.5.1.ts` 中全部可见且无破坏
- [ ] 三个新 tag(`edgar` / `etf` / `analytics`)在 OpenAPI Schema 中可见
- [ ] FE-010 changelog v1.5.1 已 commit

---

> **下一步**:M9-t8(V1.5 final handoff 收尾文档)