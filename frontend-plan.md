# 猎手雷达 V1.4 — 前端实现计划书

> 版本:V1.4.0-front-plan
> 适用对象:Hunter Radar V1.4 PRD §3.5(全维度共振体检看板)+ §4(自定义分析与高级功能)
> 文档定位:为前端工程实施提供技术选型、目录结构、模块拆分、里程碑拆分、合规与无障碍约束,本计划书不实现具体代码。

---

## 1. 计划范围与边界

### 1.1 覆盖范围

本计划书覆盖以下前端功能模块,完全对应 PRD §3.5 与 §4 描述:

- §3.5 全维度共振体检看板(Resonance Dashboard)
  - 加权评分卡机制(Threat Score 0–100)
  - 信号生命周期管理(发现 / 确认 / 衰减)
  - 市场状态门控(VIX > 30 或 SPX 跌破 20 日均线)
  - 终极警报全屏覆盖层
- §3.1–§3.4 各模组可视化(期权异动 / 全监管做空 / 量价背离 / SEC 内部)
- §4.1 自定义代码输入与历史
- §4.2 自选篮子雷达
- §4.3 自定义预警推送与 Screener 扩展

### 1.2 不覆盖范围(明示)

- 后端 ETL 与数据采集(FINRA / SEC / Yahoo Finance 爬虫、ETL 流水线、数据库建模)—— 由独立后端任务负责
- 实时行情数据流(本产品为日终批处理,前端无 WebSocket 订阅)
- 商业化计费 / 订阅 / 支付流程(仅预留前端路由容器)
- 原生 App(仅做 PWA 适配,不开发 iOS / Android)
- §3.4 ETF 一级市场申赎异动模块(本版本不实现,前端仅保留占位卡)

---

## 2. 技术选型

### 2.1 技术栈总览

| 层 | 选型 | 备选 | 决策理由 |
|---|---|---|---|
| 构建工具 | Vite 5 | Webpack 5 / Turbopack | HMR 毫秒级、原生 ESM、生态成熟、零配置支持 React+TS |
| 框架 | React 18 | Vue 3 / Svelte 5 | 团队熟悉度高、SSR/PWA 工具链齐备、社区可视化库最丰富 |
| 语言 | TypeScript 5(严格模式) | — | PRD 数据模型含 Z-Score / 分位值 / 评分卡,必须强类型保护计算正确性 |
| 路由 | TanStack Router 1.x | React Router 7 | 完全类型安全的路由参数、搜索参数、loader |
| 服务端状态 | TanStack Query 5 | SWR / RTK Query | 缓存、重试、失效与 React Suspense 集成度高 |
| 客户端状态 | Zustand 4 | Redux Toolkit / Jotai | Threat Score / 信号灯状态需要全局共享,Zustand 简洁且无 boilerplate |
| 样式 | Tailwind CSS 3 | CSS Modules / Vanilla Extract | 工具类约束设计无歧义;无主观视觉偏好注入 |
| 组件库 | Radix UI Primitives | Headless UI / shadcn/ui | 完全无样式原语,与 Tailwind 配合避免组件库锁定设计语言 |
| 图表 | ECharts 5(主) + lightweight-charts(金融专用) | Recharts / Visx | ECharts 支持明暗双轨图、水位图、迷你图;lightweight-charts 用于 K 线 / 价差图,体积仅 45KB |
| 表单 | React Hook Form + Zod | Formik | 预警规则配置、自选篮子批量输入需要 schema 校验 |
| 日期 | date-fns | Day.js / Luxon | Tree-shakable、时区支持 |
| 国际化 | i18next + react-i18next | — | PRD 要求中文文案,需保留 i18n 通道以备未来双语切换 |
| 测试 | Vitest(单元) + React Testing Library(组件) + Playwright(E2E) | Jest + Cypress | Vite 原生支持 Vitest;Playwright 跨浏览器 E2E 体验最佳 |
| 静态检查 | ESLint(typescript-eslint + react-hooks) + Prettier | — | 标准化代码风格,CI 强制 |
| 部署 | Vercel / Netlify Edge / 自托管 Nginx | — | 纯静态 SPA + PWA,任意 CDN 即可 |
| PWA | Workbox 7(vite-plugin-pwa) | — | 离线缓存最近一次报告、Service Worker 推送就绪 |
| 监控 | Sentry | — | 前端异常、性能指标采集 |
| 文档 | Storybook 8 | Ladle | 组件级文档,设计与产品协作 |

### 2.2 不选用项说明

- **不选 Next.js**:本产品是纯前端 SPA + 后端 REST,无需 SSR/ISR;Vite 更轻、构建产物更小
- **不选 Ant Design / Material UI / Chakra**:这些库携带强设计语言,与 PRD 的中性文案要求冲突
- **不选 Recharts 作为主图表库**:Recharts 在大数据量散点图与热力图上性能下降,本产品的 Z-Score 历史序列与短期信号堆积需要 ECharts 的 canvas 渲染
- **不选 Redux**:本产品状态规模小,Zustand 完全够用;Redux 的样板代码会拖慢迭代

### 2.3 浏览器与设备支持

- 桌面端:Chrome 110+ / Edge 110+ / Firefox 110+ / Safari 16+
- 移动端:iOS Safari 16+ / Chrome Android 110+(PWA 模式)
- 最低分辨率:1280×800(桌面) / 360×640(移动)
- 不支持:IE 任何版本(无兼容代码)

---

## 3. 目录结构

```
hunter-radar-frontend/
├── public/
│   ├── favicon.ico
│   ├── manifest.webmanifest              # PWA 清单
│   └── robots.txt
├── src/
│   ├── main.tsx                         # 入口
│   ├── App.tsx                          # 根组件 + Provider 装配
│   ├── router.tsx                       # TanStack Router 配置
│   ├── routes/                          # 路由级组件
│   │   ├── __root.tsx                   # 根布局(头部 / 全局免责声明 / 错误边界)
│   │   ├── index.tsx                    # 首页(搜索框 + 历史)
│   │   ├── symbol.$ticker.tsx           # 单标的综合体检看板(核心页)
│   │   ├── basket.index.tsx             # 自选篮子列表
│   │   ├── basket.$id.tsx               # 单个篮子详情
│   │   ├── screener.index.tsx           # 每日猎物榜单
│   │   ├── alerts.index.tsx             # 预警规则管理(Pro)
│   │   └── settings.tsx                 # 偏好与免责声明
│   ├── components/                      # 展示型组件
│   │   ├── radar/
│   │   │   ├── ThreatScoreGauge.tsx     # 圆形仪表盘
│   │   │   ├── ModuleSignalLight.tsx    # 单模块信号灯
│   │   │   ├── ModuleLightRow.tsx       # 四/三模块信号灯阵列
│   │   │   ├── SignalLifecycleBadge.tsx # 发现/确认/衰减 状态徽章
│   │   │   ├── MarketRegimeBanner.tsx   # VIX 门控提示横幅
│   │   │   └── UltimateAlertOverlay.tsx # 终极警报全屏覆盖层
│   │   ├── charts/
│   │   │   ├── OptionsAnomalyList.tsx   # 末日 Put 异常合约列表 + OI 迷你图
│   │   │   ├── ShortIcebergChart.tsx    # 水下冰山水位图
│   │   │   ├── DivergenceDualTrack.tsx  # 明暗双轨图
│   │   │   ├── SecTimeline.tsx          # SEC 内部行为时间轴
│   │   │   └── ThreatHistoryChart.tsx   # 90 日 Threat Score 轨迹
│   │   ├── search/
│   │   │   ├── SymbolSearchBox.tsx      # 搜索框(含 debounce + 自动补全)
│   │   │   ├── SymbolTypeBadge.tsx      # 个股 / ETF 标识
│   │   │   └── SearchHistoryList.tsx    # 最近查询
│   │   ├── basket/
│   │   │   ├── BasketHistogram.tsx      # 篮子 Threat Score 分布
│   │   │   ├── BasketMemberTable.tsx    # 篮子成员表
│   │   │   └── BasketDangerCluster.tsx  # 危险聚集提示
│   │   ├── screener/
│   │   │   ├── ScreenerTable.tsx        # Top 10–20 表格
│   │   │   └── PaywallTeaser.tsx        # 前 3 条免费 + Pro 引导
│   │   ├── alerts/
│   │   │   ├── AlertRuleForm.tsx        # 预警规则配置表单
│   │   │   ├── AlertChannelPicker.tsx   # 邮件 / 浏览器通知
│   │   │   └── AlertHistory.tsx         # 触发历史
│   │   ├── layout/
│   │   │   ├── AppHeader.tsx            # 顶部导航
│   │   │   ├── AppFooter.tsx            # 底部 + 全局免责声明
│   │   │   └── DisclaimerBanner.tsx     # 站内固定提示
│   │   └── primitives/                  # Radix 包装(Button / Dialog / Select 等)
│   ├── features/                        # 业务逻辑 hooks
│   │   ├── useSymbolSearch.ts
│   │   ├── useThreatReport.ts
│   │   ├── useBasketSnapshot.ts
│   │   ├── useScreener.ts
│   │   ├── useAlertRules.ts
│   │   ├── useMarketRegime.ts
│   │   └── useSearchHistory.ts
│   ├── lib/                             # 工具与适配
│   │   ├── api/
│   │   │   ├── client.ts                # fetch 封装 + 拦截器
│   │   │   ├── mock/                    # 假数据(后端未到位时使用)
│   │   │   │   ├── symbolReport.mock.ts
│   │   │   │   ├── screener.mock.ts
│   │   │   │   └── basket.mock.ts
│   │   │   └── types.ts                 # 与后端契约的 TS 类型
│   │   ├── format/
│   │   │   ├── number.ts                # 百分号 / 美元 / 紧凑数字
│   │   │   └── date.ts
│   │   ├── compliance/
│   │   │   └── disclaimer.tsx           # 文案常量(集中管理,审计用)
│   │   ├── color/
│   │   │   └── scorePalette.ts          # Threat Score 0–100 颜色映射
│   │   └── pwa/
│   │       └── registerSW.ts
│   ├── stores/                          # Zustand store
│   │   ├── useAppStore.ts               # 用户偏好(语言、时区、主题预留)
│   │   ├── useSearchHistoryStore.ts     # localStorage 持久化
│   │   └── useAlertStore.ts
│   ├── styles/
│   │   ├── tailwind.css
│   │   └── tokens.css                   # CSS 变量(色板 / 间距)
│   ├── i18n/
│   │   ├── zh-CN.json
│   │   └── index.ts
│   └── test/
│       ├── setup.ts
│       ├── fixtures/
│       └── helpers/
├── .env.example
├── .eslintrc.cjs
├── .prettierrc
├── index.html
├── package.json
├── pnpm-lock.yaml                       # 锁文件统一使用 pnpm
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.cjs
├── README.md
└── CHANGELOG.md
```

---

## 4. 模块拆解与依赖关系

### 4.1 模块依赖图

```
首页 (§4.1)
   └── symbol.$ticker (§3.5 核心页)
          ├── 模块一可视化(§3.1)
          ├── 模块二可视化(§3.2)
          ├── 模块三可视化(§3.3)
          ├── 模块四可视化(§3.4,ETF 灰态)
          ├── ThreatScoreGauge
          ├── ModuleLightRow
          ├── SignalLifecycleBadge
          ├── MarketRegimeBanner
          └── UltimateAlertOverlay

自选篮子 (§4.2)
   └── basket.$id
          ├── BasketHistogram
          ├── BasketMemberTable(复用 symbol.$ticker 缩略卡片)
          └── BasketDangerCluster

Screener (§4.3)
   └── screener.index
          ├── ScreenerTable
          └── PaywallTeaser(Pro 引导)

预警 (§4.3)
   └── alerts.index
          ├── AlertRuleForm
          ├── AlertChannelPicker
          └── AlertHistory
```

### 4.2 跨模块复用

| 复用单元 | 消费方 | 备注 |
|---|---|---|
| `useThreatReport(symbol)` | 看板页、篮子页、Screener | 同 symbol 在不同页呈现的 Threat Score 必须一致 |
| `<ThreatScoreGauge>` | 看板页、篮子成员卡、Screener 行 | 颜色映射规则全局唯一 |
| `<ModuleSignalLight>` | 看板页、终极警报 | 信号灯颜色严格按 PRD §3.5.3 状态机 |
| `<SymbolTypeBadge>` | 搜索框、看板页头、篮子成员 | 个股 / ETF 标签决定模块四是否渲染 |
| `useMarketRegime()` | 看板页、终极警报、Screener 顶部 | 门控提示在多处出现,需拉取并缓存 |
| `compliance/disclaimer.tsx` | 全站页脚、终极警报、报告顶部 | 文案常量集中,合规审计时单一来源 |

### 4.3 数据契约(与后端 API 关系)

前端需要的所有数据通过以下 REST 端点提供(后端实现后填实,本阶段以 mock 支撑):

| 端点 | 用途 | 频次 | 缓存策略 |
|---|---|---|---|
| `GET /api/v1/symbols/lookup?q=QQQ` | 自动补全 | 实时 | TanStack Query 5 分钟 |
| `GET /api/v1/symbols/{ticker}/report` | 单标的综合报告 | 盘后一次 | SWR 12 小时(日内不变) |
| `GET /api/v1/symbols/{ticker}/history?days=90` | Threat Score 90 日轨迹 | 一次性 | TanStack Query 24 小时 |
| `GET /api/v1/baskets` | 自选篮子列表 | 登录后 | TanStack Query 6 小时 |
| `POST /api/v1/baskets` | 新建篮子 | 用户操作 | 即时失效 |
| `GET /api/v1/baskets/{id}/snapshot` | 篮子当日快照 | 盘后一次 | TanStack Query 12 小时 |
| `GET /api/v1/screener?date=YYYY-MM-DD` | 每日猎物榜单 | 盘后一次 | TanStack Query 24 小时 |
| `GET /api/v1/alerts/rules` | 预警规则 | 用户操作 | 即时 |
| `POST /api/v1/alerts/rules` | 新建规则 | 用户操作 | 即时 |
| `GET /api/v1/regime` | 市场门控状态 | 盘后一次 | TanStack Query 6 小时 |

> **未到位前端门控**:以上任一端点返回 404 / 5xx 时,前端必须显示「数据等待监管披露」占位卡,不得用旧数据或假数据伪装成功响应(对齐 PRD §5.1 数据冗余与容错)。

---

## 5. 视觉与交互规范

### 5.1 设计原则(与 PRD §1.5 一致)

- **中性文案**:无 emoji 状态灯(使用文字「发现/确认/衰减」+ 颜色编码),无「建议/推荐」类措辞
- **数据即界面**:Threat Score / Z-Score / 占比等数值优先展示,装饰元素让位于数据
- **可解释性**:任何异常都需在 N 步点击内可下钻到原始 FINRA / SEC 文件链接
- **键盘可达**:Tab 顺序符合视觉顺序,信号灯与告警可用快捷键聚焦

### 5.2 颜色系统

- Threat Score 0–100 颜色映射(全局唯一,见 `lib/color/scorePalette.ts`):

| 区间 | 颜色 | 含义 |
|---|---|---|
| 0–49 | 中性绿 | 衰减 / 安全 |
| 50–69 | 中性黄 | 确认 |
| 70–79 | 中性橙 | 发现(常态) |
| 80–100 | 中性红 | 发现(高恐慌模式)或终极警报 |
- 信号灯阵列使用同色板,保持与仪表盘一致
- 全站禁止使用品牌化强色(如纯荧光红),所有颜色对色盲友好(WCAG AA 合规)

### 5.3 排版与间距

- 字体:`Inter`(英数)+ 系统默认中文回退(`PingFang SC` / `Microsoft YaHei`)
- 数值字段:`Inter` tabular-nums,等宽对齐便于扫读
- 间距尺度:Tailwind 默认 4 / 8 / 16 / 24 / 32px 五档
- 圆角:4px(数据卡)/ 8px(模态)/ 9999px(信号灯圆点)

### 5.4 关键页面交互稿(文字 wireframe)

#### 5.4.1 单标的综合体检看板(核心页)

```
+--------------------------------------------------------------+
| [LOGO]  Hunter Radar              [搜索 QQQ____]  [账户]   |
+--------------------------------------------------------------+
| 免责声明横幅:本工具不构成投资建议,数据源自 FINRA / SEC 公开延时数据 |
+--------------------------------------------------------------+
|                                                              |
|  QQQ  Invesco QQQ Trust  [ETF]                上次更新 18:42 |
|                                                              |
|  +----------------------------+  +-------------------------+ |
|  | Threat Score                |  | 90 日轨迹               | |
|  | 圆形仪表盘 78/100           |  | [迷你折线图]            | |
|  | (发现)                      |  |                         | |
|  +----------------------------+  +-------------------------+ |
|                                                              |
|  信号灯阵列                                                  |
|  [模块一 76] [模块二 88] [模块三 65] [模块四 -- (ETF 不适用)] |
|                                                              |
|  +------------------ 摘要文案 -------------------------+    |
|  | QQQ 做空占比突破历史极值(Z-Score 2.8),看跌期权端   |    |
|  | 出现密集新开仓,但无内部人信号。该信号可能反映整体   |    |
|  | 市场看空情绪或对冲盘,建议结合成分股表现综合判断。   |    |
|  +-------------------------------------------------------+  |
|                                                              |
|  +--- 模块一:期权异动 ----+  +--- 模块二:全监管做空 ----+   |
|  | 末日 Put 异常合约表格  |  | 水下冰山水位图(近 20 日) |   |
|  |  OI 增幅迷你图         |  |                         |   |
|  +------------------------+  +-------------------------+    |
|                                                              |
|  +--- 模块三:量价背离 ----+  +--- 模块四:SEC 内部 ----+    |
|  | 明暗双轨图              |  | [ETF 无内部人行为数据]   |   |
|  +------------------------+  +-------------------------+    |
|                                                              |
|  原始数据来源链接(展开)                                     |
|  - FINRA Daily Short Sale Volume: 2026-06-10                |
|  - SEC EDGAR Form 4(无)                                     |
+--------------------------------------------------------------+
| 免责声明:本雷达数据源自 FINRA 及 SEC 等公开延时数据...       |
+--------------------------------------------------------------+
```

#### 5.4.2 终极警报全屏覆盖层

- 触发条件:Threat Score ≥ 70 且至少一个核心模块异常持续 2 日以上
- 表现:背景中性红遮罩,中央卡片显示「检测到多维度做空筹码共振」
- 卡片底部:动态滚动免责声明
- 关闭:必须用户主动点击「我已了解」按钮,无自动消失

### 5.5 无障碍

- WCAG 2.1 AA 合规
- 颜色对比度 ≥ 4.5:1(正文) / 3:1(大字)
- 全部交互组件支持键盘操作
- 屏幕阅读器友好:信号灯带 `aria-label="模块一,76 分,发现"`
- 减少动画支持:`prefers-reduced-motion` 时关闭数字滚动与图表入场动画

---

## 6. 合规与文案约束

### 6.1 文案禁令清单

前端文案在 CI 阶段由 `tools/compliance_check.js`(可复用 `prd_build/audit_*.js` 模式新增)强制检查,以下词组与符号禁用:

- 任何 emoji(状态灯用文字 + 颜色)
- 「建议」「推荐」「应当」「值得」「可以买入」「可以卖出」等主观词
- 「100% 准确」「保证收益」等绝对化措辞
- 「投资机会」「金股」「黑马」等营销词汇

### 6.2 必含文案(集中常量)

`src/lib/compliance/disclaimer.tsx` 集中管理以下必含文本:

- 页脚固定免责声明
- 报告页顶部提示横幅
- 终极警报底部动态免责声明
- Screener 榜单顶部说明
- 登录 / 注册页(若启用)勾选声明
- 邮件 / 推送预警正文尾部

### 6.3 数据未到位门控

- 端点 404 / 5xx 时显示「数据等待监管披露」占位卡
- 不得使用 mock 数据伪装成真实数据
- 不得复用前一日数据
- 篮子里任一标的拉取失败,整篮仍展示,失败成员独立标注

---

## 7. 性能预算

### 7.1 关键指标

| 指标 | 目标 | 测量方式 |
|---|---|---|
| 首屏 LCP(单标的页) | < 1.5s (P95) | Lighthouse / Web Vitals |
| 交互响应(TTI) | < 2.5s (P95) | Lighthouse |
| 包体大小(主入口) | < 200KB gzip | Vite build 报告 |
| 图表初始渲染 | < 500ms | Performance API |
| Service Worker 离线可用 | 最近一次报告可读 | Workbox |

### 7.2 实现策略

- 路由级 code-split:看板页、篮子页、Screener 页各自独立 chunk
- ECharts 按需引入(用 `echarts/core` + 手动注册模块,体积从 ~900KB 降至 ~300KB)
- 图表数据懒加载:K 线历史通过动态 import 进入视口才请求
- Service Worker 预缓存最近一次报告(用于离线兜底)
- 关键 CSS 内联,字体使用 `font-display: swap`

---

## 8. 里程碑拆分

### M0 — 项目脚手架(0.5 周)

- 初始化 Vite + React + TS + Tailwind + ESLint + Prettier
- 接入 TanStack Router 与 TanStack Query
- 搭建目录结构与 CI(Vercel Preview / GitHub Actions)
- 配置 i18n 框架(zh-CN 兜底)
- Storybook 初始化
- 交付物:`pnpm dev` 可运行的空壳 + CI 绿勾

### M1 — 核心看板骨架(1.5 周)

- 路由 `symbol.$ticker.tsx` 框架
- `useThreatReport(symbol)` mock 数据接入
- `ThreatScoreGauge` + `ModuleLightRow` 组件
- `SignalLifecycleBadge` 状态机
- `MarketRegimeBanner` + `useMarketRegime`
- 必含免责声明横幅(全站)
- 端到端从首页搜索 → 看板页路由打通
- 交付物:用 mock 数据完整呈现 §3.5 看板骨架(不含 4 个模组的细化图表)

### M2 — 四个模组可视化(2 周)

- M2a 模块一(期权异动):异常合约列表 + OI 迷你图 + 5 日曲线
- M2b 模块二(全监管做空):水下冰山水位图 + 放大窗口
- M2c 模块三(量价背离):明暗双轨图 + 自然语言标注
- M2d 模块四(SEC 内部):事件时间轴 + ETF 灰态占位
- 交付物:四个模组可视化全部完成,各模组带 Storybook 故事

### M3 — 终极警报与生命周期(0.5 周)

- `UltimateAlertOverlay` 全屏覆盖层
- 信号生命周期天数计数
- 90 日 Threat Score 轨迹
- 交付物:触发条件齐备,符合 PRD §3.5.5

### M4 — 自定义分析(§4)(1 周)

- M4a 自定义代码输入:搜索框 + 自动补全 + 历史(localStorage 持久化)
- M4b 自选篮子:列表 / 详情 / 分布图 / 危险聚集
- M4c Screener:榜单 + 免费 / Pro 分级
- M4d 预警规则:表单 + 通道选择 + 触发历史
- 交付物:§4 全部前端能力可演示

### M5 — 集成与端到端(1 周)

- 接入真实后端(若后端已就绪)
- E2E 测试(Playwright 关键路径)
- 性能调优(达到 §7.1 预算)
- Lighthouse 跑分(目标 ≥ 90)
- 无障碍审计(WCAG AA)
- 合规文案 CI 检查(`compliance_check.js`)
- 交付物:可上线版本,配套部署文档

### M6 — PWA 与推送(0.5 周)

- Workbox 注册与离线策略
- 浏览器通知推送通道
- 安装提示(可装桌面)
- 交付物:PWA 可装,推送可用(需后端配合)

### 里程碑总览

| 里程碑 | 周期 | 累计 | 主要交付 |
|---|---|---|---|
| M0 | 0.5 周 | 0.5 周 | 项目脚手架 |
| M1 | 1.5 周 | 2.0 周 | 看板骨架 |
| M2 | 2.0 周 | 4.0 周 | 四模组可视化 |
| M3 | 0.5 周 | 4.5 周 | 终极警报 + 生命周期 |
| M4 | 1.0 周 | 5.5 周 | 自定义分析 |
| M5 | 1.0 周 | 6.5 周 | 集成 + E2E + 性能 |
| M6 | 0.5 周 | 7.0 周 | PWA + 推送 |

**总周期估算:7 周(1 个全职前端工程师 + 半个后端对接)**

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 后端 API 推迟到位,前端长期依赖 mock | M1–M4 进度可独立,但 M5 集成延期 | mock 与真实 API 通过 `lib/api/client.ts` 适配器隔离,接口契约先行 |
| ECharts 在低端移动设备卡顿 | 移动端体验差 | 检测设备性能,降级到 Recharts 或纯 SVG |
| 大量历史数据(90 日 × 多标的)首屏慢 | 看板页 LCP 不达标 | 路由级流式渲染(Suspense)+ 数据分页 |
| 合规文案被无意修改 | 合规风险 | CI 阶段 grep + 强制文案常量集中,PR diff 高亮 |
| PWA 推送浏览器支持参差 | 推送覆盖不全 | 推送作为「增强」能力,缺失时回退到邮件 |
| WCAG 审计未通过 | 上线阻断 | M5 早中期介入,无障碍作为 M1–M4 验收硬卡 |

---

## 10. 与现有资产的衔接

### 10.1 复用 `prd_build/tools/` 的审计脚本

- `audit.js` / `audit_assembly.js` 的模式(正则 + 错误清单)可用于前端的 `compliance_check.js`
- `count_lines.{py,js,ps1}` 可在 CI 阶段统计前端文件规模趋势
- `section_structure.js` 的「层级校验」思路可移植到组件 prop 校验

### 10.2 与后端契约的占位

- 本计划书定义的 10 个 REST 端点需后端在 M1 开始前给出 OpenAPI 草案
- TypeScript 类型 `src/lib/api/types.ts` 与 OpenAPI 同步,可用 `openapi-typescript` 自动生成

### 10.3 与 GitHub 仓库的目录衔接

新建 `frontend/` 目录,与现有的 `docs/` `references/` `tools/` `prd_build/` 并列:

```
Hunter-Radar-V1.4/
├── docs/                      # PRD 与设计文档
├── references/                # 源参考与审计报告
├── tools/                     # PRD 装配与审计脚本
├── prd_build/                 # 本地原始工作目录镜像
└── frontend/                  # ← 本计划书实施位置
    ├── src/
    ├── public/
    ├── package.json
    └── ...
```

README.md 中追加章节「前端开发」,指向 `frontend/README.md` 与本计划书。

---

## 11. 验收标准

每个里程碑必须满足以下通用验收项方可进入下一阶段:

- [ ] 所有 PR 通过 ESLint + Prettier + TypeScript 严格类型检查
- [ ] 新增组件在 Storybook 中有故事 + 文档
- [ ] 关键路径有单元测试(覆盖主分支,目标 ≥ 70%)
- [ ] `compliance_check.js` 在 CI 中通过(无 emoji / 无主观词)
- [ ] 必含免责声明完整呈现
- [ ] 键盘可达性 + 屏幕阅读器测试通过
- [ ] Lighthouse 移动 / 桌面分数 ≥ 90
- [ ] 后端 API 未到位时,前端不崩溃且显示「数据等待监管披露」占位

---

## 12. 后续工作(本计划书不实现,仅记录)

- §3.4 ETF 一级市场申赎异动模块(待 CBOE / 发行商数据源确定后,本计划书预留 `EtfPrimaryFlowPanel.tsx` 占位卡 + REST 端点 `GET /api/v1/etf/{ticker}/primary-flow` 返回 501)
- 机构版批量 API 前端(机构付费用户)
- 多语种扩展(英文 / 繁体)—— i18n 框架已就位
- 服务端渲染(若 SEO 需求出现)—— 评估迁移到 Remix 的成本

---

(本计划书到此结束,实施阶段由独立前端工程任务按里程碑推进)
