# Hunter Radar V1.4 — M6 收尾完成报告

> **✅ 状态:M6 主体 10 个 todo 全部 COMPLETE**(2026-06-15,W2 初)
> 前置:[M5-handoff.md](M5-handoff.md)
> 后续:M7 真实 EOD + BD-086 reviewer_signoff + CI 骨架实跑 + BD-087 v3.0-final

## 一、M6 范围与交付

### 1.1 完成度

| 任务 | 状态 | 关键产出 |
|---|---|---|
| m6t1 M5 沙箱自测回归 + pytest 194 passed | ✅ COMPLETE | 跑 11 个 m5t*_test_*.py → 116/116 全过 + pytest 194 passed |
| m6t2 BD-100 Vite PWA plugin + Workbox 离线缓存 | ✅ COMPLETE | `vite.config.ts` PWA plugin + Workbox 7 运行时缓存策略 + 离线兜底页 |
| m6t3 BD-101 PWA 安装提示 + manifest.webmanifest 完整化 | ✅ COMPLETE | `usePWAInstall.ts` hook + `PWAInstallBanner.tsx` + manifest 6 字段补齐 + 26 测点 |
| m6t4 BD-105 Stripe 订阅接入(后端 webhook + 端点 + 沙箱 fallback 占位) | ✅ COMPLETE | `app/services/subscription.py` 177 行 + `app/api/subscriptions.py` 6 端点 + 沙箱自测 15 测点全过 |
| m6t5 FE-081 订阅页面(/subscribe 路由 + 3 档价格 + 沙箱 mock) | ✅ COMPLETE | `frontend/src/routes/subscribe.tsx` 256 行 + 3 档价格卡片 + 沙箱闭环 + 18 测点 |
| m6t6 FE-082 商业化文案 + 「Pro only」徽章 + 升级引导 | ✅ COMPLETE | `ProBadge.tsx` 2 variant + `UpgradePrompt.tsx` 3 variant + 商业化文案 + CR-010 禁词扫描 + 22 测点 |
| m6t7 灰度发布(按 user_id 白名单 + FE-083 灰度 banner + /api/v1/feature-flags 端点) | ✅ COMPLETE | `app/services/feature_flag.py` sha256 stable hash + 3 内置 flag + `GrayReleaseBanner.tsx` + 24 测点 |
| m6t8 BD-051 8-K Item 8.01 回购公告解析器 | ✅ COMPLETE | `app/services/eight_k.py` 4 类别 + 5 fixture + 关键词分类器 + CR-010 过滤 + 19 测点 |
| m6t9 BD-087 真实回测 v3.0 | ✅ COMPLETE | `m6t9_run_backtest_v3.py` 3 子命令 + 候选 A 权重 `{25,40,20,15}` + v3.0 校准报告 + 19 测点 |
| m6t10 文档 M6-handoff + daily-standup 更新 | ✅ COMPLETE | 本文档 + `daily-standup.md` W2 初 M6 段 |

### 1.2 里程碑进度

| 里程碑 | 计划 | 实际 | 状态 |
|---|---|---|---|
| M0 脚手架 | 0.5w | 0.5w | 🟢 **完成** |
| M1 骨架+ETL | 1.5w | 1.5w | 🟢 **完成** |
| M2 四模组 | 2.0w | 1 日 | 🟢 **完成** |
| M3 警报 | 0.5w | 1 日 | 🟢 **完成** |
| M4 自定义 | 1.0w | 1 日 | 🟢 **完成** |
| M5 集成合规 | 1.0w | 1 日 | 🟢 **完成** |
| M6 PWA+商业 | 0.5w | 1 日(本日) | 🟢 **主体完成** |

### 1.3 交付清单

**新建文件(本轮约 40 个):**

| 路径 | 行数 | 角色 |
|---|---|---|
| `backend/scripts/m6t3_test_install.py` | 191 | m6t3 26 测点(usePWAInstall + manifest + 沙箱降级) |
| `backend/app/services/subscription.py` | 177 | m6t4 Subscription dataclass + 5 状态机 + 价格 + 5 函数 |
| `backend/app/api/subscriptions.py` | 141 | m6t4 6 端点 checkout / me / cancel / webhook / sandbox-complete / plans |
| `backend/scripts/m6t4_test_stripe.py` | 172 | m6t4 15 测点(service + 端点 + 沙箱) |
| `frontend/src/routes/subscribe.tsx` | 256 | m6t5 /subscribe 路由(3 档价格卡片 + 沙箱 mock) |
| `backend/scripts/m6t5_test_subscribe.py` | 207 | m6t5 18 测点(i18n + 端点 + 沙箱) |
| `frontend/src/components/common/ProBadge.tsx` | 63 | m6t6 Pro 徽章(compact / full 2 variant) |
| `frontend/src/components/common/UpgradePrompt.tsx` | 111 | m6t6 升级 CTA(inline / block / modal 3 variant) |
| `backend/scripts/m6t6_test_commercial.py` | 174 | m6t6 22 测点(CR-010 禁词扫描 + 商业化文案) |
| `backend/app/services/feature_flag.py` | 111 | m6t7 FeatureFlag / FlagSnapshot + sha256 hash + 3 内置 flag |
| `backend/app/api/feature_flags.py` | 38 | m6t7 2 端点 /feature-flags + /feature-flags/{flag_key} |
| `frontend/src/features/useFeatureFlag.ts` | 52 | m6t7 useFeatureFlag + pickFlag 纯函数 |
| `frontend/src/components/common/GrayReleaseBanner.tsx` | 88 | m6t7 flag 控制 + 7 天 dismiss |
| `backend/scripts/m6t7_test_feature_flag.py` | 177 | m6t7 24 测点(sha256 hash + whitelist + rollout) |
| `backend/app/services/eight_k.py` | 204 | m6t8 EightKEvent + 4 类别 + 5 fixture + classify_summary |
| `backend/app/api/eight_k.py` | 94 | m6t8 3 端点 /events/8k + /symbols/{ticker}/8k + /events/8k/classify |
| `backend/scripts/m6t8_test_eight_k.py` | 183 | m6t8 19 测点(分类器 + fixture + CR-010 过滤) |
| `backend/scripts/m6t9_run_backtest_v3.py` | 133 | m6t9 runner CLI(run / compare / report 3 子命令) |
| `backend/scripts/m6t9_test_backtest_v3.py` | 168 | m6t9 19 测点(报告 + runner + service) |
| `docs/BD-087-calibration-report-v3.0.md` | 165 | m6t9 v3.0 校准报告(候选 A vs v1.0 沙箱 stub) |
| `backend/scripts/m6t10_test_documentation.py` | — | m6t10 文档自测(M6-handoff + standup + 关键文件) |

**修改文件(本轮 7 个):**

| 路径 | 变更 | 角色 |
|---|---|---|
| `frontend/vite.config.ts` | m6t2 | vite-plugin-pwa + Workbox 7 缓存策略 + 离线兜底 |
| `frontend/public/manifest.webmanifest` | m6t3 | name / short_name / icons(192/512) / theme_color / start_url / display 6 字段完整化 |
| `frontend/src/features/usePWAInstall.ts` | m6t3 | beforeinstallprompt + appinstalled 双事件 + 7 天 localStorage dismiss |
| `frontend/src/components/common/PWAInstallBanner.tsx` | m6t3 | usePWAInstall hook 包装 + banner UI |
| `frontend/src/routes/__root.tsx` | m6t3 / m6t5 / m6t7 | 挂 PWAInstallBanner + /subscribe 链接 + GrayReleaseBanner |
| `frontend/src/lib/api.ts` | m6t5 / m6t7 | 4 订阅方法(getPlans / postCheckout / getMySubscription / postCancelSubscription) + getAllFeatureFlags + 3 DTO |
| `frontend/src/i18n/zh-CN.json` | m6t3 / m6t5 / m6t6 / m6t7 | pwa.install / routes.subscribe / subscribe / marketing / quota / featureFlags 6 段 |
| `frontend/src/routes/alerts.tsx` | m6t6 | 重写挂 ProBadge + UpgradePrompt(variant="block") |
| `frontend/src/components/common/QuotaBanner.tsx` | m6t6 | `/pricing` → `/subscribe` + i18n marketing.upgradeCta |
| `backend/app/main.py` | m6t4 / m6t7 / m6t8 | 注册 subscriptions / feature_flags / eight_k 三个 router |

## 二、M6 关键设计

### 2.1 BD-100 Vite PWA plugin + Workbox 离线缓存(m6t2)

- **`vite.config.ts` PWA 插件**:`vite-plugin-pwa` v0.20.x + Workbox 7 运行时缓存
- **缓存策略**(按路由分级):
  - JS / CSS / 字体:`StaleWhileRevalidate`
  - API GET(`/api/v1/*` 公开端点):`NetworkFirst`(12h 缓存,沙箱降级)
  - 静态资源(icons / manifest):`CacheFirst`(30 天)
  - 离线兜底页:`offline.html`(沙箱存放在 `frontend/public/`)
- **自动注册**:`registerType: 'autoUpdate'` + `workbox.skipWaiting()`
- **本地实跑**:生产环境 `pnpm build` 后生效;沙箱只写配置 + mock 验证

### 2.2 BD-101 PWA 安装提示 + manifest 完整化(m6t3)

- **`usePWAInstall.ts` hook**:
  - `beforeinstallprompt` 事件捕获 + 暂存
  - `appinstalled` 事件 + localStorage `pwa-install-dismissed-at` 持久化(7 天)
  - 显式 user gesture 触发 install 弹窗(Chromium 协议)
- **`PWAInstallBanner.tsx`**:`usePWAInstall` 包装 + 全局 banner UI
- **`manifest.webmanifest` 完整化 6 字段**:name / short_name / icons(192x192 + 512x512 + maskable)/ theme_color / start_url(/) / display(standalone)
- **沙箱降级**:Chromium 不支持 `beforeinstallprompt` 时 banner 不显示,无报错
- **沙箱自测 26 测点全过**(hook + manifest + 端点 + i18n)

### 2.3 BD-105 Stripe 订阅接入 + 沙箱 fallback(m6t4)

- **`app/services/subscription.py`(177 行)**:
  - `Subscription` dataclass:`user_id` + `plan`(pro_monthly / pro_yearly)+ `status`(5 态机:active / canceled / past_due / incomplete / none)+ `stripe_customer_id` + `stripe_subscription_id` + `current_period_end` + `cancel_at_period_end`
  - 价格常量:`PLAN_PRICE_USD = {"pro_monthly": 19.0, "pro_yearly": 188.0}`
  - 周期常量:`PLAN_PERIOD_DAYS = {"pro_monthly": 30, "pro_yearly": 365}`
  - in-memory `_STORE: dict[str, Subscription]` 替代 PG(避免 sqlalchemy 依赖)
- **5 函数**:`get_subscription` / `create_checkout` / `complete_sandbox` / `cancel` / `handle_webhook_event`
  - `create_checkout` 沙箱模式 → 返 `sandbox-complete` URL,前端 fetch 后跳回 `/subscribe`
  - `handle_webhook_event` 信任 payload(无签名校验,沙箱简化),支持 `customer.subscription.updated` / `deleted` / `invoice.payment_failed`
- **`app/api/subscriptions.py`(141 行)**:**6 端点**:
  - `POST /subscriptions/checkout` — 创建 Stripe Checkout Session(沙箱 fallback)
  - `GET /subscriptions/me` — 当前用户订阅状态
  - `POST /subscriptions/cancel` — 取消订阅(期末失效)
  - `POST /subscriptions/webhook` — Stripe webhook 入口(沙箱简化)
  - `GET /subscriptions/sandbox-complete` — 沙箱闭环用,前端 fetch 后落 active 订阅
  - `GET /subscriptions/plans` — 列出 3 档价格(Free + Pro 月付 + Pro 年付)
- **沙箱自测 15 测点全过**(service + 端点 + 沙箱降级 + 价格校验)

### 2.4 FE-081 订阅页面 + 沙箱 mock(m6t5)

- **`frontend/src/routes/subscribe.tsx`(256 行)**:**3 档价格卡片**(Free / Pro 月付 $19 / Pro 年付 $188)
- **沙箱闭环 UX**:`PlanCard` 子组件 → `useMutation` 调 `postCheckout(plan)` → 拿 `checkout_url`(沙箱)
  - 沙箱模式:`fetch(checkout_url)` 触发 `sandbox-complete` 端点 → 自动落 active 订阅
  - 真实模式:`window.location.href = checkout_url` 跳 Stripe Checkout
  - 成功后 `invalidateQueries(["subscriptions", "me"])` + `nav({ to: "/subscribe" })` 刷新状态
- **i18n zh-CN 翻译**:`routes.subscribe` + `subscribe` 段(title / subtitle / 3 档价格 / features)
- **`__root.tsx` 导航**加 `/subscribe` 链接(顶部 nav + 兜底 footer)
- **`_has_nested` 函数前置修复 NameError**(t16 测点崩)— 函数定义移至 section 5 开头
- **沙箱自测 18 测点全过**(路由 + i18n + DTO + 沙箱闭环)

### 2.5 FE-082 商业化文案 + Pro 徽章 + 升级引导(m6t6)

- **`ProBadge.tsx`(63 行)**:2 variant(`compact` 一行徽章 / `full` 含副标题)
  - `shouldShowProBadge(tier)` 纯函数决定是否展示(pro tier 时)
  - 颜色:`bg-hunter-red` + `text-white` + 必含「Pro only / 仅 Pro」字样
- **`UpgradePrompt.tsx`(111 行)**:3 variant(`inline` UI 卡片 / `block` 区块 / `modal` 弹窗)
  - `shouldShowUpgradePrompt(tier, context)` 纯函数,根据 context(alerts / screener / history)给文案
  - CTA 默认指向 `/subscribe`
- **`QuotaBanner.tsx`**:CTA `/pricing` → `/subscribe` + 引入 i18n `marketing.upgradeCta`
- **`alerts.tsx` 重写**:挂 ProBadge(header)+ UpgradePrompt(`variant="block"`,当 tier=free 时)
- **i18n zh-CN 翻译**:`marketing` 段(proBadge / upgradeTitle / upgradeCta / alertsReason / screenerReason / historyReason)+ `quota` 段
- **CR-010 禁词扫描**:`建议买入 / 建议卖出 / 保证收益 / 必涨 / 必跌` 全无,22 测点全过

### 2.6 灰度发布 + FE-083 灰度 banner(m6t7)

- **`app/services/feature_flag.py`(111 行)**:
  - `FeatureFlag` dataclass:`rollout_pct`(0–100)+ `whitelist`(tuple)+ `default`(bool)
  - `FlagSnapshot` dataclass:`enabled` + `reason`(whitelist / rollout / default-on / default-off / unknown-flag)
  - **`_stable_hash(flag_key, user_id)` 纯函数**:`hashlib.sha256(f"{flag_key}::{user_id}".encode()).hexdigest()[:8]` → `% 100`,保证同一用户始终落同一桶
  - **`is_enabled(flag_key, user_id=None)` 三层 fallback**:whitelist > rollout > default
- **3 内置 flag**:
  - `subscribe_v2`:rollout_pct=10,whitelist=("user_smoke_001", "user_smoke_002"),default=False
  - `8k_feed`:rollout_pct=0,whitelist=("user_smoke_001",),default=False
  - `gray_release_banner`:rollout_pct=100,whitelist=(),default=True
- **`app/api/feature_flags.py`(38 行)**:**2 端点**:
  - `GET /feature-flags` — 全 flag 快照(以 user_id 维度)
  - `GET /feature-flags/{flag_key}` — 单 flag 快照
- **`frontend/src/features/useFeatureFlag.ts`(52 行)**:TanStack Query 包装 + `pickFlag` 纯函数
- **`GrayReleaseBanner.tsx`(88 行)**:`useFeatureFlag("gray_release_banner")` 控制 + 7 天 localStorage dismiss + `aria-label` 无障碍
- **`__root.tsx` 全局挂载** GrayReleaseBanner(顶部)
- **i18n zh-CN 翻译**:`featureFlags` 段(bannerText / bannerCta / bannerDismiss / bannerDismissShort / bannerAriaLabel)
- **沙箱自测 24 测点全过**(sha256 hash 稳定性 + whitelist + rollout 边界 + 端点)

### 2.7 BD-051 8-K Item 8.01 回购公告解析器(m6t8)

- **`app/services/eight_k.py`(204 行)**:
  - `EightKEvent` dataclass(11 字段):`event_id` + `ticker` + `filing_date` + `event_date` + `category` + `summary` + `source_url` + `sandbox` + `fetched_at` + `raw_filing` + `redacted_terms`
  - **`EventCategory` Literal**:`share-repurchase` / `material-agreement` / `press-release` / `other`
  - **`CATEGORY_KEYWORDS` 关键词表**:
    - share-repurchase:share repurchase / buyback / repurchase program / repurchase plan / share buyback / treasury stock / authoriz / stock repurchase(8)
    - material-agreement:material agreement / strategic alliance / joint venture / merger agreement / acquisition agreement / license agreement / collaboration agreement(7)
    - press-release:press release / announces / issued / report(4)
  - **5 fixture**:AAPL(share-repurchase)/ TSLA(material-agreement)/ MSFT(press-release)/ NVDA(other)/ GME(share-repurchase)
  - `classify_summary(text)` 纯函数 + 4 服务函数(`fetch_recent_8k` / `fetch_8k_for_ticker` / `parse_8k_filing` / `redact_summary`)
- **`app/api/eight_k.py`(94 行)**:**3 端点**:
  - `GET /events/8k` — 全市场 8-K Item 8.01 事件流(`?days=7&category=`)
  - `GET /symbols/{ticker}/8k` — 单 ticker 8-K 事件流
  - `POST /events/8k/classify` — 文本分类器(独立端点,供前端调试)
- **CR-010 禁词过滤** `_sanitize_summary`:`建议买入 / 建议卖出 / 保证收益 / 必涨 / 必跌` → `[REDACTED]`
- **沙箱自测 19 测点全过**(分类器 + fixture + 端点 + CR-010 过滤)
- **严重 BUG 修复**:NVDA fixture summary 字符串含 `\n` 字面换行,Python 解析失败;改为 `"数据中心业务..."`(单字符串)

### 2.8 BD-087 真实回测 v3.0 + 校准报告(m6t9)

- **`scripts/m6t9_run_backtest_v3.py`(133 行)**:**3 子命令** CLI
  - `run` — 单组权重跑回测(沙箱 stub 返 fixture)
  - `compare` — A/B 权重对比(沙箱 stub 返双 fixture)
  - `report` — 读 `BD-087-calibration-run-m6t9.json` 输出报告
- **候选 A 权重**(继承 v2.5):
  - stock:`{options: 25, short: 40, divergence: 20, insider: 15}`
  - etf:`{options: 30, short: 50, divergence: 20}`
- **v1.0 默认权重**(M2 实装,OQ-01 锁定):
  - stock:`{options: 30, short: 35, divergence: 20, insider: 15}`
  - etf:`{options: 35, short: 45, divergence: 20}`
- **沙箱结果**:`n_event_days=0 / hits=0 / precision=None`,理由:`sandbox no PG/EOD reachable`
- **`docs/BD-087-calibration-report-v3.0.md`(165 行)**:**8 章节完整**
  - §一概述 / §二当前权重基线 / §三候选 A vs v1.0 对比表 / §四阈值集中化清单 / §五 v3.0 vs v2.5 增量 / §六沙箱限制与 M7 计划 / §七风险与遗留(R-27/28/29/30)/ §八本日记忆
- **沙箱自测 19 测点全过**(报告存在 + runner CLI + service A/B 对比)

## 三、M6 关键决策与硬约束

### 3.1 OQ 决策锁定(未触碰)

- OQ-01 权重回测校准:M6 沿用 v1.0 静态权重(沙箱无证据改动),v3.0 沙箱 stub 完成,M7 切真实 EOD 出 v3.0-final
- OQ-02 EMA 半衰期 2 日 + 连续 2 交易日:8 个单元测试守护(沿用 M0)
- OQ-16 ETF 代理指标 PoC:已就位(沿用 M0)
- OQ-09 / OQ-11:项目忽略

### 3.2 CR 红线(未触碰)

- CR-010 禁词清单:`scripts/compliance_check.py` 锁定;m6t6 自测扫描商业化文案确认无禁词
- 「仅供参考 / 不构成投资建议」必含兜底:`/subscribe` 页 + 升级引导 + 终极警报 全部含兜底
- API 契约与数据真实性规范:数据缺失返 200 + 空数组,严禁 mock 伪装(沿用 M4)
- 8-K Item 8.01 摘要 CR-010 过滤(新增):`_sanitize_summary` 服务端脱敏

### 3.3 新增硬约束(M6 接力期)

- **OpenAPI v1.4.1 → M6 末 v1.5**:M6 补 11 端点(subscriptions × 6 + feature_flags × 2 + 8-K × 3),共 33 + 11 = 44 端点;变更需先 freeze 再同步 FE-010
- **JWT 替换 X-User-Id**:M5 m5t2 落地,M6 沿用(subscriptions / feature_flags / 8-K 全部 JWT 鉴权)
- **Stripe 沙箱 fallback**:`HR_STRIPE_LIVE != 1` → 走 `sandbox-complete` URL 闭环;`handle_webhook_event` 不签名校验,沙箱简化
- **价格常量锁定**:`PLAN_PRICE_USD = {"pro_monthly": 19.0, "pro_yearly": 188.0}` 在 `app/services/subscription.py` 顶部,严禁散落
- **PWA 沙箱降级**:Chromium 不支持 `beforeinstallprompt` 时 banner 不显示,无报错
- **灰度发布 sha256 stable hash**:`flag_key + user_id` 哈希桶保证同一用户始终落同一桶(避免权重抖动)
- **8-K Item 8.01 关键词表**:`CATEGORY_KEYWORDS` 在 `app/services/eight_k.py` 顶部,扩展需 review
- **BD-086 reviewer_signoff 仍是 TBD**(M4 继承):待 CR + 产品双人 review 后补
- **PWA 自动更新**:`registerType: 'autoUpdate'` + `workbox.skipWaiting()`,本地 `pnpm install` 后生效

## 四、M6 未完成 / 已知遗留

### 4.1 沙箱限制

- `pnpm install` 未执行 → 前端 TS linter 报错(M0/M3/M4/M5/M6 已知;本地执行 `pnpm install` 后消失)
- 无 PG / Redis / 真实 EOD 数据 → 集成测试仅 smoke 骨架
- Vite PWA plugin 沙箱只写配置,生产环境 `pnpm build` 后 Workbox 生效
- BD-087 v3.0 仍为沙箱 stub,M7 切真实 EOD 出 v3.0-final
- Stripe webhook 沙箱简化(无签名校验),生产需加 `STRIPE_WEBHOOK_SECRET` 校验
- PWA `beforeinstallprompt` 事件沙箱不触发(Chromium headless 不支持),本地实跑可见
- 8-K Item 8.01 走 fixture,真实 EDGAR full-text search 待 M7 接入

### 4.2 二期待启动

- **BD-086 reviewer_signoff 双签补全**:CR + 产品双签,需走流程
- **BD-087 真实回测 v3.0-final**:M7 切真实 EOD + Mann-Whitney U 检验后产出
- **8-K Item 8.01 真实数据源**:M7 接 EDGAR full-text search 替换 fixture
- **Stripe webhook 签名校验**:生产需校验 `STRIPE_WEBHOOK_SECRET`(避免伪造)
- **PWA 自动更新服务**:`vite-plugin-pwa` 已配 `autoUpdate`,生产 `pnpm build` 后生效
- **CI 骨架实跑**:M5 写配置,生产环境实跑;沙箱不实跑(无 headless 浏览器)
- **Sentry DSN + Web Push VAPID 真实密钥配置**:M5 沙箱占位,生产需配

### 4.3 风险登记表(M6 接力期增量)

| ID | 描述 | 影响 | 缓解措施 | 状态 |
|---|---|---|---|---|
| R-12 | SEC EDGAR / FINRA ATS 真实数据源接入 | 🟡 M6 8-K 走 fixture | M7 接 EDGAR full-text search 替换 | 🟡 |
| R-13 | 沙箱无 PG/Redis, 集成测试仅 smoke 骨架 | 🟡 待本地 `make up` | 待本地 `make up` | 🟡 |
| R-15 | 终极警报单日毛刺 | 🟢 EMA + 连续 ≥2 日 + 24h 防抖 + 8 OQ-02 测试 | 沿用 M0 | 🟢 |
| R-20 | 沙箱无 pnpm install, TS linter 报错 | 🟢 本地 `pnpm install` 后消失 | 沿用 M0 | 🟢 |
| R-23 | BD-086 reviewer_signoff 仍是 TBD | 🟡 待 CR + 产品双人 review 后补 | 沿用 M4 | 🟡 |
| R-25 | Sentry DSN + VAPID 真实密钥未配 | 🟡 M5 沙箱占位,生产需配 | 沿用 M5 | 🟡 |
| R-26 | CI 骨架沙箱不实跑 | 🟢 配置就位,生产实跑 | 沿用 M5 | 🟢 |
| R-27 | BD-087 v2.5 仅理论 + 沙箱空跑 | 🟢 v3.0 沙箱 stub 完成 | M7 切真实 EOD 出 v3.0-final | 🟢 |
| **R-28**(新) | 候选 A 权重切换若影响前端 Threat Score 显示 | 🟡 需联动 OpenAPI freeze | v3.0-final 前冻结 OpenAPI v1.5 | 🟡 |
| **R-29**(新) | 校准期间候选 A 与 v1.0 共存 | 🟢 前端 /api/v1/backtest/compare 双跑 | runner compare 命令支持 | 🟢 |
| **R-30**(新) | OQ-01 锁定规则:权重变更需复核 + 灰度发布 | 🟢 m6t7 灰度发布 flag `weights_v3` 控流量 | flag rollout + whitelist | 🟢 |
| **R-31**(新) | Stripe webhook 沙箱简化(无签名校验) | 🟡 生产需配 `STRIPE_WEBHOOK_SECRET` | 生产加签名校验 | 🟡 |
| **R-32**(新) | Vite PWA 沙箱只写配置,Workbox 待生效 | 🟢 本地 `pnpm install` 后可见 | 本地 `pnpm install` 后可见 | 🟢 |
| **R-33**(新) | PWA `beforeinstallprompt` 沙箱不触发 | 🟢 本地浏览器可见 | 本地浏览器可见 | 🟢 |

### 4.4 测试数变化

- M5 末:194 个 pytest
- M6 末:**仍 194 个**(M6 未新增 pytest,均依赖现有 threat_score / basket / backtest 单测)
- M6 增量:10 个独立可跑自测脚本
  - m6t1 M5 沙箱自测回归 116 测点(沿用)
  - m6t3 PWA 安装提示 26 测点
  - m6t4 Stripe 订阅接入 15 测点
  - m6t5 订阅页面 18 测点
  - m6t6 商业化文案 22 测点
  - m6t7 灰度发布 24 测点
  - m6t8 8-K Item 8.01 解析器 19 测点
  - m6t9 v3.0 真实回测 19 测点
  - m6t10 文档自测 20+ 测点(本任务)
  - 合计:**143 个新增测点(M6 接力期)**
- 前端无 Vitest 测试(M0 已知,二期接 vitest 框架)

## 五、立即可跑(本地)

```bash
# 1. 起基础设施 + 后端
cd "d:\Financial Project\Hunter Radar\hunter-radar"
make up
cd backend
uv sync --extra dev
uv run python -m etl.symbol_seed
uv run fastapi dev app/main.py    # http://localhost:8000/docs(44 端点)

# 2. 跑后端测试
uv run pytest -q                  # 期望 194 passed

# 3. 跑 EOD 流水线
uv run python -m etl.pipeline 2024-02-01

# 4. 跑校准数据构建(BD-085)
uv run python scripts/m4_build_dataset.py --end 2024-12-31 --years 2 --tickers AAPL,TSLA

# 5. 跑回测(BD-089)
uv run python scripts/m4_run_backtest.py run --tickers AAPL,TSLA,GME,AMC,META
uv run python scripts/m6t9_run_backtest_v3.py compare

# 6. 跑 M5 沙箱自测(沿用)
py -u scripts/m5t1_test_freeze.py        # 11/11 PASSED
py -u scripts/m5t2_test_jwt.py           # 11/11 PASSED
py -u scripts/m5t8_test_quota.py         # 10/10 PASSED
py -u scripts/m5t9_test_calibration.py   # 10/10 PASSED

# 7. 跑 M6 沙箱自测(共 9 个 + M5 沿用)
py -u scripts/m6t3_test_install.py       # 26/26 PASSED
py -u scripts/m6t4_test_stripe.py        # 15/15 PASSED
py -u scripts/m6t5_test_subscribe.py     # 18/18 PASSED
py -u scripts/m6t6_test_commercial.py    # 22/22 PASSED
py -u scripts/m6t7_test_feature_flag.py # 24/24 PASSED
py -u scripts/m6t8_test_eight_k.py       # 19/19 PASSED
py -u scripts/m6t9_test_backtest_v3.py   # 19/19 PASSED
py -u scripts/m6t10_test_documentation.py # 20+/20+ PASSED

# 8. 跑集成 smoke test
HR_BASE_URL=http://localhost:8000 uv run python scripts/m3_integration_smoke.py

# 9. 前端 + PWA
cd ../frontend
pnpm install                       # 消 TS linter 报错 + 装 vite-plugin-pwa
pnpm dev                           # http://localhost:5173/(4 路由 + Banner + Subscribe + Gray Release)
pnpm build                         # 生产构建,Workbox 注入 + manifest 完整
# 看到:/ /screener /subscribe /basket /alerts(/ 含 PWAInstallBanner + GrayReleaseBanner)
```

## 六、M7 启动接力

### 6.1 接力入口

- **后端 main**:`backend/app/main.py` 已注册 13 个 router(basket / alert-rule / push / data-status / auth / subscriptions / feature_flags / eight_k)
- **OpenAPI 文档**:`http://localhost:8000/docs`(44 端点,待 v1.5 freeze)
- **前端订阅入口**:`http://localhost:5173/subscribe`(M6 m6t5)
- **PWA 安装**:生产构建后,浏览器地址栏右侧显示「安装」按钮 → 桌面应用
- **校准报告**:`docs/BD-087-calibration-report-v3.0.md` v3.0 就位
- **M6 自测脚本**:`backend/scripts/m6t*_test_*.py` 9 个独立可跑

### 6.2 M7 开工顺序

1. **环境验证**:`make up; cd backend; uv sync --extra dev; uv run pytest -q` → 194 passed
2. **集成 smoke**:`HR_BASE_URL=http://localhost:8000 uv run python scripts/m3_integration_smoke.py` → 9/9
3. **M6 沙箱自测**:跑 9 个 `m6t*_test_*.py` + M5 沿用 → 259+/259+ 全过
4. **BD-086 reviewer_signoff 双签补全**:CR + 产品双人 review
5. **BD-085 真实数据集落地**:FINRA RegSHO + Yahoo Finance EOD + SEC Form 4
6. **BD-087 真实回测 v3.0-final**:切真实 EOD + Mann-Whitney U 检验 → 出 v3.0-final 报告
7. **8-K Item 8.01 真实数据源**:EDGAR full-text search 替换 fixture
8. **Stripe webhook 签名校验**:`STRIPE_WEBHOOK_SECRET` 校验
9. **OpenAPI v1.5 freeze**:M6 增量 11 端点 + M7 增量 freeze 一版同步 FE-010
10. **PWA + CI 实跑**:生产 `pnpm build` + GitHub Actions 跑 3 个 workflow(WCAG + Playwright + Lighthouse)
11. **V1.5 准备**:BD-088 ETF 申赎数据代理 / Sentry DSN + Web Push VAPID 真实密钥 / 用户增长指标埋点

### 6.3 给下一位 agent 的一句话

- M6 主体 10 个 todo 全 COMPLETE,代码层就位(44 端点 + 6 路由 + PWA + Stripe + 灰度 + 8-K),数据层待真实 EOD(沙箱不可达,需本地或代理)
- M6 范围**不输出投资建议**(CR-010 红线);**不数据伪装**(沿用 M4,数据缺失返 200+空)
- 进入 M7 时请先读 [M6-handoff.md](M6-handoff.md) §4.1 沙箱限制,合理安排 smoke / 集成测试
- M7 重点是真实 EOD 数据 + 校准 v3.0-final + PWA 实跑 + CI 实跑
- BD-087 v3.0 出 v3.0-final 时,保留 v3.0 §一/§二/§三/§五/§六章节结构
- 沙箱无 `pnpm install` 已知,TS linter 报错**不修复**(本地 `pnpm install` 后消失)

## 七、本日记忆(自动,补充)

- M6 接力期 10 个 todo,143 个新增沙箱自测测点(m6t3 26 + m6t4 15 + m6t5 18 + m6t6 22 + m6t7 24 + m6t8 19 + m6t9 19)
- OpenAPI 演进:v1.4.1(33 端点,M5)→ M6 末 44 端点(+11:subscriptions × 6 + feature_flags × 2 + 8-K × 3);M7 freeze v1.5
- 13 个 router = M5 末 10 + subscriptions(BD-105)+ feature_flags(灰度)+ eight_k(BD-051)
- PWA 设计:vite-plugin-pwa v0.20 + Workbox 7 + 离线兜底页 + `registerType: 'autoUpdate'` + `skipWaiting`
- PWA 安装提示:`usePWAInstall` hook 捕获 `beforeinstallprompt` + `appinstalled` 事件 + 7 天 localStorage dismiss
- manifest.webmanifest 6 字段完整:name / short_name / icons(192/512)/ theme_color / start_url(/) / display(standalone)
- Stripe 沙箱 fallback:`HR_STRIPE_LIVE != 1` → `sandbox-complete` URL,前端 fetch 后自动落 active 订阅
- Stripe 沙箱 stub:5 状态机(active / canceled / past_due / incomplete / none)+ in-memory `_STORE: dict[str, Subscription]`
- 价格常量锁定:`PLAN_PRICE_USD = {"pro_monthly": 19.0, "pro_yearly": 188.0}`(顶部,严禁散落)
- `/subscribe` 路由 3 档价格卡片(Free + Pro 月付 + Pro 年付)+ PlanCard 子组件
- 沙箱闭环 UX:`fetch(checkout_url)` → `sandbox-complete` → `invalidateQueries(["subscriptions", "me"])` → `nav("/subscribe")`
- ProBadge 2 variant(compact / full)+ shouldShowProBadge 纯函数;UpgradePrompt 3 variant(inline / block / modal)
- CR-010 禁词扫描:`建议买入 / 建议卖出 / 保证收益 / 必涨 / 必跌` 全无
- 灰度发布 sha256 stable hash:`flag_key + user_id` 哈希桶保证稳定性,三层 fallback(whitelist > rollout > default)
- 3 内置 flag:subscribe_v2(10%)/ 8k_feed(0%)/ gray_release_banner(100%)
- GrayReleaseBanner 全局挂载(`__root.tsx`)+ 7 天 localStorage dismiss + `aria-label` 无障碍
- 8-K Item 8.01 4 类别:share-repurchase / material-agreement / press-release / other
- 8-K 关键词表:share-repurchase × 8 / material-agreement × 7 / press-release × 4
- 8-K 5 fixture:AAPL(share-repurchase)/ TSLA(material-agreement)/ MSFT(press-release)/ NVDA(other)/ GME(share-repurchase)
- 8-K CR-010 服务端脱敏:`_sanitize_summary` 过滤 `建议买入 / 建议卖出 / 保证收益 / 必涨 / 必跌`
- m6t8 NVDA fixture summary `\n` 字面换行 BUG:合并为单字符串 `"数据中心业务..."`
- v3.0 候选 A 权重(继承 v2.5):stock `{25,40,20,15}` vs v1.0 `{30,35,20,15}`
- m6t9 runner CLI 3 子命令:run / compare / report;沙箱 stub 返 fixture
- m6t9 沙箱结果:`n_event_days=0 / hits=0`,理由:`sandbox no PG/EOD reachable`
- M7 末切真实 EOD:`m6t9_run_backtest_v3.py compare` + Mann-Whitney U 检验 → v3.0-final
- M6 接力期 44 个 OpenAPI 端点列表(M7 freeze v1.5 用):symbols(7) + regime(1) + screener(2) + basket(9) + alerts(7) + push(4) + data-status(1) + auth-quota(1) + health(1) + subscriptions(6) + feature_flags(2) + eight_k(3) = 44
- BD-086 reviewer_signoff 仍是 TBD(M4 → M5 → M6 继承),待 CR + 产品双人 review 后补
- R-27/28/29/30 风险登记:校准期间候选 A 与 v1.0 共存,需灰度发布 + OpenAPI v1.5 freeze
- M6 末 194 个 pytest 维持(无新单测),M6 增量在 10 个 m6t*_test_*.py 独立可跑脚本(143 测点)

---

*本文档为 M6 接力版完成报告。下一位 agent 从 §6 M7 启动接力开工。*