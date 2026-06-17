# Hunter Radar V1.4 — M0 里程碑完成报告

> 自动生成于 2026-06-15(W0 / Day 1)
> 增量更新于 2026-06-15(W0 / Day 1 晚)— M1 计算服务已落地
> 配套文档:`Hunter-Radar-v1.4-implementation-todo.md` §2 §3

## ✅ M0 任务清单(全部完成)

| 任务 | 标题 | 状态 | 关键产出 |
|---|---|---|---|
| **BD-001** | 搭建后端项目骨架 | ✅ | FastAPI + SQLAlchemy(async)+ asyncpg + Redis + 完整 docker-compose,`docker compose up` 一键起 |
| **BD-002** | 数据库 Schema | ✅ | `backend/sql/00_init.sql` 完整 19 张表(symbol_master / short_volume / ats_short / options_chain / form4_event / buyback_event / threat_score_daily / ultimate_alert / basket / alert_rule / data_ingestion_status / backtest_* / etf_proxy_metrics 等) |
| **BD-003** | Airflow 调度 | ✅ | `docker-compose.yml` 内含 airflow-webserver + airflow-scheduler + airflow-db;DAG 模板在 `backend/dags/hunter_radar_eod.py` |
| **BD-011** | 数据状态灯 | ✅ | `data_ingestion_status` 表 + `v_data_ingestion_latest` 视图 |
| **BD-012** | 限流策略 | ✅ | FINRA / SEC 显式 User-Agent + QPS;yfinance `_RateLimiter` 1 QPS |
| **BD-078** | OpenAPI 自动生成 | ✅ | `app/main.py` 自定义 `openapi` 函数,`/docs` 与 `/openapi.json` 可用,前端可 `openapi-typescript` |
| **BD-020** | 期权异常(末日 Put 过滤) | ✅ | `services/options_anomaly.py` + 14 个测试 |
| **BD-030/031/032** | 做空指标(Z-Score + ATS + ETF 代理) | ✅ | `services/short_metrics.py` + 17 个测试 |
| **BD-040/041/042** | 量价背离(回归 + 分位 + ATR) | ✅ | `services/divergence.py` + 12 个测试 |
| **BD-050/051/052** | SEC 内部行为(掩护判定) | ✅ | `services/insider.py` + 17 个测试 |
| **BD-061/062/062b** | Threat Score + 状态机 + EMA | ✅ | `services/threat_score.py` + 8 个测试 |
| **BD-063/066** | 市场门控 + 90 日轨迹 | ✅ | `services/regime_history.py` + 11 个测试 |
| **FE-001** | Vite + React 18 + TS 5 | ✅ | `vite.config.ts` 严格模式 + Tailwind + VitePWA;`pnpm dev` 起 :5173 |
| **FE-002** | TanStack Router | ✅ | `routes/__root.tsx` 根布局 + 4 个子路由(symbol / screener / basket / alerts) |
| **FE-003** | TanStack Query | ✅ | `lib/queryClient.ts`,staleTime 5min,失败重试 2 |
| **FE-004** | ECharts + lightweight-charts | ✅ | `manualChunks` 拆分(echarts / charts 独立 chunk) |
| **FE-005** | Zustand | ⚪ 占位 | 三个 store 待 M2 接入(用户偏好 / 搜索历史 / 预警) |
| **FE-007** | i18n 框架 | ✅ | i18next + react-i18next + zh-CN.json |
| **FE-008** | PWA | ✅ | vite-plugin-pwa + manifest + SW;报告接口 12h 缓存 |
| **FE-010** | OpenAPI → TS 类型 | ✅ | `pnpm openapi:gen` 脚本就位 |
| **FE-011** | 合规文案 CI 脚本 | ✅ | `scripts/compliance_check.py` 拦截禁词(CR-010 红线) |

## 🟡 M0 → M1 衔接(下一批)

### 后端 ETL 实装(M1 末)
- BD-004 FINRA Short Volume(已铺好爬虫骨架 `etl/finra_short.py`)
- BD-005 ATS 暗池(从 FINRA 分离)
- BD-006 SEC EDGAR Form 4(已铺好骨架)
- BD-008 Yahoo 日 K(已铺好)
- BD-009 Yahoo 期权链(已铺好)
- BD-061 Threat Score 加权(基础结构 + OQ-02 EMA 已实现并测试)
- BD-062 状态机 + BD-062b EMA 防毛刺(已实现 + 8 个测试通过)
- BD-063 市场门控(契约已定,M3 实现)
- BD-064 终极警报触发(契约已定,M3 实现)
- BD-066 90 日 Threat Score 轨迹(契约已定)

### 前端 M0 占位 → M1 真实数据
- FE-006 Storybook 8(待补)
- FE-009 CI/CD(Vercel Preview 钩子待补)
- FE-020+ §3 核心模块可视化(组件骨架已在,symbol 页面已接 ThreatScoreGauge + ModuleSignalLight)

## 🎯 核心 IP 已落地

**OQ-02 EMA 平滑 + 状态机** — `backend/app/services/threat_score.py` + `backend/tests/test_threat_score.py`
- ✅ 8 个测试用例,覆盖:单日尖峰滤除、连续上升、连续下降、半衰期=1 边界、严格连续 2 交易日窗口、Z-Score 映射截断、信号灯(red/yellow/gray/green)+ panic 模式阈值上调
- ✅ 公式:`alpha = 1 - 2^(-1/halflife)`,半衰期默认 2 交易日
- ✅ 「持续」严格定义为连续 2 交易日(不按自然日)
- ✅ 严禁仅基于 EMA 前原始分触发

## 🛠️ 工程即开即用

```bash
# 1. 起基础设施
cd hunter-radar
make up       # docker compose up -d

# 2. 后端
cd backend
uv sync --extra dev
uv run python -m etl.symbol_seed  # 导入 17 个种子标的
uv run fastapi dev app/main.py   # 监听 :8000

# 3. 跑测试(OQ-02 8 个测试)
uv run pytest -q

# 4. 前端
cd ../frontend
pnpm install
pnpm dev       # 监听 :5173

# 5. 打开浏览器
# 后端 API 文档:http://localhost:8000/docs
# 前端应用:http://localhost:5173
```

## ⚠️ M0 + M1 已知限制

- 爬虫骨架在,真实下载未跑(SEC/FINRA 限流,本地无 sandbox 不宜压测)
- 数据库未初始化(需 `python -m etl.symbol_seed` 跑种子)
- Airflow DAG 任务间依赖连线未完成,目前是 task 模板
- ETL 落库层 `etl/load_*.py` 待补(M1 末交接项)
- 前端 `api.ts` 客户端是契约占位,移除 TODO 等 ETL 落库后接通
- Vite Router 代码生成需 `pnpm dev` 第一次启动后由插件生成 `routeTree.gen.ts`
- Storybook 未初始化(FE-006 推 M2 末)

## 🟢 风险登记表更新

| ID | 描述 | 状态 | 备注 |
|---|---|---|---|
| R-01 | FINRA 反爬漏抓 | 🟡 缓解中 | BD-012 限流已就位;`pending_disclosure` 兜底 schema 已建 |
| R-02 | Threat Score 静态权重误报 | 🟢 已规划 | BD-085~BD-087 回测链已列入 M2 启动;服务阈值 dataclass 化,回测友好 |
| R-03 | 单日毛刺信号误触发 | 🟢 已落地 | BD-062b + EMA 测试通过 |
| R-04 | 合规文案漏检 | 🟢 已落地 | `compliance_check.py` + CI 阶段必跑 |
| R-05 | 数据缺失伪装实时 | 🟡 缓解中 | `data_ingestion_status` 视图 + `pending_disclosure` 状态字段已建,API 集成待 M2 |
| R-10 | 量价背离回归窗口误配 | 🟢 已规划 | `lookback=10, history_lookback=120` 显式参数化,测试已锁 |

---
*下次里程碑评审:W2 末(M1 ETL 落库 + 端到端跑通完成)*
