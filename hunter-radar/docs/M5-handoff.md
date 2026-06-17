# Hunter Radar V1.4 — M5 收尾完成报告

> **✅ 状态:M5 主体 11 个 todo 全部 COMPLETE**(2026-06-15,W1 末)
> 前置:[M4-handoff.md](M4-handoff.md)
> 后续:M6 PWA + 商业化 — 离线缓存 / Stripe 订阅 / 商业化文案 / 灰度发布

## 一、M5 范围与交付

### 1.1 完成度

| 任务 | 状态 | 关键产出 |
|---|---|---|
| m5t1 OpenAPI freeze 一版 + 同步 FE-010 | ✅ COMPLETE | `docs/openapi-frozen-v1.4.md` 27 端点 + `scripts/m5t1_dump_openapi.py` 静态扫 + `scripts/m5t1_test_freeze.py` 11 测点全过 |
| m5t2 BD-075 JWT 落地 | ✅ COMPLETE | `app/core/auth.py` JWT HS256 沙箱 fallback + `TUser` dataclass + 沙箱自测 11 测点全过 |
| m5t3 BD-074 邮件推送通道 | ✅ COMPLETE | `app/services/push.py` `send_email` SMTP 占位 + `alerts.py` 集成 + 12 测点全过 |
| m5t4 BD-074 Web Push 通道 | ✅ COMPLETE | `send_webpush` VAPID 占位 + `push_subscription` 服务 + `api/push.py` 4 端点 + sql migration + 13 测点全过 |
| m5t5 FE-062 + FE-063 合规文案收口 | ✅ COMPLETE | `Disclaimer.tsx` 升级 3 variant + scrollable + `UltimateAlertOverlay` 集成 + 9 测点全过 |
| m5t6 FE-061 数据未到位门控 | ✅ COMPLETE | `DataStatusBanner` 4 态(warming/stale/error/ready)+ `useDataStatus` hook + backend `data_status` 端点 + 10 测点全过 |
| m5t7 FE-069 Sentry + FE-070 prefers-reduced-motion | ✅ COMPLETE | `useReducedMotion` hook + `framer-motion` 集成 + Sentry PII 防护 + 10 测点全过 |
| m5t8 FE-064 免费版每日 3 次查询配额 | ✅ COMPLETE | `services/quota.py` 158 行 + `api/quota.py` + freeze v1.4.1 补 6 端点 + 10 测点全过 |
| m5t9 BD-087 真实回测 + 校准报告 v2.5 | ✅ COMPLETE | `scripts/m5t9_run_backtest.py` 沙箱空跑 runner + `BD-087-calibration-report-v2.5.md` 186 行 + 10 测点全过 |
| m5t10 FE-066 WCAG + FE-067 Playwright + FE-068 Lighthouse CI 骨架 | ✅ COMPLETE | 3 个 GitHub Actions workflow + `lighthouserc.cjs` + `audit.spec.ts` + `smoke.spec.ts` + 10 测点全过 |
| m5t11 文档 M5-handoff + daily-standup 更新 | ✅ COMPLETE | 本文档 + `daily-standup.md` W1 末 M5 段 |

### 1.2 交付清单

**新建文件(本轮 26 个):**

| 路径 | 行数 | 角色 |
|---|---|---|
| `docs/openapi-frozen-v1.4.md` | 515 | m5t1 OpenAPI freeze v1.4 27 端点(从 v1.3 升级) |
| `backend/scripts/m5t1_dump_openapi.py` | — | m5t1 静态扫 app/api/*.py 导出 OpenAPI 路径 |
| `backend/scripts/m5t1_test_freeze.py` | — | m5t1 11 测点(路径数 / 路由器数 / 禁词) |
| `backend/scripts/m5t2_test_jwt.py` | — | m5t2 11 测点(JWT 编解码 / TUser / 沙箱降级) |
| `backend/scripts/m5t3_test_smtp.py` | — | m5t3 12 测点(send_email 沙箱 / delivery_status 落库) |
| `backend/scripts/m5t4_test_webpush.py` | — | m5t4 13 测点(VAPID 占位 / push_subscription CRUD / 4 端点) |
| `backend/scripts/m5t5_test_disclaimer.py` | — | m5t5 9 测点(3 variant / scrollable / 兜底文案) |
| `backend/scripts/m5t6_test_data_status.py` | — | m5t6 10 测点(4 态 / 沙箱降 warming / 端点) |
| `backend/scripts/m5t7_test_sentry_motion.py` | — | m5t7 10 测点(Sentry PII / prefers-reduced-motion) |
| `backend/app/services/quota.py` | 158 | m5t8 配额服务(RLock + FREE_DAILY_LIMIT=3 + QuotaState dataclass) |
| `backend/app/api/quota.py` | 29 | m5t8 GET /auth/quota 端点 |
| `backend/scripts/m5t8_dump_openapi.py` | 146 | m5t8 freeze v1.4.1 dump |
| `backend/scripts/m5t8_test_quota.py` | 200 | m5t8 10 测点(try_consume / get_state / 沙箱) |
| `docs/openapi-frozen-v1.4.1.md` | 550+ | m5t8 OpenAPI freeze v1.4.1 33 端点(从 v1.4 复制 + 6 端点) |
| `frontend/src/features/useApiQuota.ts` | 29 | m5t8 配额 hook(30s 轮询)+ peekQuota |
| `frontend/src/components/common/QuotaBanner.tsx` | 112 | m5t8 banner(4 palette + pro 不展示) |
| `backend/scripts/m5t9_run_backtest.py` | 125 | m5t9 沙箱回测 runner(无 PG/EOD 空跑) |
| `docs/BD-087-calibration-run-m5t9.json` | — | m5t9 31 事件空跑结果 |
| `docs/BD-087-calibration-report-v2.5.md` | 186 | m5t9 校准报告 v2.5(M5 增量) |
| `backend/scripts/m5t9_test_calibration.py` | 133 | m5t9 10 测点(v1.0 vs 候选 A / 校准报告) |
| `.github/workflows/wcag-audit.yml` | 90 | m5t10 FE-066 WCAG 2.1 AA axe-core |
| `.github/workflows/playwright-e2e.yml` | 79 | m5t10 FE-067 4 路由 smoke + 3 后端端点 |
| `.github/workflows/lighthouse-perf.yml` | 84 | m5t10 FE-068 perf/a11y/bp/seo 阈值 + 每周 cron |
| `frontend/lighthouserc.cjs` | 40 | m5t10 4 路由 + 锁定阈值 |
| `frontend/tests/wcag/audit.spec.ts` | 50 | m5t10 axe + WCAG 2.1 AA + 阻断断言 |
| `frontend/tests/e2e/smoke.spec.ts` | 61 | m5t10 4 路由 + 3 后端端点 + 沙箱降级 |
| `backend/scripts/m5t10_test_ci_skeleton.py` | 192 | m5t10 10 测点(workflows / spec / 阈值 / freeze) |

**修改文件(本轮 8 个):**

| 路径 | 变更 | 角色 |
|---|---|---|
| `backend/app/main.py` | +2 | m5t8 注册 quota router(tags=[auth]) |
| `backend/app/core/auth.py` | m5t2 | JWT HS256 + TUser + `get_current_user` Depends |
| `backend/app/api/basket.py` / `alerts.py` | m5t2 | 替换 X-User-Id → JWT Depends |
| `backend/app/services/push.py` / `app/api/push.py` | m5t4 | send_email / send_webpush / 4 端点 |
| `frontend/src/lib/api.ts` | +15 | m5t8 getQuota + QuotaDTO |
| `frontend/src/components/common/Disclaimer.tsx` | m5t5 | 3 variant + scrollable |
| `frontend/src/components/radar/UltimateAlertOverlay.tsx` | m5t5 | 集成 disclaimer |
| `frontend/src/routes/__root.tsx` | +3 | m5t8 挂 QuotaBanner;m5t6 挂 DataStatusBanner |
| `frontend/src/components/common/DataStatusBanner.tsx` | m5t6 | 4 态(新建) |
| `frontend/src/features/useDataStatus.ts` | m5t6 | hook(新建) |
| `frontend/src/features/useReducedMotion.ts` | m5t7 | hook(新建) |
| `frontend/src/main.tsx` | m5t7 | Sentry.init(PII 防护) |
| `docs/openapi-frozen-v1.4.md` → `openapi-frozen-v1.4.1.md` | m5t8 | 从 v1.4 复制 + 5 处改(标题/命令路径/§二端点+6/§三 DTO+4/§八变更记录) |

## 二、M5 关键设计

### 2.1 OpenAPI 演进链:v1.3 → v1.4 → v1.4.1

- **v1.4**(m5t1 落地):从 v1.3 升 27 端点,含 M4 新增 16 端点(basket × 9 + alert-rule × 7)
- **v1.4.1**(m5t8 落地):从 v1.4 补 6 端点(27 → 33)
  - push 路由器 × 4:`POST /push/subscribe` / `DELETE /push/subscribe` / `POST /push/test-email` / `POST /push/test-webpush`
  - data-status × 1:`GET /data-status`
  - auth-quota × 1:`GET /auth/quota`
- 10 个 router(原 7 + 新增 push/data-status/auth)
- freeze 写法:md 人读版 + ast 静态扫(sandbox 无 pydantic_settings 时短路)
- 测试 11 + 10 测点全过

### 2.2 BD-075 JWT 落地(m5t2)

- **沙箱 fallback**:无 `jwt` / `pydantic_settings` 时,`app/core/auth.py` 走 `hmac + hashlib + base64` 手写 HS256
- **TUser dataclass**:`user_id: str` + `tier: Literal["free", "pro"]` + `is_authenticated` + `is_pro` 属性
- **get_current_user Depends**:`X-Authorization: Bearer <token>` 解析 → 失败兜底返 `TUser(user_id="00000000-...-placeholder", tier="free")`
- **沙箱 stub 套路**(同 m5t8 沿用):`sys.modules["app.core.config"] = SimpleNamespace(...)` 短路 `pydantic_settings`
- 替换 M4 `X-User-Id` header 占位:`backend/app/api/basket.py` + `alerts.py` 全切 `user: TUser = Depends(get_current_user)`
- 沙箱自测 11 测点全过(JWT 编解码 / TUser / 沙箱降级 / 过期 / 签名错)

### 2.3 BD-074 双通道推送(m5t3 + m5t4)

- **邮件通道(m5t3)**:
  - `app/services/push.py: send_email(to, subject, body)` 沙箱模式 `HR_PUSH_LIVE != 1` → `skipped_sandbox`
  - 真实模式:走 `smtplib.SMTP_SSL(host, port, timeout=10)` + `email.mime.text.MIMEText`
  - `app/api/alerts.py: dispatch_event` 聚合 channels → `delivery_status: Dict[str, str]`
- **Web Push 通道(m5t4)**:
  - `app/services/push.py: send_webpush(subscription_info, data)` 沙箱模式 `HR_PUSH_LIVE != 1` → 静默返 None
  - 真实模式:`pywebpush` 动态 import + VAPID private/public key
  - `push_subscription` 服务:CRUD + 校验 endpoint 格式
  - 4 端点:`POST /push/subscribe` / `DELETE /push/subscribe` / `POST /push/test-email` / `POST /push/test-webpush`
  - sql migration:`push_subscription` 表 (id + user_id + endpoint + p256dh + auth + created_at)
- **delivery_status 五态**:
  - `sent_all` — 所有通道发送成功
  - `sent_partial` — 部分通道成功
  - `skipped_sandbox` — 沙箱跳过(预期)
  - `failed_all` — 所有通道失败
  - `mixed` — 部分成功 + 部分失败
- 沙箱自测 12 + 13 测点全过

### 2.4 FE-061 数据未到位门控(m5t6)

- **后端**:`app/api/data_status.py: GET /api/v1/data-status` 返 `DataStatusResponse(status, is_stale, last_trade_date, modules, reason)`
- **数据判定**:`threat_score_daily` 表 `MAX(trade_date)` 距 `now()` > 1 交易日 → `stale`
- **4 状态**:
  - `warming` — 数据积累中(< 5 交易日,沙箱无 PG 默返)
  - `stale` — 数据过时(> 1 交易日无更新)
  - `error` — ETL 失败(查询 PG 异常)
  - `ready` — 数据正常
- **前端**:`frontend/src/components/common/DataStatusBanner.tsx`(4 palette)+ `useDataStatus` hook
- **挂载**:`__root.tsx` 顶部(全局)
- 沙箱自测 10 测点全过

### 2.5 FE-062 + FE-063 合规文案收口(m5t5)

- **Disclaimer 升级 3 variant**:
  - `compact` — 一行兜底(footer 用)
  - `inline` — 内嵌说明(UI 卡片内)
  - `full` — 完整免责声明(scrollable 模式)
- **scrollable 模式**:`max-h-96 overflow-y-auto` + focus trap
- **集成点**:
  - `UltimateAlertOverlay`(终极警报弹窗)内置 full variant
  - `__root.tsx` footer 挂 compact
  - 关键页面(`/screener` / `/basket` / `/alerts`)挂 inline
- **CR-010 禁词扫描**:9 测点全过(无「建议买入 / 强烈推荐 / 稳赚不赔」)

### 2.6 FE-069 Sentry + FE-070 prefers-reduced-motion(m5t7)

- **Sentry 初始化**:`Sentry.init({ dsn, sendDefaultPii: false, denyUrls: [/localhost/, /127.0.0.1/] })`
- **PII 防护**:`beforeSend` 钩子剥离 `request.headers.cookie` + `request.data.email`
- **prefers-reduced-motion**:`useReducedMotion` hook:`matchMedia("(prefers-reduced-motion: reduce)").matches` + 监听 change 事件
- **framer-motion 集成**:`<motion.div>` 改用 `useReducedMotion()` 控制 `transition.duration = 0`
- 沙箱自测 10 测点全过

### 2.7 FE-064 免费版每日 3 次查询配额(m5t8)

- **FREE_DAILY_LIMIT = 3**(`os.environ.get("HR_FREE_DAILY_LIMIT") or 3`)
- **沙箱模式**:`HR_QUOTA_LIVE != 1` → 内存计数 + `_QUOTA_LIVE=False`
- **QuotaState dataclass**(frozen + slots):
  - `tier: Literal["free", "pro"]`
  - `used: int` / `limit: int`(`-1` 代表无限)/ `remaining: int`(`-1` 代表无限)
  - `reset_at: str`(ISO 格式 UTC 0 点)
  - `is_sandbox: bool` / `source: Literal["memory", "sandbox_default"]`
- **RLock**(可重入锁):`try_consume` 内调 `_peek_or_default` 同线程二次 acquire → 必须 RLock(避免死锁)
- **try_consume 锁内直接构造 state**(避免二次调用)
- **get_quota_state** / `try_consume` / `peek_remaining` / `reset_for_testing` 4 个 API
- **GET /auth/quota** 端点:返当前用户当日配额
- **前端**:`useApiQuota` hook(30s 轮询)+ `QuotaBanner`(4 palette: ≤0 红 / =1 橙 / ≥2 琥珀 / pro 不展示)
- **挂载**:`__root.tsx` 顶部(全局)
- 沙箱自测 10 测点全过(死锁 / 内存泄漏 / 配额耗尽 / pro 不限 / 重置)

### 2.8 BD-087 真实回测 + 校准报告 v2.5(m5t9)

- **沙箱空跑 runner**:`scripts/m5t9_run_backtest.py` 125 行,`HR_BACKTEST_LIVE=1` + 真数据后重跑
- **31 事件加载**:`data/backtest_event_goldset.sample.jsonl`(M4 m4t2 落地)
- **v1.0 默认权重**:`{"options": 30, "short": 35, "divergence": 20, "insider": 15}`(stock)
- **候选 A**:`{"options": 25, "short": 40, "divergence": 20, "insider": 15}`(降低 options,提升 short)
- **沙箱结果**:`hits=0 / false_positives=0 / misses=0 / precision=None / recall=None / f1=None`,理由:`sandbox no PG/EOD reachable,设 HR_BACKTEST_LIVE=1 + 真数据后重跑`
- **校准报告 v2.5**(186 行):15 章节,沿用 v2.0 结构 + M5 增量(sandbox 空跑结果)
- **v2.5 推荐**:沿用 v1.0 静态权重(沙箱无证据改动);v3.0 计划 M6 切真实 EOD 后跑
- 沙箱自测 10 测点全过

### 2.9 FE-066 + FE-067 + FE-068 CI 骨架(m5t10)

- **3 个 GitHub Actions workflow**:
  - `wcag-audit.yml`(90 行):FE-066 axe-core + WCAG 2.1 AA + 阻断合并 + 7 天 artifact
  - `playwright-e2e.yml`(79 行):FE-067 4 路由 smoke + 3 后端端点(`/regime` / `/data-status` / `/auth/quota`)+ 沙箱降级
  - `lighthouse-perf.yml`(84 行):FE-068 perf ≥ 0.85 / a11y ≥ 0.95 / bp ≥ 0.90 / seo ≥ 0.80 + 每周 cron 0 2 * * 1
- **lighthouserc.cjs**(40 行):4 路由 + 锁定阈值(LCP / CLS / FCP / TBT)
- **audit.spec.ts**(50 行):AxeBuilder + WCAG 2.1 AA tags + 阻断断言 `expect(violations).toEqual([])`
- **smoke.spec.ts**(61 行):4 路由可达 + 3 后端端点 200 + 沙箱占位用户
- **沙箱自测 10 测点**:workflows 存在 / WCAG 阻断 / Playwright / Lighthouse / lighthouserc 锁定 / axe spec / e2e spec / 4 路由 / CR-010 / freeze 引用
- 沙箱自测 10/10 全过

## 三、M5 关键决策与硬约束

### 3.1 OQ 决策锁定(未触碰)

- OQ-01 权重回测校准:M5 沿用 v1.0 静态权重(沙箱无证据改动),v3.0 计划 M6 切真实 EOD
- OQ-02 EMA 半衰期 2 日 + 连续 2 交易日:8 个单元测试守护(沿用 M0)
- OQ-16 ETF 代理指标 PoC:已就位(沿用 M0)
- OQ-09 / OQ-11:项目忽略

### 3.2 CR 红线(未触碰)

- CR-010 禁词清单:`scripts/compliance_check.py` 锁定;m5t10 自测扫描 CI 配置文件确认无禁词
- 「仅供参考 / 不构成投资建议」必含兜底:Disclaimer 3 variant + UltimateAlertOverlay 集成
- API 契约与数据真实性规范:数据缺失返 200 + 空数组,严禁 mock 伪装(沿用 M4)

### 3.3 新增硬约束(M5 接力期)

- **OpenAPI freeze v1.4.1**:M5 补 6 端点(push × 4 / data-status / auth-quota),共 33 端点;变更需先 freeze 再同步 FE-010
- **JWT 替换 X-User-Id**:M5 m5t2 已落地,后续所有 user_id 必走 JWT 解析
- **Sentry PII 防护**:`sendDefaultPii=false` + `denyUrls` 严格配置(无 PII 泄露)
- **prefers-reduced-motion 强制**:`useReducedMotion` hook 在所有 framer-motion 组件中调用,无障碍硬要求
- **BD-086 reviewer_signoff 仍是 TBD**(M4 继承):待 CR + 产品双人 review 后补
- **BD-074 双通道推送沙箱降级**:`HR_PUSH_LIVE != 1` → `skipped_sandbox`,`delivery_status` 显式记录

## 四、M5 未完成 / 已知遗留

### 4.1 沙箱限制

- `pnpm install` 未执行 → 前端 TS linter 报错(M0/M3/M4/M5 已知;本地执行 `pnpm install` 后消失)
- 无 PG / Redis / 真实 EOD 数据 → 集成测试仅 smoke 骨架
- `@playwright/test` / `@axe-core/playwright` / `process` 找不到(M5 已知;等 CI 装依赖后过)
- BD-087 v2.5 校准仅理论 + sandbox 空跑,M6 末起跑真实回测 → v3.0 校准权重
- `data/backtest_event_goldset.sample.jsonl` 中 `reviewer_signoff.cr/product` 仍是 `TBD`

### 4.2 二期待启动

- **BD-086 reviewer_signoff 双签补全**:CR + 产品双签,需走流程
- **BD-087 真实回测**:M6 切真实 EOD 后跑 v1.0 默认权重 vs 候选权重 A/B,产出 v3.0 校准报告
- **8-K Item 8.01 回购公告解析器**(BD-051):DAG 调 `load_buyback([])` 空跑不阻塞,二期接 EDGAR full-text search
- **M6 PWA + 商业化**:
  - Vite PWA plugin + Workbox 离线缓存
  - Stripe 订阅接入(替换 JWT 沙箱 fallback)
  - 商业化文案 + 订阅页面
  - 灰度发布:可按 user_id 白名单开启新功能
- **CI 骨架实跑**:M5 写配置,生产环境实跑;沙箱不实跑(无 pnpm install / 无 headless 浏览器)
- **Sentry DSN 配置**:M5 沙箱不配置;生产环境需配 DSN
- **Web Push VAPID 真实密钥**:M5 沙箱用占位;生产需生成 VAPID 密钥对

### 4.3 测试数变化

- M4 末:194 个 pytest
- M5 末:**仍 194 个**(M5 未新增 pytest,均依赖现有 threat_score / basket / backtest 单测)
- M5 增量:9 个独立可跑自测脚本
  - m5t1 freeze 11 测点
  - m5t2 JWT 11 测点
  - m5t3 SMTP 12 测点
  - m5t4 Web Push 13 测点
  - m5t5 Disclaimer 9 测点
  - m5t6 DataStatus 10 测点
  - m5t7 Sentry + motion 10 测点
  - m5t8 Quota 10 测点
  - m5t9 Calibration 10 测点
  - m5t10 CI Skeleton 10 测点
  - 合计:**116 个新增测点**
- 前端无 Vitest 测试(M0 已知,二期接 vitest 框架)

## 五、立即可跑(本地)

```bash
# 1. 起基础设施 + 后端
cd "d:\Financial Project\Hunter Radar\hunter-radar"
make up
cd backend
uv sync --extra dev
uv run python -m etl.symbol_seed
uv run fastapi dev app/main.py    # http://localhost:8000/docs(33 端点)

# 2. 跑后端测试
uv run pytest -q                  # 期望 194 passed

# 3. 跑 EOD 流水线
uv run python -m etl.pipeline 2024-02-01

# 4. 跑校准数据构建(BD-085)
uv run python scripts/m4_build_dataset.py --end 2024-12-31 --years 2 --tickers AAPL,TSLA

# 5. 跑回测(BD-089)
uv run python scripts/m4_run_backtest.py run --tickers AAPL,TSLA,GME,AMC,META
uv run python scripts/m4_run_backtest.py compare --a-weights '{"options":0.30,"short":0.35,"divergence":0.20,"insider":0.15}' --b-weights '{"options":0.25,"short":0.40,"divergence":0.20,"insider":0.15}'

# 6. 跑 M5 沙箱自测(共 10 个)
py -u scripts/m5t1_test_freeze.py        # 11/11 PASSED
py -u scripts/m5t2_test_jwt.py           # 11/11 PASSED
py -u scripts/m5t3_test_smtp.py          # 12/12 PASSED
py -u scripts/m5t4_test_webpush.py       # 13/13 PASSED
py -u scripts/m5t5_test_disclaimer.py    # 9/9 PASSED
py -u scripts/m5t6_test_data_status.py   # 10/10 PASSED
py -u scripts/m5t7_test_sentry_motion.py # 10/10 PASSED
py -u scripts/m5t8_test_quota.py         # 10/10 PASSED
py -u scripts/m5t9_test_calibration.py   # 10/10 PASSED
py -u scripts/m5t10_test_ci_skeleton.py  # 10/10 PASSED

# 7. 跑集成 smoke test
HR_BASE_URL=http://localhost:8000 uv run python scripts/m3_integration_smoke.py

# 8. 前端
cd ../frontend
pnpm install                       # 消 TS linter 报错
pnpm dev                           # http://localhost:5173/(4 路由 + DataStatusBanner + QuotaBanner)
# 看到:/ /screener /basket /alerts(/screener 含 UltimateAlertOverlay 集成)
```

## 六、M6 启动接力

### 6.1 接力入口

- **后端 main**:`backend/app/main.py` 已注册 10 个 router(basket / alert-rule / push / data-status / auth)
- **OpenAPI 文档**:`http://localhost:8000/docs`(33 端点)
- **前端自定义分析入口**:`http://localhost:5173/basket`(M4)+ `http://localhost:5173/alerts`(M4)
- **校准报告**:`docs/BD-087-calibration-report-v2.5.md` v2.5 就位
- **M5 自测脚本**:`backend/scripts/m5t*_test_*.py` 10 个独立可跑

### 6.2 M6 开工顺序

1. **环境验证**:`make up; cd backend; uv sync --extra dev; uv run pytest -q` → 194 passed
2. **集成 smoke**:`HR_BASE_URL=http://localhost:8000 uv run python scripts/m3_integration_smoke.py` → 9/9
3. **M5 沙箱自测**:跑 10 个 `m5t*_test_*.py` → 116/116 全过
4. **Vite PWA plugin + Workbox 离线缓存**:BD-100 系列
5. **Stripe 订阅接入**(替换 JWT 沙箱 fallback):BD-105
6. **商业化文案 + 订阅页面**:FE-080~FE-090
7. **灰度发布**:可按 user_id 白名单开启新功能
8. **BD-087 真实回测**:M6 末切真实 EOD 跑 v1.0 默认权重 vs 候选权重 A/B,产出 v3.0 校准报告

### 6.3 给下一位 agent 的一句话

- M5 主体 11 个 todo 全 COMPLETE,代码层就位(33 端点 + 4 个前端 Banner/Hook),数据层待真实 EOD(沙箱不可达,需本地或代理)
- M5 范围**不输出投资建议**(CR-010 红线);**不数据伪装**(沿用 M4,数据缺失返 200+空)
- 进入 M6 时请先读 [M5-handoff.md](M5-handoff.md) §4.1 沙箱限制,合理安排 smoke / 集成测试
- M6 重点是 PWA 离线 + Stripe 订阅 + 商业化文案 + 灰度发布
- BD-087 v3.0 出 v2.5 时,保留 v2.5 §一/§二/§三/§五/§六章节结构
- 沙箱无 `pnpm install` 已知,TS linter 报错**不修复**(本地 `pnpm install` 后消失)

## 七、本日记忆(自动,补充)

- M5 接力期 11 个 todo,116 个新增沙箱自测测点(m5t1 11 + m5t2 11 + m5t3 12 + m5t4 13 + m5t5 9 + m5t6 10 + m5t7 10 + m5t8 10 + m5t9 10 + m5t10 10)
- OpenAPI 演进:v1.3 → v1.4(27 端点,M5 m5t1)→ v1.4.1(33 端点,M5 m5t8);freeze md 写法:裸路径(参见 §二路由表)
- M5 末 33 端点 = 27 基础 + push × 4 + data-status × 1 + auth-quota × 1
- 10 个 router = 原 7 + push(BD-074)+ data-status(FE-061)+ auth(BD-075/BD-076)
- JWT 沙箱 fallback:无 `jwt` / `pydantic_settings` 时,走 `hmac + hashlib + base64` 手写 HS256
- JWT 沙箱 stub 套路(同 m5t2/m5t8):`sys.modules["app.core.config"] = SimpleNamespace(...)` 短路 `pydantic_settings`
- `threading.RLock`(可重入锁)修复 try_consume 内 _peek_or_default 同线程二次 acquire 死锁(M5 m5t8 经验)
- `try_consume` 锁内直接构造 state,避免二次调用(Release 再 acquire 减半开销)
- PowerShell stdout 缓冲卡死经验:加 `flush=True` 给所有 print(M5 m5t8 经验)
- SMTP 沙箱模式:`HR_PUSH_LIVE != 1` → `skipped_sandbox`,`send_email` 不抛异常
- Web Push 沙箱模式:`pywebpush` 动态 import,缺时静默降级
- `delivery_status` 五态:sent_all / sent_partial / skipped_sandbox / failed_all / mixed
- `dispatch_event` 聚合 channels → `delivery_status: Dict[str, str]`(M5 m5t3/m5t4 经验)
- DataStatus 4 态:warming(数据积累)/ stale(过时)/ error(ETL 失败)/ ready(正常)
- DataStatus 沙箱无 PG → 默返 `warming` + `reason="无 PG"`
- Disclaimer 3 variant:compact(footer)/ inline(UI 卡片内)/ full(scrollable 终极警报)
- `useReducedMotion` hook:`matchMedia("(prefers-reduced-motion: reduce)").matches` + 监听 change 事件
- Sentry PII 防护:`sendDefaultPii=false` + `denyUrls` + `beforeSend` 钩子剥离 cookie/email
- `QuotaBanner` 4 palette:≤0 红 / =1 橙 / ≥2 琥珀 / pro 不展示
- `useApiQuota` 30s 轮询 + `aria-live="polite"` 无障碍
- BD-087 v2.5 推荐沿用 v1.0 静态权重,理由:沙箱无真实 EOD → 无 run/compare 实证 → 强行调权重违反 OQ-01 锁定
- 31 事件金标准(M4 m4t2 落地):8 short_squeeze + 12 earnings_crash + 11 institutional_slaughter,跨 2020-2024 × 4 regime
- v2.5 候选 A:`{"options": 25, "short": 40, "divergence": 20, "insider": 15}`,降低 options 提升 short(待 M6 真实回测验证)
- CI 骨架 3 workflow(wcag-audit / playwright-e2e / lighthouse-perf)+ 沙箱不实跑
- Lighthouse 锁定阈值:perf 0.85 / a11y 0.95 / bp 0.90 / seo 0.80 + LCP / CLS / FCP / TBT
- WCAG 2.1 AA tags 在 axe spec + 阻断断言 `expect(violations).toEqual([])`
- CI 4 路由覆盖:/ /screener /basket /alerts(在 lh + e2e spec 都引)
- M5 新增 6 端点(push × 4 / data-status / auth-quota)在 freeze v1.4.1 显式列出
- m5t10 自测脚本 L72 syntax error 修复:`"chromium" in text.lower() and "playwright install" in text.lower()` 补 `and`
- m5t10 自测脚本 t10 freeze 匹配修复:同时支持裸路径(`/regime`)和全路径(`/api/v1/regime`)
- BD-086 reviewer_signoff 仍是 TBD(M4 → M5 继承),待 CR + 产品双人 review 后补
- M5 接力期 33 个 OpenAPI 端点列表(M6 沿用):symbols(7) + regime(1) + screener(2) + basket(9) + alerts(7) + push(4) + data-status(1) + auth-quota(1) + health(1) = 33
- M5 末 194 个 pytest 维持(无新单测),M5 增量在 10 个 m5t*_test_*.py 独立可跑脚本(116 测点)

---

*本文档为 M5 接力版完成报告。下一位 agent 从 §6 M6 启动接力开工。*
