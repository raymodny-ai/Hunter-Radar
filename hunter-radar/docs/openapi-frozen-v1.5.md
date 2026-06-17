># Hunter Radar V1.5 — OpenAPI Freeze v1.5

> **🧊 Freeze 时点:2026-06-16(M7 接力期补 freeze,W2 末 v1.4.1 → v1.5 增量)**
> 配套:本仓库后端 `app/api/*.py` 共 **48 个端点**(13 router + 2 health;v1.4.1 起 44 + 4 新增)
> 配套:`docs/openapi-frozen-v1.5.json`(机器可读,由 `scripts/m7t7_dump_openapi.py` 静态扫)
> 同步:本 freeze 是 FE-010(`openapi-typescript` 自动生成)与机构版复制方的前置依赖
> 解除 freeze 流程:见 §四 变更流程
> 上一 freeze 版:v1.4.1(2026-06-15 M5 接力期,44 端点)→ `docs/openapi-frozen-v1.4.1.{json,md}`

---

## 一、概述

### 1.1 范围

- **base URL**:`http://localhost:8000`(开发)/ `https://api.hunter-radar.example`(生产)
- **OpenAPI 3.0.3**(FastAPI 0.136.3 自动生成)
- **不包含**:Sentry / Redis / Postgres 内部接口
- **包含**:`/api/v1/*` 业务端点 + `/health` 运维端点 + `/` 根描述
- **M7 增量**:4 个 admin 端点 + 1 个 webhook 行为变更

### 1.2 自动生成命令(生产环境)

```bash
cd backend
uv run fastapi dev app/main.py   # 起服务
curl http://localhost:8000/openapi.json > docs/openapi-frozen-v1.5.json
# 沙箱 fallback(无 PG / Redis / asyncpg / sentry_sdk / stripe):
py -u backend/scripts/m7t7_dump_openapi.py
```

> **沙箱 fallback**:
> 本仓库 `docs/openapi-frozen-v1.5.json` 由 `scripts/m7t7_dump_openapi.py` 静态扫描
> `app/api/*.py` 的 `@router.{get,post,put,delete}` + DTO 字段产出,
> 等同于人读版 §二 / §三 的机器可读形态。生产环境务必用 `uv run` 覆盖一次。

### 1.3 OpenAPI freeze 硬约束(沿用 M3 / M4 / M5)

- **新增端点**:必须在 freeze 解除流程中登记,不得私下增路由
- **修改端点**(字段 / 路径 / 状态码 / 错误体):必须先 freeze 解除,改完再 freeze
- **删除端点**:必须先 freeze 解除,标 deprecated 90 天后才物理删除
- **数据缺失语义**:统一返 200 + 空数组 / 空对象,严禁 5xx 透传(Redis 沙箱降级到原函数)

---

## 二、M7 增量(v1.4.1 → v1.5)

### 2.1 新增 4 端点(全部走 `admin` 标签)

| # | Method | Path | 角色 | 状态 | 关联 todo |
|---|---|---|---|---|---|
| 1 | POST | `/api/v1/admin/etl/run` | 触发 BD-085 ETL 重跑 | m7t7 sandbox stub | 沙箱:etl/backtest_dataset_real |
| 2 | POST | `/api/v1/admin/backtest/run` | 触发 v3.0-final backtest | m7t7 sandbox stub | 沙箱:m7t4_run_backtest_v30_final |
| 3 | GET | `/api/v1/admin/backtest/result` | 读最近 backtest 结果 | m7t7 sandbox stub | 读 docs/BD-087-calibration-run-m7t4.json |
| 4 | POST | `/api/v1/admin/webhook/replay` | 重放 sandbox webhook | m7t7 sandbox stub | 测试用,接 handle_webhook_event |

### 2.2 行为变更(端点不变)

| # | Method | Path | 变更内容 | 关联 todo |
|---|---|---|---|---|
| 1 | POST | `/api/v1/subscriptions/webhook` | 加 Stripe 签名校验(M7-t6 落地,R-31 风险解除) | m7t6 |

**webhook 行为变更详情**:
- **沙箱模式**(STRIPE_WEBHOOK_SECRET 未设)→ 返 200 + `signature_skipped=true` + `signature_mode=sandbox_skip` + `warning`(显式标注,绝不 mock 200 伪装成功)
- **真实模式**(secret 已设)→ 用 `stripe.Webhook.construct_event(payload, sig, secret)` 校验
- **SDK 不可用**(secret 已设)→ 503 `signature_check_unavailable`(不 mock 200 伪装)
- **签名错误** → 400 `invalid signature`
- **payload 非 JSON** → 400 `invalid JSON payload`
- **读 raw bytes**(`await request.body()`)而非 `await request.json()`(Stripe 签名校验需原始字节)

### 2.3 etl 层不暴露为 API

| 模块 | 位置 | 说明 |
|---|---|---|
| `etl/edgar_fulltext.py` | m7t5 | EDGAR full-text search 沙箱 stub,通过 admin/etl/run 触发,不直接暴露为 HTTP API |
| `etl/backtest_dataset_real.py` | m7t3 | BD-085 真实数据集 ETL stub,通过 admin/etl/run 触发 |
| `etl/sec_form4.py` / `etl/yfinance_pull.py` / `etl/finra_short.py` | M2 既有 | 现有 ETL 模块不暴露 API |

**理由**:ETL 是运维/后台任务,经 admin 触发更合理;暴露为 HTTP API 易被滥用。V1.5+ 若需要公开 API,走新的 `/api/v1/admin/*` 即可。

---

## 三、端点总数对比

| Freeze 版 | paths | endpoints | tags | router 数 | 增量来源 |
|---|---|---|---|---|---|
| v1.4(M0~M4) | 27 | 33 | 9 | 9 | 基础版 |
| v1.4.1(M5 接力期) | 36 | 44 | 12 | 12 | +push(m5t4) / +data-status(m5t6) / +auth-quota(m5t8) 6 端点 |
| **v1.5(M7 接力期)** | **40** | **48** | **13** | **13** | +admin 4 端点(m7t7)+ webhook 行为变更(m7t6)+ EDGAR ETL etl 层(m7t5 不暴露 API) |

### 3.1 13 router 列表

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
| **合计** | — | — | — | **48** | — |

---

## 四、变更流程(沿用 v1.4.1)

1. **申请**:`docs/freeze-bump-request.md` 写明:新增 / 修改 / 删除端点 + 业务理由 + review_mode(sandbox_stub / production)
2. **审批**:CR + Product 签字(参考 BD-086 双签)
3. **修改代码**:`app/api/*.py` 落地 + DTO 字段同步
4. **重 freeze**:跑 `scripts/m7t7_dump_openapi.py` → `docs/openapi-frozen-v1.5.json` 覆盖
5. **同步前端**:FE-010 changelog + `openapi-typescript` 重新生成
6. **通知**:在 `daily-standup.md` + 本 freeze md §二登记

---

## 五、风险与遗留

| ID | 风险 | 状态 | 缓解 |
|---|---|---|---|
| **R-31** | Stripe webhook 沙箱简化(无签名校验) | ✅ **本 freeze 解除**(m7t6) | webhook 显式标注 signature_skipped + signature_mode=sandbox_skip |
| **R-34**(新) | admin 端点暂免鉴权 | 🟡 已知 | V1.4 上线前加 admin role + JWT 校验 |
| **R-35**(新) | admin 端点暴露内部 ETL trigger | 🟡 已知 | V1.4 加 IP 白名单 + rate limit |
| **R-36**(新) | etl 层不暴露 API,前端无法直接拉 8-K 数据 | 🟡 已知 | V1.5 评估 `/api/v1/edgar/search?ticker=X&days=N` 公开端点 |

---

## 六、本日记忆(M7-t7 关键决策)

1. **v1.5 freeze 落地**:48 endpoints / 40 paths / 13 tags(M7-t7)
2. **新增 4 admin 端点**:`/api/v1/admin/{etl/run, backtest/run, backtest/result, webhook/replay}`(全部 sandbox stub)
3. **webhook 签名校验补全**:R-31 解除(沙箱显式 sandbox_skip + 真实模式 construct_event)
4. **EDGAR fulltext 不暴露 API**:通过 admin/etl/run 触发,避免滥用
5. **FE-010 同步**:前端 openapi-typescript 重生成 + changelog 同步(m7t7 收尾)
6. **R-34/35/36 风险新增**:admin 鉴权 + IP 白名单 + EDGAR 公开端点待 V1.5 评估

---

> **下一步**:M7-t8(PWA + CI 实跑配置:Workbox + Lighthouse + Sentry DSN + VAPID 真实密钥)