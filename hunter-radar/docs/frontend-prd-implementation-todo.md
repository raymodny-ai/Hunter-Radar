# Hunter Radar Frontend PRD Implementation TODO

> **基于**: Hunter-Radar-Frontend-PRD.md (V1.0, 2026-08-01)
> **对齐**: docs/frontend-v2.0-todo.md (FE-100~FE-157)
> **状态标注**: ✅ 已完成 | 🔄 需重构/增强 | 🆕 全新开发
> **生成时间**: 2026-06-15
> **实施进度**: Phase 1–5 全部完成 ✅（每阶段 tsc --noEmit 零错误 + vite build 成功；最终主 bundle 126.11KB gzip，符合 PRD §7.1 < 200KB 预算）

---

## Phase 1: Dashboard + Symbol Detail + Auth (核心监控循环)

### P1-01 Dashboard 重写 — 左侧排名面板
- **PRD**: §3.1 (Left Panel 320px: Threat Score Ranking Top 20 + Module Signal Lights)
- **优先级**: P0
- **类型**: 🔄 (现有 index.tsx 仅 Top10 网格卡片，需重构为排名列表+sparkline+badge)
- **对应旧ID**: FE-100(✅布局骨架已有), FE-105(✅Watchlist面板已有)
- **依赖**: P1-04 (uiStore)
- **验收标准**:
  - 左面板 320px 固定宽度，Top 20 按分数降序
  - 每行: ticker + 分数色阶 + lifecycle badge + 7d sparkline
  - 支持按模块分排序、按 lifecycle 筛选
  - 点击行导航至 `/symbol/$ticker`
  - hover 触发 prefetch (useSymbolAutoWarmup 已有 ✅)

### P1-02 Dashboard 重写 — 主区域 Signal Radar + Alert Feed
- **PRD**: §3.1 (Main Area: Signal Radar 4-axis + Ultimate Alert Feed + Data Freshness)
- **优先级**: P0
- **类型**: 🔄 (SignalRadar 组件已有 ✅，需集成为 Dashboard 主图 + 新增 Alert Feed 时间线)
- **对应旧ID**: FE-118(✅ 4D雷达图组件已有), FE-106(🔄 Alerts面板需重构为Feed卡片)
- **依赖**: P1-01
- **验收标准**:
  - Signal Radar: hover 高亮排名列表对应标的，click 钻入详情
  - Ultimate Alert Feed: 30s 轮询，时间线卡片展开显示模块分解
  - Data Freshness Status: 对接 `/data-status` (useDataStatus ✅)
  - Loading: skeleton; Empty: "No signals today"; Error: toast + retry

### P1-03 Symbol Detail 增强
- **PRD**: §3.2 (sticky sub-nav, period toggle, chart sync, add to basket, subscribe gate)
- **优先级**: P0
- **类型**: 🔄 (7大图表已有 ✅，需增加 sticky nav + 周期切换 + 篮子按钮)
- **对应旧ID**: FE-117~FE-124(✅ 图表组件全部已有), FE-125(✅ useChartSync已有)
- **依赖**: P1-04, P1-05
- **验收标准**:
  - Sticky sub-nav: 各 section 锚点滚动
  - Period toggle: 30d / 60d / 90d / YTD (uiStore.chartPeriod)
  - Add to Basket 按钮 (header)
  - Subscribe gate: free 7天历史 / pro 全量 (ProBadge ✅, UpgradePrompt ✅)
  - Responsive: desktop 2列, tablet <1024px 单列

### P1-04 uiStore 扩展 (PRD §6.2)
- **PRD**: §6.2 (theme, sidebarCollapsed, chartPeriod, activeModules, pushPermissionState, pwaInstallPrompt)
- **优先级**: P0
- **类型**: 🔄 (现有 uiStore 缺少 chartPeriod/theme/pushPermissionState)
- **对应旧ID**: FE-108(🔄)
- **依赖**: 无
- **验收标准**:
  - 新增字段: `chartPeriod: '30d'|'60d'|'90d'|'ytd'`, `theme: 'dark'` (固定dark)
  - localStorage 持久化 chartPeriod

### P1-05 Auth 层 (PRD §5.1)
- **PRD**: §5.1 (JWT Bearer, silent refresh, 401 redirect, rate limit header)
- **优先级**: P0
- **类型**: 🆕 (现有 api.ts 无 auth header 处理)
- **对应旧ID**: 无 (新增)
- **依赖**: 无
- **验收标准**:
  - `lib/auth.ts`: token 存取 (localStorage), getAuthHeader()
  - api.ts request() 注入 Authorization header
  - 401 全局拦截 → 清除 token + toast
  - X-RateLimit-Remaining < 10% 时显示 quota warning
  - 向后兼容: 无 token 时不注入 header (sandbox 模式)

### P1-06 API 层补全 (PRD §5.2 缺失端点)
- **PRD**: §5.2 (/alerts/ultimate, /quota/usage, /llm/summary)
- **优先级**: P0
- **类型**: 🔄 (api.ts 已有 30+ 端点，需补 ultimate alerts 全局 feed)
- **对应旧ID**: FE-115(🔄)
- **依赖**: 无
- **验收标准**:
  - 新增 `getUltimateAlertsFeed()`: 全市场终极警报 (Dashboard feed 用)
  - 新增 `getLlmSummary(ticker)`: LLM 摘要 (Detail 页用)
  - 保持现有端点类型定义不变

### P1-V Phase 1 验证
- `npx tsc --noEmit` 零错误
- `npx vite build` 成功

---

## Phase 2: Screener + Alerts + Web Push (发现与通知)

### P2-01 Screener 筛选面板
- **PRD**: §3.3 (Filter Panel: score range slider, module toggles, lifecycle multi-select, regime filter, date picker)
- **优先级**: P0
- **类型**: 🆕 (现有 screener 无筛选面板)
- **对应旧ID**: FE-127(✅虚拟列表已有), FE-128(✅排序已有), FE-129(✅top100已有)
- **依赖**: 无
- **验收标准**:
  - 左侧可折叠筛选面板
  - Threat Score range slider (0-100)
  - Module toggles (4维)
  - Lifecycle multi-select
  - 筛选结果实时更新 (前端过滤)

### P2-02 Screener 分页 + 批量操作
- **PRD**: §3.3 (paginated 25/50/100, bulk actions: Add to Basket, Export CSV)
- **优先级**: P1
- **类型**: 🆕
- **对应旧ID**: 无
- **依赖**: P2-01
- **验收标准**:
  - 分页控件 25/50/100
  - 行选择 checkbox + 批量 Add to Basket
  - Export CSV 下载
  - Quota exceeded: inline upgrade CTA

### P2-03 Alerts 三 Tab 重构
- **PRD**: §3.4 (Tabs: Active Alerts / History / Settings)
- **优先级**: P0
- **类型**: 🔄 (现有 alerts.tsx 有规则CRUD，需重构为三Tab + Alert Card 设计)
- **对应旧ID**: FE-140(🔄), FE-141(✅ AlertRuleForm已有), FE-142(✅ useWebPush已有)
- **依赖**: 无
- **验收标准**:
  - Tab 1 Active Alerts: 按日期分组，Alert Card (§3.4 布局)
  - Tab 2 History: 分页历史 + outcome 注释
  - Tab 3 Settings: push 偏好 + 阈值配置
  - Alert Card: 🔴 ticker + score + consecutive days + modules + regime + actions

### P2-V Phase 2 验证
- `npx tsc --noEmit` 零错误
- `npx vite build` 成功

---

## Phase 3: Basket + Regime + Subscription (组合与变现)

### P3-01 Basket 增强
- **PRD**: §3.5 (aggregate danger score, snapshot history, export, rename)
- **优先级**: P1
- **类型**: 🔄 (现有 basket.tsx 功能完整，需增加聚合分+快照历史)
- **对应旧ID**: FE-133(✅), FE-134(✅ SparkRadar), FE-135(✅ Histogram), FE-136(✅ DangerCluster)
- **依赖**: 无
- **验收标准**:
  - Header: 成员数 + 聚合危险分 (成员均值/最大值)
  - Snapshot History: 日对比折线图 (ThreatHistoryChart 复用)
  - Export CSV
  - Rename basket (updateBasket API 已有 ✅)

### P3-02 Regime 增强
- **PRD**: §3.6 (transition annotations, historical regime table)
- **优先级**: P1
- **类型**: 🔄 (现有 regime.tsx 有门控灯+时间轴，需增加注释+历史表格)
- **对应旧ID**: FE-130(✅), FE-131(✅), FE-132(✅)
- **依赖**: 无
- **验收标准**:
  - Regime transition annotations (时间轴上 event markers)
  - Current Regime card: duration + key drivers
  - Historical regime table: 每段时期平均 threat score

### P3-03 Subscribe 定价页
- **PRD**: §3.7 (feature comparison table, Stripe checkout, usage meter)
- **优先级**: P1
- **类型**: 🆕 (现有 subscribe.tsx 仅为重定向 stub)
- **对应旧ID**: 无
- **依赖**: P1-05 (auth)
- **验收标准**:
  - Free vs Pro 功能对比表 (PRD §3.7 tiers)
  - "Upgrade" → Stripe Checkout redirect (sandbox stub)
  - Current plan indicator + usage meter (useApiQuota ✅ + QuotaDTO ✅)
  - Success/failure callback 处理

### P3-V Phase 3 验证
- `npx tsc --noEmit` 零错误
- `npx vite build` 成功

---

## Phase 4: Admin + Logs + Feature Flags (运营工具)

### P4-01 Admin Tab 化重构
- **PRD**: §3.8 (Tabs: ETL Controls / Feature Flags / Users & Quota / Audit Log / Attribution)
- **优先级**: P2
- **类型**: 🔄 (现有 admin.tsx 仅 ETL+Backtest 按钮)
- **对应旧ID**: FE-152(🔄)
- **依赖**: 无
- **验收标准**:
  - Tab 结构 5 个子面板
  - ETL Controls: 触发/状态/重试 (现有 ✅ + 增强)
  - Feature Flags: 开关列表 + 灰度百分比 (getAllFeatureFlags API ✅)
  - Audit Log: 可搜索操作日志 (后端 /logs/file 复用)
  - Attribution: 埋点事件仪表板 (reportAnalytics API ✅)

### P4-02 Logs 页面 (已完成验证)
- **PRD**: §3.9 (SSE stream, level filter, search highlight, pause/resume)
- **优先级**: P2
- **类型**: ✅ (logs.tsx 已完整实现: SSE + 级别过滤 + 搜索 + 暂停/继续 + 下载)
- **对应旧ID**: FE-160(✅)
- **验收标准**: 已满足 PRD 全部要求

### P4-V Phase 4 验证
- `npx tsc --noEmit` 零错误
- `npx vite build` 成功

---

## Phase 5: PWA + i18n + Performance (生产打磨)

### P5-01 i18n en-US locale ✅
- **PRD**: §1.3 (zh-CN primary, en-US secondary)
- **优先级**: P1
- **类型**: 🆕 (现有仅 zh-CN.json)
- **对应旧ID**: 无
- **依赖**: 无
- **验收标准**:
  - `src/i18n/en-US.json` 完整翻译 ✅（551 行全量对齐 zh-CN key 结构）
  - i18n/index.ts 注册 en-US + 语言切换器 ✅（TopNav EN/中 切换，uiStore.language 持久化）
  - 所有新页面文案走 i18n key ✅

### P5-02 PWA 离线增强 ✅
- **PRD**: §7.3 (cache-first shell, network-first API, offline banner, install prompt)
- **优先级**: P1
- **类型**: 🔄 (vite-plugin-pwa 已配置 ✅, PWAInstallBanner ✅, usePWAInstall ✅)
- **对应旧ID**: FE-113(✅), FE-145(✅)
- **依赖**: 无
- **验收标准**:
  - 离线 banner: navigator.onLine 监听 + 提示 ✅（OfflineBanner 集成至 __root banners 首位）
  - Workbox runtimeCaching: API network-first 策略 ✅
  - Mutation 队列: TanStack Query v5 onlineManager 离线暂停/恢复重放 ✅

### P5-03 Performance 优化 ✅
- **PRD**: §7.1 (LCP < 2.5s, bundle < 200KB gzip initial, route code-split)
- **优先级**: P1
- **类型**: 🔄 (echartsLargeMode ✅, usePerformanceProbe ✅)
- **对应旧ID**: FE-126(✅), FE-153(✅), FE-156(✅)
- **依赖**: 无
- **验收标准**:
  - ECharts 按需引入 (已有 echarts-setup.ts) ✅
  - 路由级 code-split (TanStack Router lazy) ✅（9 路由 stub + .lazy.tsx 双文件模式，echarts 224.62KB gzip 延迟加载）
  - 图表 aria-label 全覆盖 (FE-147 ✅ 部分已有) ✅
  - 初始 bundle 126.11KB gzip < 200KB 预算 ✅

### P5-V Phase 5 最终验证 ✅
- `npx tsc --noEmit` 零错误 ✅
- `npx vite build` 成功 ✅（3.86s）
- 全页面键盘导航可达 ✅

---

## 已完成资产盘点 (无需重复开发)

| 资产 | 状态 | 文件 |
|------|------|------|
| AppShell 四区布局 | ✅ | components/layout/AppShell.tsx |
| TopNav + SearchBox | ✅ | components/layout/TopNav.tsx, SearchBox.tsx |
| LeftToolbar + RightSidebar | ✅ | components/layout/ |
| 10 个 ECharts 图表组件 | ✅ | components/charts/ |
| 7 个雷达组件 | ✅ | components/radar/ |
| 16 个 feature hooks | ✅ | features/ |
| api.ts 30+ 端点 | ✅ | lib/api.ts |
| hunter-dark 主题 | ✅ | lib/theme/hunter-dark.ts |
| Skeleton 组件 | ✅ | components/common/Skeleton.tsx |
| Logs 页面 | ✅ | routes/logs.tsx |
| useWebPush | ✅ | features/useWebPush.ts |
| AlertRuleForm | ✅ | components/common/AlertRuleForm.tsx |

---

## 关键路径

```
P1-04 (uiStore) ──┬── P1-01 (Dashboard 排名)
                  └── P1-03 (Detail 周期切换)
P1-05 (Auth) ──────── P3-03 (Subscribe)
P1-06 (API补全) ──┬── P1-02 (Alert Feed)
                  └── P1-03 (LLM Summary)
P2-01 (筛选) ──── P2-02 (分页+批量)
```
