# Hunter Radar 前端 V2.0 — 开发 TODO List

> **版本**:V2.0-frontend-todo(基于 PRD V2.0)
> 适用范围:Hunter Radar 前端 PRD 撰写.md(八大章节全覆盖)
> 配套文档:`PROJECT-OVERVIEW.md`(已实现组件/Hooks/API 端点)、`Hunter-Radar-v1.4-implementation-todo.md`(FE-001~FE-082 已完成)
> ID 编号:FE-100 起,避免与 V1.4 已有 ID(FE-001~FE-082)冲突
> 优先级:P0 阻断级 / P1 主线级 / P2 增强级
> 工作量单位:人天(d)
> 状态标注:🆕 新增 / 🔄 重构增强已有代码
> 生成时间:2026-06-15

---

## 1. 项目总览

### 1.1 交付目标

基于 PRD 八大章节,将现有 V1.x 前端从"基础数据展示"升级为"TradingView 级专业量化分析平台":
- **四区模块化拓扑布局**(顶部导航 + 左侧工具栏 + 主画布 + 右侧边栏)
- **六大核心页面**全面落地(Screener / 标的详情 7 图表 / 宏观环境 / 自选篮子雷达 / 预警中心 / LLM 智能助手)
- **ECharts 深度图表矩阵**(跨图表联动、Canvas 降级、暗黑主题色彩语义)
- **PWA + 响应式断点**(桌面三栏 → 平板折叠 → 移动端单列)
- **合规与无障碍 WCAG AA**(aria 属性、免责 Tooltip、屏幕阅读器)

### 1.2 现有资产盘点(可复用)

| 类别 | 已有 | 文件位置 |
|------|------|----------|
| 路由 | 5 个(`/`, `/screener`, `/symbol/$ticker`, `/basket`, `/alerts`) | `routes/` |
| 通用组件 | 9 个(DataStatusBanner, Disclaimer, GrayReleaseBanner, LlmPanel, LogPanel, ProBadge, PWAInstallBanner, QuotaBanner, UpgradePrompt) | `components/common/` |
| 雷达组件 | 6 个(ThreatScoreGauge, ModuleSignalLight, SignalLifecycleBadge, ThreatHistoryChart, UltimateAlertOverlay, RegimeBanner) | `components/radar/` |
| Hooks | 8 个(useApiQuota, useDataStatus, useFeatureFlag, usePrefersReducedMotion, usePWAInstall, useSignalLifecycle, useThreatHistory, useUltimateAlert) | `features/` |
| API 客户端 | `lib/api.ts`(20 个端点封装) | `lib/` |
| 基础设施 | i18n, Sentry, TanStack Query, Zustand | `lib/`, `i18n/` |

### 1.3 团队编制建议

| 角色 | 人数 | 备注 |
|------|------|------|
| 前端工程师 | 2 人 | React + TS + ECharts,需熟悉金融图表渲染 |
| UI/UX 设计师 | 0.5 人 | 兼任,负责暗黑主题色谱定义 + 响应式断点设计稿 |
| QA 工程师 | 0.5 人 | 兼任,负责 WCAG 审计 + E2E 测试 |

---

## 2. 里程碑甘特视图

```
里程碑                     周期     累计    W1   W2   W3   W4   W5   W6   W7   W8
M1 基座架构与状态层       2w      2w     ██   ██
M2 核心图表渲染           3w      5w              ███  ███  ███
M3 数据大屏与智能编排     2w      7w                          ███  ███
M4 边缘系统与体验精雕     1w      8w                                    ██
```

---

## 3. 详细 TODO List(按里程碑分组)

### 3.1 M1:基座架构与状态层(第 1-2 周)

> 目标:搭建四区布局骨架,注册全局状态,打通 API 类型层,验证 PWA HTTPS。

#### 3.1.1 页面拓扑与全局导航

| ID | 标题 | PRD | 优先 | 工作量 | 类型 | 依赖 | 验收标准 |
|----|------|-----|------|--------|------|------|----------|
| FE-100 | 四区 Grid 布局骨架(顶部 + 左侧 + 主画布 + 右侧) | §2 | P0 | 2d | 🆕 | — | CSS Grid 四区划分,`xl` 断点下三栏可见;`<Outlet />` 嵌入主画布区;骨架屏占位 |
| FE-101 | 顶部全局导航栏重构(搜索框 + 状态灯带 + Logo) | §2.1 | P0 | 2d | 🔄 | FE-100 | 搜索框 300ms debounce 调用 `/symbols/lookup`;右侧状态灯带对接 `/data-status` 端点(绿/琥珀/红三色) |
| FE-102 | 全局搜索框 Autocomplete 下拉(模糊匹配 + 搜索历史) | §2.1 | P0 | 1.5d | 🆕 | FE-101 | 输入 `QQ` 显示 `QQQ (Invesco QQQ Trust) [ETF]`;搜索历史 localStorage 持久化,最多 10 条,支持清空 |
| FE-103 | 左侧垂直工具栏(Analyzer Lenses 图标面板) | §2.2 | P0 | 1.5d | 🆕 | FE-100 | 每个图标切换一层可视化数据(期权/做空/背离/内部人);点击在主画布叠加/隐藏对应指标层 |
| FE-104 | 右侧功能侧边栏(Tabs 抽屉:自选 + 预警流 + LLM) | §2.4 | P0 | 1.5d | 🆕 | FE-100 | 三 Tab 切换:Watchlist / Alerts / AI Copilot;Tab 状态 Zustand 持久化 |
| FE-105 | 右侧边栏 — Watchlist 微缩面板 | §2.4 | P1 | 1d | 🆕 | FE-104, FE-117 | 紧凑列表展示篮子成员的最新 Threat Score + 红绿灯状态;点击跳转详情页 |
| FE-106 | 右侧边栏 — Alerts Center 预警流面板 | §2.4 | P1 | 1d | 🆕 | FE-104, FE-131 | 时间倒序滚动;点击预警条目主画布自动切换到对应标的 |
| FE-107 | 左侧工具栏响应式降级(移动端底部悬浮抽屉) | §2.2 | P1 | 1d | 🆕 | FE-103, FE-143 | `< 768px` 时自动下沉为底部 Bottom Sheet;触摸手势支持上滑展开 |

#### 3.1.2 状态管理与基础设施

| ID | 标题 | PRD | 优先 | 工作量 | 类型 | 依赖 | 验收标准 |
|----|------|-----|------|--------|------|------|----------|
| FE-108 | Zustand UI 状态 Store 重构(主题 + 布局 + 工具栏) | §5.1 | P0 | 1d | 🔄 | — | Store 包含:darkMode(固定 true)、leftToolbarCollapsed、rightSidebarTab、widgetLayout;localStorage 持久化 |
| FE-109 | TanStack Query 全局 staleTime 优化(EOD 模式) | §5.1 | P0 | 0.5d | 🔄 | — | 全局 staleTime ≥ 1h;EOD 数据无需高频轮询;screener/threat 等查询缓存命中率 > 80% |
| FE-110 | 骨架屏组件(SkeletonChart / SkeletonTable / SkeletonCard) | §5.1 | P0 | 1d | 🆕 | — | 三种骨架变体;微弱呼吸动画;尊重 `prefers-reduced-motion`;替代全屏 Spinner |
| FE-111 | ECharts 暗黑主题注册(registerTheme + 全局色谱) | §4.1 | P0 | 1d | 🆕 | — | 背景 `#131722`;网格线 `#363A45`;多头信号 `#2196F3`;威胁红 `#FF5252` / `#E040FB`;通过 `echarts.registerTheme('hunter-dark', ...)` 全局注册 |
| FE-112 | openapi-typescript 类型生成集成(CI 阻断) | §6 | P0 | 0.5d | 🔄 | — | `pnpm run openapi:gen` 生成 `api-types.d.ts`;CI 阶段 tsc 编译零错误 |
| FE-113 | PWA HTTPS 本地证书配置(mkcert + LNA) | §5.2 | P0 | 1d | 🔄 | — | 本地 dev 环境 `https://localhost:5173`;Service Worker 注册成功;解决局域网 IP 访问时 SW 被阻断问题 |
| FE-114 | Zustand Widget 布局云端同步(双重持久化) | §5.2 | P1 | 1.5d | 🆕 | FE-108 | 布局变更 300ms 防抖后 POST 到后端用户配置表;断网时回退 localStorage |

#### 3.1.3 API 层补全

| ID | 标题 | PRD | 优先 | 工作量 | 类型 | 依赖 | 验收标准 |
|----|------|-----|------|--------|------|------|----------|
| FE-115 | `api.ts` 新增 attribution / regime_timeline / alerts CRUD / push / events 8K 接口 | §6 | P0 | 1d | 🔄 | — | 补齐 PRD 映射表中 18 个端点;TypeScript 类型完备;与 openapi-typescript 生成类型一致 |
| FE-116 | `useLookup` Hook(搜索防抖 + React Query 缓存) | §2.1 | P0 | 0.5d | 🆕 | FE-102 | 300ms debounce;queryKey `['lookup', q]`;staleTime 10min;返回 `{ ticker, name, type, exchange }[]` |

---

### 3.2 M2:核心图表渲染(第 3-5 周)

> 目标:集中攻坚标的详情页 7 大图表组件;实现跨图表十字光标联动;Screener 虚拟列表。

#### 3.2.1 标的详情页 7 大图表组件

| ID | 标题 | PRD | 优先 | 工作量 | 类型 | 依赖 | 验收标准 |
|----|------|-----|------|--------|------|------|----------|
| FE-117 | Attribution Waterfall(威胁分贡献度瀑布图) | §3.2.1 | P0 | 2d | 🆕 | FE-115 | ECharts 水平瀑布图;正向(红)负向(绿)柱状图;对接 `/attribution` 端点;Tooltip 显示各模块绝对数值贡献度 |
| FE-118 | 4D Signal Radar(四维信号雷达图) | §3.2.2 | P0 | 2d | 🆕 | FE-111 | ECharts 极坐标;四顶点:期权/做空/背离/内部人;半透明多边形面积填充;安全时收缩,风险时扩张 |
| FE-119 | 90-Day Trajectory 升级为 ECharts 折线图(EMA 平滑 + Tooltip) | §3.2.3 | P0 | 1.5d | 🔄 | FE-111 | 替换现有 SVG 实现;`smooth: true`;Hover 时 Tooltip 同时展示 EMA 后分 + 原始分 + lifecycle 颜色;阈值标线 |
| FE-120 | Options Anomaly Heatmap(期权异常合约热力表) | §3.2.4 | P0 | 2.5d | 🆕 | FE-111, FE-115 | 仅展示活跃合约(零交易量已过滤);DTE≤3 且 OTM>10% 的末日 Put 红色高亮;Vol/OI ≥5x 闪烁光晕;排序支持 |
| FE-121 | Short Iceberg V2(做空水位冰山图 — 双层堆叠面积图) | §3.2.5 | P0 | 2.5d | 🆕 | FE-111, FE-115 | 上层浅红(全市场 Short Ratio);下层深红(ATS 暗池占比);ECharts stacked area;Tooltip 含 Z-Score;对接 `short-iceberg-v2` |
| FE-122 | Volume-Price Divergence Dual-track(量价背离双轨图) | §3.2.6 | P0 | 2d | 🆕 | FE-111, FE-115 | 共用 X 轴,分离 Y 轴;左 Y:价格归一化(明线);右 Y:做空量回归(暗线);背离段 `markArea` 血红色遮罩 |
| FE-123 | Insider Action Timeline(内部人交易掩护时间轴) | §3.2.7 | P0 | 1.5d | 🆕 | FE-115 | 挂载于 K 线 X 轴下方;C-level 减持红色倒三角;点击弹出 Popover(职务/方向/数量/均价);ETF 标的整条灰态 |
| FE-124 | 标的详情页布局重构(多图表网格容器 + Z-index 景深) | §3.2 | P0 | 2d | 🔄 | FE-117~FE-123, FE-100 | 替换现有简单 grid 布局;采用 react-grid-layout 可拖拽网格;7 个图表组件按 PRD 拓扑排列 |

#### 3.2.2 跨图表联动与性能

| ID | 标题 | PRD | 优先 | 工作量 | 类型 | 依赖 | 验收标准 |
|----|------|-----|------|--------|------|------|----------|
| FE-125 | 跨图表十字光标同步(axisPointer.link + 消息总线) | §4.2 | P0 | 2d | 🆕 | FE-119, FE-121, FE-122 | `axisPointer.link: { xAxisIndex: 'all' }`;Zustand 消息总线;dataZoom + highlight 事件 16ms 内完成所有图表同步重绘 |
| FE-126 | ECharts large 模式 + Data Decimation + WebGL 降级 | §4.3 | P1 | 1.5d | 🆕 | FE-111 | `large: true` 默认开启;>5000 数据点时帧率 ≥ 30FPS;帧率跌破时自动切换 WebGL renderer |
| FE-127 | Screener 虚拟列表(react-window / virtual scroll) | §3.1 | P0 | 2d | 🆕 | FE-100 | Top 100+ 数据;仅渲染视口可见 DOM + 缓冲区;1000 条模拟数据零卡顿滚动 |
| FE-128 | Screener 多维排序与筛选(表头动态列) | §3.1 | P0 | 1.5d | 🔄 | FE-127 | 支持 Threat Score / Short Ratio / ATS% / OTM 偏离度排序;ETF 标的自动隐藏"内部人"列 |
| FE-129 | Screener 对接 mv_screener_top100 物化视图 | §3.1 | P0 | 0.5d | 🔄 | FE-127 | 请求 `top=100`;展示 symbol_type 标签;ETF 列自动适配 |

---

### 3.3 M3:数据大屏与智能编排(第 6-7 周)

> 目标:宏观环境页、自选篮子雷达页、LLM 智能助手 SSE 流式输出、预警中心完整落地。

#### 3.3.1 宏观环境页

| ID | 标题 | PRD | 优先 | 工作量 | 类型 | 依赖 | 验收标准 |
|----|------|-----|------|--------|------|------|----------|
| FE-130 | 宏观环境总览页(Regime Overview) — 路由 + 页面骨架 | §3.3 | P1 | 1d | 🆕 | FE-100, FE-115 | 新增路由 `/regime`;注册到 routeTree;页面含门控指示灯 + Regime 时间轴 |
| FE-131 | VIX/SPX 门控状态指示灯(Gating Indicators) | §3.3 | P1 | 1d | 🆕 | FE-130 | VIX 水位标尺(数值 + 颜色);SPX 相对 MA20 位置;对接 `/regime` 端点 |
| FE-132 | Regime 切换时间轴(状态转移色块图) | §3.3 | P1 | 1.5d | 🆕 | FE-130, FE-115 | 横贯屏幕;不同市场状态(平稳/挤压/断裂)不同背景色块;对接 `/regime_timeline`;ECharts 渲染 |

#### 3.3.2 自选篮子雷达页

| ID | 标题 | PRD | 优先 | 工作量 | 类型 | 依赖 | 验收标准 |
|----|------|-----|------|--------|------|------|----------|
| FE-133 | 自选篮子雷达页重构(CSS Grid 平铺式卡片阵列) | §3.4 | P1 | 2d | 🔄 | FE-100, FE-104 | 替换现有简单列表;每张卡片独占一个 Grid 单元;卡片内含 Spark-Radar + Threat Score + EMA 箭头 + 减持红点 |
| FE-134 | 卡片内 Spark-Radar 微缩雷达图(去坐标轴) | §3.4 | P1 | 1.5d | 🆕 | FE-118 | 4D 雷达图的微缩版;无坐标轴;数据从篮子成员 Threat Score 子模块获取 |
| FE-135 | 篮子分布直方图(BasketHistogram) | §3.4 | P1 | 1d | 🆕 | FE-133 | ECharts 直方图 + 阈值线(70/80);对接 `/baskets/{id}/distribution` |
| FE-136 | 危险聚集提示(BasketDangerCluster) | §3.4 | P2 | 0.5d | 🆕 | FE-135 | 连续 ≥3 个成员 Threat Score ≥ 70 时自动提示 |

#### 3.3.3 LLM 智能助手

| ID | 标题 | PRD | 优先 | 工作量 | 类型 | 依赖 | 验收标准 |
|----|------|-----|------|--------|------|------|----------|
| FE-137 | LLM 面板 SSE 流式输出改造(逐字打字机效果) | §3.6 | P0 | 2d | 🔄 | FE-115 | 替换现有 `fetch().json()` 为 EventSource/SSE;逐字渲染;Markdown 实时解析(heading/list/code-block);无阻塞 Loading |
| FE-138 | LLM 面板上下文自动注入(标的切换触发) | §3.6 | P1 | 1d | 🔄 | FE-137 | 主视口标的切换时,自动打包 Threat Score + 模块分 + regime + 冰山图特征;POST 到 `/llm/analyze` |
| FE-139 | LLM 面板底部持久化免责水印 | §3.6 / §7.1 | P0 | 0.5d | 🆕 | FE-137 | 不可关闭;文案:"LLM 输出仅供技术推演,存在幻觉风险,不构成投资建议" |

#### 3.3.4 预警中心页

| ID | 标题 | PRD | 优先 | 工作量 | 类型 | 依赖 | 验收标准 |
|----|------|-----|------|--------|------|------|----------|
| FE-140 | 预警中心页完整实现(规则管理 + 历史事件流) | §3.5 | P0 | 2d | 🔄 | FE-115 | 替换现有占位页;规则管理区:表单创建/编辑/删除规则;历史事件流:无限滚动列表 |
| FE-141 | AlertRuleForm(React Hook Form + Zod 条件构建器) | §3.5 | P0 | 2d | 🆕 | FE-140 | 条件组合:标的 + 指标 + 阈值 + 比较运算符;支持 AND/OR 嵌套;Zod schema 校验 |
| FE-142 | Web Push 订阅集成(VAPID + Service Worker) | §3.5 | P1 | 1.5d | 🆕 | FE-113, FE-140 | 首次进入预警页调用 `/push/vapid-public-key`;注册 SW + 获取推送权限;POST 到 `/push/subscriptions` |

---

### 3.4 M4:边缘系统与体验精雕(第 8 周)

> 目标:响应式断点适配、合规无障碍、8-K 跑马灯、管理面板、性能调优。

#### 3.4.1 响应式与移动端适配

| ID | 标题 | PRD | 优先 | 工作量 | 类型 | 依赖 | 验收标准 |
|----|------|-----|------|--------|------|------|----------|
| FE-143 | Tailwind 响应式断点三档适配(xl / md / mobile) | §5.3 | P0 | 2d | 🔄 | FE-100 | `xl > 1280px` 三栏完整布局;`md > 768px` 右侧折叠为抽屉;`< 768px` 垂直单列 + 底部工具栏 |
| FE-144 | 移动端图表交互降级(触控长按唤醒十字光标) | §5.3 | P1 | 1.5d | 🆕 | FE-125, FE-143 | `< 768px` 时禁用鼠标悬停;改为 long-press 激活十字光标;避免与页面滚动手势冲突 |
| FE-145 | PWA 离线策略增强(Workbox 缓存最近 5 标的) | §5.2 | P1 | 1d | 🔄 | FE-113 | 缓存最近 5 个标的 Threat Score + 历史数据;离线时显示缓存数据 + 提示"离线模式";容量上限 5MB |

#### 3.4.2 合规与无障碍

| ID | 标题 | PRD | 优先 | 工作量 | 类型 | 依赖 | 验收标准 |
|----|------|-----|------|--------|------|------|----------|
| FE-146 | Threat Score / 红绿灯合规 Tooltip(Info 图标) | §7.1 | P0 | 1d | 🆕 | FE-118, FE-128 | 所有 Threat Score 数值旁 + 红绿灯模块旁有 Info 图标;Hover 弹出免责文案(红底高亮);文案从 i18n 集中引用 |
| FE-147 | 图表 aria-label / aria-describedby 无障碍增强 | §7.2 | P0 | 1.5d | 🆕 | FE-117~FE-123 | 所有 ECharts 图表外层 DOM 配置动态 aria-label(如"当前全市场做空占比 30%,暗池占比 8%");aria-describedby 指向数据摘要 |
| FE-148 | 色彩对比度校准(文本 ≥ 4.5:1 + 暗黑主题) | §7.2 | P1 | 1d | 🆕 | FE-111 | 所有关键文本(ticker / Threat Score / 日期)与 `#131722` 背景对比度 ≥ 4.5:1;axe-core 扫描 0 violations |
| FE-149 | 键盘导航全链路验证(Tab + 方向键 + 图表遍历) | §7.2 | P1 | 1d | 🔄 | FE-100 | Tab 可遍历:搜索框 → 导航 → 左侧工具栏 → 主画布图表 → 右侧边栏;图表内方向键切换数据节点;focus 可见环 |
| FE-150 | 屏幕阅读器适配验证(VoiceOver / NVDA) | §7.2 | P1 | 1d | 🆕 | FE-147, FE-149 | 至少测试 VoiceOver(macOS) + NVDA(Windows);图表区域朗读数据摘要;免责声明正确读出 |

#### 3.4.3 运营功能与事件广播

| ID | 标题 | PRD | 优先 | 工作量 | 类型 | 依赖 | 验收标准 |
|----|------|-----|------|--------|------|------|----------|
| FE-151 | 8-K 重大事件跑马灯(SSE 实时横幅) | §6 | P1 | 1.5d | 🆕 | FE-115 | 对接 `/events/8k`(SSE);顶部无缝滚动横幅;点击跳转对应标的;仅展示 Item 8.01 事件 |
| FE-152 | Admin 管理面板(ETL 触发 + 回测 + Webhook 重放) | §6 | P2 | 1.5d | 🆕 | FE-115 | 新增路由 `/admin`;权限检查(非管理员隐藏);按钮触发 `/admin/etl/run` `/admin/backtest/run` |
| FE-153 | 前端性能探针上报(Performance API → `/analytics/events`) | §6 | P2 | 1d | 🆕 | FE-115 | 采集 FCP / LCP / Widget 曝光时长;batch POST 到 `/analytics/events`;5s 防抖 |
| FE-154 | Feature Flags 灰度条件渲染 Hook 增强 | §6 | P1 | 0.5d | 🔄 | — | `useFeatureFlag` 增强:支持 `enabledIf('new_screener_v2')` 组件包裹器;flag 关闭时静默降级隐藏 |

#### 3.4.4 测试与上线

| ID | 标题 | PRD | 优先 | 工作量 | 类型 | 依赖 | 验收标准 |
|----|------|-----|------|--------|------|------|----------|
| FE-155 | Playwright E2E 关键路径(搜索→详情→Screener→篮子→预警) | — | P0 | 2d | 🔄 | FE-127, FE-133, FE-140 | CI 跑通 5 条关键路径;截图归档;响应式三档各跑一次 |
| FE-156 | Lighthouse 性能调优(目标 ≥ 90 移动 + 桌面) | — | P0 | 1.5d | 🔄 | FE-126, FE-143 | LCP < 1.5s;TTI < 2.5s;CLS < 0.1;ECharts 按需引入,主 bundle gzip < 200KB |
| FE-157 | WCAG AA 自动化审计(aXe + Lighthouse Accessibility) | §7.2 | P0 | 1d | 🔄 | FE-147, FE-148 | axe-core 0 violations;Lighthouse Accessibility ≥ 95;CI 阻断 |

---

## 4. API 端点映射表(PRDM §6 对接矩阵)

> 对照 PRD 第六章"API 路由对接与全链路数据流转地图"中 18 项。

| # | 前端功能模块 | 后端 API 端点 | 状态 | 对应 TODO |
|---|-------------|---------------|------|-----------|
| 1 | 应用基座 / 全局状态监控 | `/health`, `/api/v1/data-status` | ✅ 已有 `DataStatusBanner` + `useDataStatus` | FE-101(灯带增强) |
| 2 | 全局 Screener 大屏 | `/api/v1/screener` | ✅ 已有基础表格 | FE-127(虚拟列表), FE-128(多维排序), FE-129(top100) |
| 3 | 标的搜索 / 路由跳转 | `/api/v1/symbols/lookup` | 🔄 需增强(当前首页简单路由) | FE-102(Autocomplete), FE-116(useLookup) |
| 4 | 标的综合风险详情 | `/api/v1/symbols/{ticker}/threat` 等 | ✅ 已有基础仪表盘 | FE-117~FE-123(7 大图表), FE-124(网格布局) |
| 5 | 总威胁分拆解 / 溯源 | `/api/v1/symbols/{ticker}/attribution` | 🆕 新增 | FE-117(瀑布图) |
| 6 | 大盘宏观状态 | `/api/v1/regime`, `/api/v1/regime-timeline` | 🔄 `RegimeBanner` 已有,需扩展 | FE-130(宏观页), FE-131(门控灯), FE-132(时间轴) |
| 7 | LLM 智能助手 | `/api/v1/llm/analyze` | ✅ 已有 `LlmPanel`(非 SSE) | FE-137(SSE 流式), FE-138(上下文注入), FE-139(免责水印) |
| 8 | 自选篮子 | `/api/v1/baskets` (CRUD) | ✅ 已有基础 CRUD | FE-133(雷达页重构), FE-134(Spark-Radar), FE-135(直方图) |
| 9 | 预警通知 / 规则引擎 | `/api/v1/alerts` (CRUD), `/api/v1/push/*` | 🔄 当前占位页 | FE-140(完整实现), FE-141(规则表单), FE-142(Web Push) |
| 10 | 重大事件广播 | `/api/v1/events/8k` (SSE) | 🆕 新增 | FE-151(跑马灯) |
| 11 | Feature Flags | `/api/v1/feature-flags` | ✅ 已有 `useFeatureFlag` | FE-154(增强) |
| 12 | Admin 管理 | `/api/v1/admin/*` | 🆕 新增 | FE-152(管理面板) |
| 13 | 后台日志流 | `/api/v1/logs/stream` (SSE) | ✅ 已有 `LogPanel` | — |
| 14 | 前端性能探针 | `/api/v1/analytics/events` | 🆕 新增 | FE-153(探针上报) |
| 15 | 配额 / 订阅 | `/api/v1/quota` | ✅ 已有 `useApiQuota` + `QuotaBanner` | — |
| 16 | ETF 一级市场 | `/api/v1/etf/flows` | ✅ 已有 API 封装(预留) | — |
| 17 | 灰度发布 | `/api/v1/feature-flags` | ✅ 已有 `GrayReleaseBanner` | FE-154(增强) |
| 18 | Options V2 / Short Iceberg V2 | `/symbols/{ticker}/options-anomaly-v2`, `/short-iceberg-v2` | ✅ 已有 API + 卡片展示 | FE-120(热力表), FE-121(冰山图) |

---

## 5. 工作量汇总

| 里程碑 | TODO 数量 | P0 | P1 | P2 | 总人天 |
|--------|-----------|----|----|----|-------|
| M1 基座架构与状态层 | 17 | 13 | 3 | 1 | 20.5d |
| M2 核心图表渲染 | 13 | 11 | 1 | 1 | 22d |
| M3 数据大屏与智能编排 | 13 | 6 | 6 | 1 | 17.5d |
| M4 边缘系统与体验精雕 | 15 | 7 | 6 | 2 | 17d |
| **合计** | **58** | **37** | **16** | **5** | **77d** |

---

## 6. 依赖关系图(关键路径)

```
FE-100 (四区布局) ──┬── FE-101 (顶部导航) ── FE-102 (搜索) ── FE-116 (useLookup)
                    ├── FE-103 (左侧工具栏) ── FE-107 (响应式降级)
                    ├── FE-104 (右侧边栏) ──┬── FE-105 (Watchlist 面板)
                    │                       └── FE-106 (Alerts 面板)
                    └── FE-124 (详情页网格) ── FE-125 (十字光标联动)

FE-111 (暗黑主题) ──┬── FE-117 (瀑布图)
                    ├── FE-118 (4D 雷达图) ── FE-134 (Spark-Radar)
                    ├── FE-119 (轨迹图升级)
                    ├── FE-120 (期权热力表)
                    ├── FE-121 (冰山图 V2)
                    └── FE-122 (背离双轨)

FE-113 (PWA HTTPS) ── FE-142 (Web Push)
FE-115 (API 补全) ──┬── FE-117~FE-123 (图表组件)
                    ├── FE-137 (LLM SSE)
                    ├── FE-140 (预警中心)
                    └── FE-151 (8-K 跑马灯)

FE-143 (响应式断点) ── FE-144 (触控降级)
FE-147 (aria) + FE-148 (对比度) ── FE-150 (屏幕阅读器) ── FE-157 (WCAG 审计)
```

---

## 7. 风险与约束

| 风险项 | 影响 | 缓解策略 |
|--------|------|----------|
| ECharts 多实例内存泄漏 | 标的详情页 7 个图表同时渲染可能 OOM | 路由离开时 `dispose()` 所有实例;`useEffect` cleanup 强制回收 |
| 十字光标 16ms 预算不足 | 低端设备跨图表联动卡顿 | FE-126 WebGL 降级 + Data Decimation 抽稀 |
| PWA Service Worker 在 HTTP 环境被阻断 | 离线缓存 + Web Push 失效 | FE-113 mkcert 强制 HTTPS;CI 验证 SW 注册 |
| iOS Safari 静默清除 LocalStorage | 用户布局偏好丢失 | FE-114 双重持久化(云端 + 本地) |
| SSE 连接在移动端不稳定 | LLM 流式输出中断 | FE-137 自动重连 + 降级为 JSON 全量响应 |

---

## 8. 技术栈确认(与 V1.x 一致)

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.x | UI 框架 |
| TypeScript | 5.6+ | 类型安全 |
| Vite | 5.x | 构建工具 |
| TanStack Router | 1.81+ | 类型安全路由 |
| TanStack React Query | 5.59+ | 服务端状态管理 |
| Zustand | 4.5+ | UI 状态管理 |
| Tailwind CSS | 3.4+ | 原子化 CSS |
| Apache ECharts | 5.5+ | 核心图表引擎 |
| lightweight-charts | 4.2+ | K 线/金融图表 |
| react-grid-layout | latest | 可拖拽网格(新增) |
| react-window | latest | 虚拟列表(新增) |
| vite-plugin-pwa | 0.20+ | PWA / Workbox |
| i18next | 23.x | 国际化 |
| @sentry/react | 10.x | 异常监控 |
| Playwright | latest | E2E 测试 |
| axe-core | latest | WCAG 审计 |
| Radix UI | latest | 无样式基础组件(dialog/dropdown/popover/toast) |

---

*文档冻结,等待审查确认后启动实施。*
