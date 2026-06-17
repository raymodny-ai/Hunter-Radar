# Frontend

Vite 5 + React 18 + TypeScript 5(strict)+ TanStack Router/Query + Tailwind + Radix + ECharts + lightweight-charts + PWA.

## 启动

```bash
# 1. 安装
pnpm install
# 2. 启动(需后端在 :8000)
pnpm dev
# 3. 打开 http://localhost:5173
```

## 目录

```
src/
├── main.tsx           # 入口(QueryClient + Router)
├── router.tsx         # TanStack Router 实例
├── routeTree.ts       # 路由树(由 vite 插件自动生成)
├── routes/            # 路由级组件
│   ├── __root.tsx     # 根布局(导航 / 免责声明 / 横幅)
│   ├── index.tsx      # 首页(搜索 + Top 10 预览)
│   ├── symbol.$ticker.tsx  # 单标的综合体检看板(核心页)
│   ├── screener.tsx   # 每日猎物榜单
│   ├── basket.tsx     # 自选篮子
│   └── alerts.tsx     # 预警规则(Pro)
├── components/
│   ├── common/Disclaimer.tsx       # 全站统一免责
│   └── radar/
│       ├── ThreatScoreGauge.tsx    # 圆形仪表盘
│       ├── ModuleSignalLight.tsx   # 单模块信号灯
│       └── RegimeBanner.tsx        # 顶部市场状态横幅
├── lib/
│   ├── api.ts         # 后端 API 客户端
│   └── queryClient.ts # TanStack Query 全局配置
├── i18n/
│   ├── index.ts       # i18next 初始化
│   └── zh-CN.json     # 中文文案(兜底)
└── index.css          # Tailwind + 信号灯发光效果
```

## 关键设计

- **OpenAPI 自动生成类型**:`pnpm openapi:gen` 从运行中的后端拉 `/openapi.json` → `src/api-types.d.ts`(FE-010 / BD-078)。
- **PWA**:`vite-plugin-pwa` + Workbox;报告接口 12h 缓存(vite.config 中已配)。
- **ECharts / lightweight-charts 按需引入**:Vite 报告包体 ≈300KB(目标)。
- **状态灯发光**:纯 CSS 阴影,GPU 友好。
- **i18n 兜底 zh-CN**:M1 阶段只做中文,接口已留出英文扩展位。
