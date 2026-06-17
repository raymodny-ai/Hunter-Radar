># FE-010 Changelog — V1.5 (M7 接力期)

> **同步对象**:前端团队 / openapi-typescript 自动生成
> **Freeze 时点**:2026-06-16(M7 接力期)
> **freeze 文件**:`docs/openapi-frozen-v1.5.{json,md}`
> **增量来源**:v1.4.1 (44 endpoints) → v1.5 (48 endpoints)

---

## 一、新增 4 端点(admin 标签)

### 1.1 POST /api/v1/admin/etl/run

- **角色**:触发 BD-085 真实数据集 ETL 重跑
- **请求**:无 body
- **响应 200**:
  ```json
  {
    "started_at": "2026-06-16T...",
    "completed_at": "2026-06-16T...",
    "ok": true,
    "sandbox": true,
    "stdout_tail": "...",
    "stderr_tail": "..."
  }
  ```
- **前端**:暂无 UI(运维内部触发)
- **沙箱**:stub 模式

### 1.2 POST /api/v1/admin/backtest/run

- **角色**:触发 v3.0-final backtest(Mann-Whitney U)
- **请求**:无 body
- **响应 200**:
  ```json
  {
    "started_at": "2026-06-16T...",
    "completed_at": "2026-06-16T...",
    "ok": true,
    "sandbox": true,
    "summary": {
      "weights_a": "v1.0",
      "weights_b": "candidate_a",
      "delta_hit_rate": -0.0645,
      "delta_f1": -0.0703,
      "mann_whitney_p_value": 0.3827,
      "significant_at_005": false
    }
  }
  ```
- **前端**:暂无 UI(运维内部触发)

### 1.3 GET /api/v1/admin/backtest/result

- **角色**:读最近 backtest 结果
- **请求**:无 query
- **响应 200**:
  ```json
  {
    "available": true,
    "path": "docs/BD-087-calibration-run-m7t4.json",
    "fetched_at": "2026-06-16T...",
    "summary": { ... 同 1.2 ... }
  }
  ```
- **前端**:暂无 UI(运维内部读)

### 1.4 POST /api/v1/admin/webhook/replay

- **角色**:重放 sandbox Stripe webhook
- **请求 body**:`{ "type": "...", "data": { "object": {...} } }`
- **响应 200**:
  ```json
  {
    "received_at": "2026-06-16T...",
    "replayed": true,
    "signature_mode": "sandbox_skip",
    "result": { "handled": true, "event_type": "...", ... }
  }
  ```
- **前端**:测试工具

---

## 二、行为变更:POST /api/v1/subscriptions/webhook

### 2.1 沙箱模式(STRIPE_WEBHOOK_SECRET 未设)

**新响应字段**:
- `signature_skipped: true`
- `signature_mode: "sandbox_skip"`
- `warning: "STRIPE_WEBHOOK_SECRET not set; sandbox mode"`

**示例**:
```json
{
  "received": true,
  "signature_skipped": true,
  "signature_mode": "sandbox_skip",
  "warning": "STRIPE_WEBHOOK_SECRET not set; sandbox mode",
  "handled": true,
  "event_type": "customer.subscription.updated",
  "user_id": "...",
  "new_status": "active"
}
```

### 2.2 真实模式(secret 已设)

- 用 `stripe.Webhook.construct_event(payload, sig, secret)` 校验签名
- 校验成功 → 200 + `signature_mode: "prod_verified"` + `handled: true`
- 签名错误 → 400 + `error: "invalid signature"` + `signature_mode: "prod_verified"`
- payload 非 JSON → 400 + `error: "invalid JSON payload"`
- SDK 不可用 → 503 + `error: "signature_check_unavailable"` + `signature_mode: "prod_unavailable"`

### 2.3 前端影响

- ✅ **沙箱开发环境**:继续工作,响应多 3 字段,前端忽略即可
- ⚠️ **生产环境联调**:需后端先设 `STRIPE_WEBHOOK_SECRET`,否则 webhook 全部 sandbox_skip
- ❌ **前端不要 retry on 5xx**:503 `signature_check_unavailable` 表示 SDK 缺失,应报警而非 retry

---

## 三、端点总数对比

| 维度 | v1.4 | v1.4.1 | v1.5 |
|---|---|---|---|
| paths | 27 | 36 | 40 |
| endpoints | 33 | 44 | 48 |
| tags | 9 | 12 | 13 |
| routers | 9 | 12 | 13 |

---

## 四、自动生成命令

```bash
cd backend
npx openapi-typescript docs/openapi-frozen-v1.5.json \
  --output src/types/api-v1.5.ts
# 或
npx openapi-typescript-codegen --input docs/openapi-frozen-v1.5.json \
  --output src/types/api-v1.5
```

---

## 五、向后兼容性

- ✅ **所有 v1.4.1 端点保留**:路径 / 方法 / 请求体 / 响应体 schema 不变
- ⚠️ **webhook 响应新增 3 字段**:旧前端代码忽略即可,无需修改
- ✅ **新增 4 端点独立标签 `admin`**:不影响业务端点的 TypeScript 类型

---

## 六、QA checklist

- [ ] 前端 `pnpm dev` 重启后,`src/types/api-v1.5.ts` 含 48 endpoints
- [ ] Webhook 测试:沙箱模式下响应含 `signature_skipped: true`
- [ ] 订阅成功路径仍正常(sandbox-complete 端点未变更)
- [ ] Admin 端点 4 个在 `src/types/api-v1.5.ts` 中可见
- [ ] FE-010 changelog 已 commit

---

> **下一步**:M7-t8(PWA + CI 实跑配置)