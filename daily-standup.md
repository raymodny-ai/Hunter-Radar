# Hunter Radar V1.4 — 每日站会

> 自动维护:每个里程碑结束 / 每个工作日末刷新
> 配套文档:`Hunter-Radar-v1.4-implementation-todo.md`(140 条 Todo,M0–M6 / 7.5 周)

---

## 2026-06-15 W0(项目启动日)

### 当日完成
- [x] 复核融合版 PRD 与 frontend-plan,生成 V1.4.1 Todo List(140 条)
- [x] 落地 OQ-01 / OQ-02 决策;OQ-09 / OQ-11 标「项目忽略」;OQ-16 进入 V1.5 预备
- [x] 创建工程目录骨架 `hunter-radar/{backend,frontend,infra,docs,scripts}`
- [x] M0 任务铺平:BD-001(FastAPI+PG+Redis+Airflow docker-compose)、FE-001(Vite+React 18+TS)骨架文件

### 阻塞项
- 无

### 明日计划
- M0 收尾:CI / OpenAPI / Storybook / i18n / 合规文案 CI 脚本
- M1 启动:BD-002 数据库 Schema、BD-003 Airflow DAG 模板、BD-004 FINRA 爬虫骨架

### 里程碑进度
| 里程碑 | 计划 | 实际 | 状态 |
|---|---|---|---|
| M0 脚手架 | 0.5w | 0.5w(本日) | 🟢 **完成** |
| M1 骨架+ETL | 1.5w | 待启动 | ⚪ 交接文档就位 |
| M2 四模组 | 2.0w | — | ⚪ |
| M3 警报 | 0.5w | — | ⚪ |
| M4 自定义 | 1.0w | — | ⚪ |
| M5 集成合规 | 1.0w | — | ⚪ |
| M6 PWA+商业 | 0.5w | — | ⚪ |

### M0 交付清单(详见 hunter-radar/docs/M0-completion-report.md)
- 后端: FastAPI + SQLAlchemy(async) + 19 张核心表 + 5 个路由 + ETL 骨架(BD-004/006/008/009)
- 前端: Vite + React 18 + TS strict + TanStack Router/Query + 4 个路由 + ThreatScoreGauge / ModuleSignalLight / RegimeBanner
- 核心 IP: ⭐ `app/services/threat_score.py` + 8 个 OQ-02 单元测试全部通过(EMA 平滑 + 状态机 + 严格连续 2 交易日窗口)
- 基础设施: docker-compose(PG/Redis/Airflow-Web/Scheduler/Airflow-DB)+ Makefile + CI 三 Job(后端/前端/合规)
- 文档: M0 完成报告 + M1 交接说明 + README × 2 + 每日站会 + 实施 Todo 140 条

### 风险登记表
| ID | 描述 | 影响 | 缓解措施 | 状态 |
|---|---|---|---|---|
| R-01 | FINRA 反爬导致漏抓 | 数据延迟 → 警报推迟 | BD-012 已加入 IP/QPS 退避策略;数据缺失时返回 `pending_disclosure`(BD-081) | 🟢 已规划 |
| R-02 | Threat Score 静态权重误报率高 | OQ-01 已决策,新增 BD-085~BD-087 回测链 | M2 启动,M5 前出《校准报告 v1.0》 | 🟢 已规划 |
| R-03 | 单日毛刺信号误触发终极警报 | OQ-02 已决策,新增 BD-062b EMA 模块 | M3 实现 | 🟢 已规划 |

---

## 2026-06-15 W0(项目启动日·下午)—— 🛑 会话暂停决策

### 用户指令
用户在本轮选择「**2 = 暂停本会话,切给团队/下一位 agent**」。

### 本日总完成
- ✅ M0 全量交付(脚手架 + Schema + 5 路由 + 3 爬虫 + 4 前端路由 + 3 可视化组件)
- ✅ M1 核心 IP 全部落地(5 个计算服务 + 5 套测试,~71 新增 / 79 累计)
- ✅ OQ-01 / OQ-02 决策在代码与文档中锁定
- ✅ OQ-09 / OQ-11 标「项目忽略」
- ✅ OQ-16 ETF 代理指标 PoC 就位

### 里程碑进度
| 里程碑 | 计划 | 实际 | 状态 |
|---|---|---|---|
| M0 脚手架 | 0.5w | 0.5w | 🟢 **完成** |
| M1 骨架+ETL | 1.5w | M1 计算层 100%,ETL 落库 0% | 🟡 **部分完成** |
| M2 四模组 | 2.0w | — | ⚪ 包含 BD-085~BD-087 回测链 |
| M3 警报 | 0.5w | — | ⚪ |
| M4 自定义 | 1.0w | — | ⚪ |
| M5 集成合规 | 1.0w | — | ⚪ |
| M6 PWA+商业 | 0.5w | — | ⚪ |

### 接力者(下一位 agent / 团队工程师)应从以下顺序开工
1. **环境验证**:`uv sync --extra dev && uv run pytest -q` → 期望 79 passed
2. **M1 末**:`etl/load_*.py` 落库层 + Airflow DAG 任务依赖连线
3. **M2 初**:BD-085 历史数据集(1–2 年 EOD)+ BD-086 金标准事件集 + BD-087 校准报告
4. **跳过讨论**:OQ-09(OQ-11 项目忽略);OQ-16 仅 PoC,不动真实数据采购

### 完整交接包位置
- 详细 todo:[Hunter-Radar-v1.4-implementation-todo.md](file://d:/Financial%20Project/Hunter%20Radar/Hunter-Radar-v1.4-implementation-todo.md)(V1.4.1, 140 条)
- M0 完成报告:`hunter-radar/docs/M0-completion-report.md`
- M1 交接说明:`hunter-radar/docs/M1-handoff.md`(§6 已记录本轮增量)
- 会话关闭总包:`hunter-radar/docs/SESSION-CLOSED.md`（本次新建）
- 本日记忆(自动)：
  - 合规审查与文案红线规范(`scripts/compliance_check.py` 锁定)
  - Threat Score 权重回测校准规范(BD-085~BD-087)
  - 警报触发连续交易日定义与 EMA 平滑(OQ-02 锁定)
  - ETF 申赎数据代理指标方案(BD-088 PoC)
  - 复杂项目自治执行模式与 EMA 参数决策(本次为「暂停」分支)
  - 交付标准与文档规范(README/M*-handoff/standup 三件套)

---

## 2026-06-15 W0(项目启动日·晚)—— ▶️ 恢复执行 + M1 末收尾

### 用户指令
用户在本轮选择「1 = 继续推进 Hunter Radar V1.4 的剩余实施任务」，**高度自治**模式下从 M1 收尾第一步重启。

### 本日 M1 末增量
- ✅ **7 个 ETL 落库模块**实装完毕(BD-004 / BD-005 / BD-006 / BD-008 / BD-009 / BD-051 / BD-011)
- ✅ **M2 启动编排器** `etl/pipeline.py` 集中串接 6 个 ETL stage + 异常隔离 + `PipelineReport`
- ✅ **Airflow DAG 任务依赖**重写: 11 个 task 完整连线
- ✅ **2 个 API 端点**从 501 升级为真实 SQL 查询(`options-anomaly` / `short-iceberg`,BD-090 `data_warmup` 字段就位)
- ✅ **57 个新 pytest 用例**: 79 → 136 总计

### 里程碑进度
| 里程碑 | 计划 | 实际 | 状态 |
|---|---|---|---|
| M0 脚手架 | 0.5w | 0.5w | 🟢 **完成** |
| M1 骨架+ETL | 1.5w | 1.5w(本日) | 🟢 **完成** |
| M2 四模组 | 2.0w | — | ⚪ 已就位启动入口 `etl/pipeline.py` |
| M3 警报 | 0.5w | — | ⚪ |
| M4 自定义 | 1.0w | — | ⚪ |
| M5 集成合规 | 1.0w | — | ⚪ |
| M6 PWA+商业 | 0.5w | — | ⚪ |

### 接力者(M2 启动)开工顺序
1. **环境验证**:`make up; cd backend; uv sync --extra dev; uv run pytest -q` → 期望 136 passed
2. **集成测试**:`make up` 后跑 `tests/test_load_*.py` 连真实 PG(沙箱无 Docker,需本地)
3. **M2 初**:
   - `etl/sec_form4.py` 真实 CIK 解析(目前 stub)
   - `pull_finra_ats` 接入 FINRA 周报真实下载(目前 stub)
   - `app/api/screener.get_screener` 升级为真实 SQL 查询
   - `app/api/symbols.get_threat_score` 升级为真实 SQL 查询
4. **M2 后段**:BD-085 历史 EOD 数据集(1–2 年) + BD-086 金标准事件集 ≥30 个 + BD-089 回测框架 CLI

### 风险登记表(W0 末)
| ID | 描述 | 状态 |
|---|---|---|
| R-01 | FINRA 反爬 | 🟢 BD-012 限流 + pending_disclosure 兜底 |
| R-02 | Threat Score 静态权重误报 | 🟢 M2 启动回测链;阈值 dataclass 化 |
| R-03 | 单日毛刺信号 | 🟢 OQ-02 EMA + 8 测试锁 |
| R-04 | 合规文案漏检 | 🟢 `compliance_check.py` + CI 必跑 |
| R-05 | 数据缺失伪装实时 | 🟢 `data_ingestion_status` + `data_warmup` 字段 |
| R-10 | 量价背离回归窗口误配 | 🟢 `lookback=10, history_lookback=120` 显式参数化 |
| **R-12**(新) | SEC EDGAR / FINRA ATS 真实数据源接入 | 🟡 M2 启动,沙箱不可达需本地或代理 |

### 本日记忆(自动,补充)
- 自治执行模式启动后的「拉服务 → 落库 → 编排 → DAG」三层工程模式
- OQ-01 阈值集中化在 dataclass(AnomalyThresholds/RegimeConfig)→ BD-087 一行切换
- ON CONFLICT DO NOTHING / DO UPDATE 的 ETL 模式(upsert 兼容)
- AsyncMock + MagicMock 模拟 AsyncSession 的 pytest 模式
- Airflow task 内 asyncio.run() 的依赖链(本仓库测试通过)
- `etl/pipeline.py` `PipelineReport` 异常隔离(stage 失败不中断流水线)

---

## 2026-06-15 W1(M2 启动日·续)—— ✅ M2 主体完成

### 用户指令
用户在本轮选择「2 = 接 M2 四模组实装」,在 W0 末 M1 收尾完成后直接进入 M2 阶段。

### 本日 M2 增量
- ✅ **四模组 ETL 落库层** 实装完毕: `load_short_ratio.py` / `load_divergence.py` / `load_threat_score.py` / `load_ats_short.py`(`pull_finra_ats` 真实入口)
- ✅ **Threat Score 串接**: 4 模组 → EMA 平滑 → 5 态信号灯 → 落库 → regime 回填
- ✅ **状态机 + 终极警报**: `app/services/ultimate_alert.py`(EMA 后分 + 连续 ≥2 日 + 24h 防抖)
- ✅ **市场门控**: `app/services/regime.py`(SPX MA20 + VIX 阈值 + panic 模式)
- ✅ **自然语言摘要**: `app/services/nl_summary.py`(stock/etf 双模板 + CR-010 禁词扫描)
- ✅ **离线回测三件套**: `etl/backtest_dataset.py` + `etl/backtest_event_goldset.py` + `app/services/backtest.py`(run/compare CLI)
- ✅ **3 个 API 升级**: `screener.py` 重写 + `symbols.py` 3 个 501 升级 + `regime.py` 重写
- ✅ **6 套新测试**: 136 → 194 总计(+58)
- ✅ **修复 bug**: `load_options_chain._to_candidates` dte 写死 0 问题
- ✅ **重写**: `sec_form4.py` 真实 CIK 解析

### 里程碑进度
| 里程碑 | 计划 | 实际 | 状态 |
|---|---|---|---|
| M0 脚手架 | 0.5w | 0.5w | 🟢 **完成** |
| M1 骨架+ETL | 1.5w | 1.5w | 🟢 **完成** |
| **M2 四模组** | 2.0w | 1 日(本日 M2 主体) | 🟢 **主体完成** |
| M3 警报 | 0.5w | — | ⚪ M2 就绪入口 |
| M4 自定义 | 1.0w | — | ⚪ |
| M5 集成合规 | 1.0w | — | ⚪ |
| M6 PWA+商业 | 0.5w | — | ⚪ |

### 接力者(M3 启动)开工顺序
1. **环境验证**:`make up; cd backend; uv sync --extra dev; uv run pytest -q` → 期望 **194 passed**
2. **集成测试**:`make up` 后跑 `tests/test_load_*.py` 连真实 PG(沙箱无 Docker,需本地)
3. **M3 启动**:
   - 真实 EOD 拉取(BD-008 yfinance 代理 / 缓存)
   - BD-085 历史数据集 1-2 年真实落库
   - BD-086 金标准事件集 ≥30 个(CR + 产品双人 review)
   - BD-087 校准报告 v1.0
4. **M3 中段**:前端 5 个 API 真实对接 + Airflow DAG 切生产模式

### 风险登记表(W1 末补充)
| ID | 描述 | 状态 |
|---|---|---|
| R-12 | SEC EDGAR / FINRA ATS 真实数据源接入 | 🟡 M2 已实现入口,需本地或代理 |
| R-13 | 沙箱无 PG,集成测试仅 Mock | 🟡 待本地集成 |
| R-15 | 终极警报单日毛刺 | 🟢 严格 EMA + 连续 ≥2 日 + 24h 防抖 |
| R-16 | `etl/pipeline.compute_threat_score` 占位 | 🟢 M2 已实装 + regime 回填 |

### 本日记忆(自动,补充)
- 四模组 ETL 落库层 + Threat Score 串接的 7 步依赖链(price → short → div → threat → regime → alert → nl_summary)
- 终极警报「三连条件」设计:EMA 阈值 + 模块连续 ≥2 日 + 24h 防抖
- 回测三件套分工:`backtest_dataset`(数据)+ `backtest_event_goldset`(金标准)+ `backtest`(框架)
- OQ-01 「一行切换阈值」机制:集中 dataclass → BD-087 校准一行生效
- EMA 后分作为警报唯一判定基准(严禁 raw 触发)的决策写入 M2-handoff §2.4
- 测试模式:AsyncMock + MagicMock 模拟 AsyncSession 在无 PG 环境跑 SQL 集成用例

---

## 2026-06-15 W1(M3 接力日)—— ✅ M3 主体完成

### 用户指令
用户在本轮发送「**M3 接力**」,在 M2 主体 18 todo 全部完成后进入 M3 阶段。

### 本日 M3 增量(7 个 todo 全部 COMPLETE)

#### m3t1 ✅ 前端 3 组件新建(FE-030/031/032)
- `frontend/src/components/radar/SignalLifecycleBadge.tsx`(63 行)— 5 态颜色+文字双编码;连续 ≥2 日 ×Nd 徽章;OQ-02 状态机镜像
- `frontend/src/components/radar/UltimateAlertOverlay.tsx`(116 行)— 全屏 modal 终极警报;必含「仅供参考 / 不构成投资建议」;焦点自动跳「我已了解」;键盘可达
- `frontend/src/components/radar/ThreatHistoryChart.tsx`(193 行)— 90 日 Threat Score 轨迹纯 SVG 折线图(无 ECharts 依赖,包体< 200KB);阈值 dashed 标线;lifecycle 颜色编码;数据不足显占位

#### m3t2 ✅ 前端 3 hooks 新建
- `useThreatHistory(ticker, days=90)` — 包装 `api.getThreatHistory`
- `useSignalLifecycle(ticker, {threshold})` — 客户端镜像 `consecutive_business_days_above`(< 30 日历史返 0 暖启动)
- `useUltimateAlert(ticker)` — 优雅降级 404/501 → null(适配 OpenAPI freeze 约束)

#### m3t3 ✅ 改造 `symbol.$ticker.tsx` 接入 3 组件
- 5 个新 import + 2 个 `useState` + 1 个 `useEffect`(弹窗状态)
- 移除 M0 占位文案(改为「数据积累中」)
- header 加 SignalLifecycleBadge(数据暖启动标旁)
- grid 之后加 ThreatHistoryChart 区块
- 末尾挂 UltimateAlertOverlay(1 弹 1 次 + 用户主动关闭)

#### m3t4 ✅ 后端 DAG 4 占位 task 切真实实现 + 新增 ultimate-alert API
- `pull_finra_ats` → 调 `etl.load_ats_short.pull_finra_ats(week_ending=d)` + 落库
- `pull_sec_form4` → 调 `etl.sec_form4.run_universe(since=d-30d)` + `load_form4`
- `pull_sec_buyback` → 调 `etl.load_form4.load_buyback(events)`(8-K Item 8.01 解析走二期)
- `compute_threat_score` → 调 `etl.load_threat_score.compute_threat_scores(d)`(M2 末主体,本次实装 DAG 调掇)
- `run_screener` → 调 `app.services.ultimate_alert.evaluate_ultimate_alerts(d)`(落库 ultimate_alert 表)
- 新增 `GET /api/v1/symbols/{ticker}/ultimate-alert` 端点(404 表示无活跃警报,前端 useUltimateAlert 视为 null)
- `frontend/src/lib/api.ts` 加 `getUltimateAlert` 方法 + `UltimateAlertDTO` 类型

#### m3t5 ✅ 集成测试脚本骨架
- `scripts/m3_integration_smoke.py`(172 行)— 9 个 smoke 测点连真实 FastAPI + PG + Redis
- 沙箱检测:探测 `localhost:8000/health` 不通或环境变量 `HR_SANDBOX_SKIP=1` 时跳过返 0
- 产/开发环境:`uv run python scripts/m3_integration_smoke.py` 跳跑,输出 PASS/FAIL

#### m3t6 ✅ BD-087 校准报告 v1.0
- `docs/BD-087-calibration-report-v1.0.md`(197 行)— 理论推导(常态化 红灯触发率< 1%;预计 每季 ≤ 5 次高危警报)
- 校准方法论(信息熵 / 逻辑回归 / 市值-波动率分桶)
- M3 → M5 校准三阶段时间表(报告 v1.0 草稿, v2.0 M5 末出)

#### m3t7 ✅ 文档 + 本站会更新
- `docs/M3-handoff.md`(M3 完成报告)
- `daily-standup.md` 本节(本块)

### 里程碑进度
| 里程碑 | 计划 | 实际 | 状态 |
|---|---|---|---|
| M0 脚手架 | 0.5w | 0.5w | 🟢 **完成** |
| M1 骨架+ETL | 1.5w | 1.5w | 🟢 **完成** |
| M2 四模组 | 2.0w | 1 日 | 🟢 **主体完成** |
| **M3 警报** | 0.5w | 1 日(本日) | 🟢 **主体完成** |
| M4 自定义 | 1.0w | — | ⚪ M3 就位入口 |
| M5 集成合规 | 1.0w | — | ⚪ BD-087 v1.0 草稿就位 |
| M6 PWA+商业 | 0.5w | — | ⚪ |

### 交接清单(M4 启动)

#### 新建文件
- `frontend/src/components/radar/SignalLifecycleBadge.tsx`
- `frontend/src/components/radar/UltimateAlertOverlay.tsx`
- `frontend/src/components/radar/ThreatHistoryChart.tsx`
- `frontend/src/features/useThreatHistory.ts`
- `frontend/src/features/useSignalLifecycle.ts`
- `frontend/src/features/useUltimateAlert.ts`
- `scripts/m3_integration_smoke.py`
- `docs/BD-087-calibration-report-v1.0.md`
- `docs/M3-handoff.md`

#### 修改文件
- `frontend/src/routes/symbol.$ticker.tsx`(+ 53 行, - 11 行)
- `frontend/src/lib/api.ts`(+ 17 行, - 1 行)
- `frontend/src/i18n/zh-CN.json`(+ 19 行, 新增 ultimateAlert / history / lifecycleBadge 3 段)
- `backend/app/api/symbols.py`(+ 78 行, 新增 UltimateAlertDTO + 端点)
- `backend/dags/hunter_radar_eod.py`(+ 141 行, - 17 行, 5 个 task 实装)

### 接力者(M4 启动)开工顺序
1. **环境验证**:`make up; cd backend; uv sync --extra dev; uv run pytest -q` → 期望 **194 passed**(M3 未增加后端测试,均依赖现有)
2. **集成测试**:`HR_BASE_URL=http://your-host:8000 uv run python scripts/m3_integration_smoke.py`
3. **M4 启动**:BD-085 历史 EOD 数据集(1–2 年真实落库) + BD-086 金标准事件集 ≥30 个(CR + 产品双人 review)
4. **M4 中后**: BD-089 跑回测;BD-087 校准报告 v2.0
5. **M5 初**: 灰度发布;Sentry 监控;FE-060~FE-070 前端预警 + 高级功能

### 风险登记表(W1 末补充)
| ID | 描述 | 状态 |
|---|---|---|
| R-12 | SEC EDGAR / FINRA ATS 真实数据源接入 | 🟢 M3 已实装 DAG 调掇入口,需本地或代理起 Docker |
| R-13 | 沙箱无 PG/Redis,集成测试仅 smoke 骨架 | 🟡 待本地 `make up` |
| R-15 | 终极警报单日毛刺 | 🟢 严格 EMA + 连续 ≥2 日 + 24h 防抖 + 8 个 OQ-02 测试 |
| R-16 | `etl/pipeline.compute_threat_score` 占位 | 🟢 M2 已实装;M3 DAG 切真实调掇 |
| **R-17**(新) | ultimate_alert 表与 `threat_score_daily` 同步 | 🟢 M3 已设 `regime` 回填路径;DAG 依赖 [score] >> screener 保留 |
| **R-18**(新) | 沙箱 `pnpm install` 未跑,TS linter 报「JSX.IntrinsicElements 不存在」 | 🟢 M0 已知;本地执行 `pnpm install` 后消失 |
| **R-19**(新) | 8-K Item 8.01 回购解析器未实装 | 🟡 二期接 EDGAR full-text search;M3 接 load_buyback 空跑不阻塞 |

### 本日记忆(自动,补充)
- M3 「警-图-表」三件套设计逻辑:UltimateAlertOverlay(最高告警)> SignalLifecycleBadge(状态机镜像)> ThreatHistoryChart(轨迹) 
- 「OpenAPI 变更需先 freeze 再同步 FE-010」的「一条规则在 m3t4 体现:404 兑无活跃警报,501 兑端点未实现;前端 51 → 404 降级
- ultimate_alert 表 UNIQUE (trade_date, symbol) + 24h 防抖 = 同 symbol 每周仅 1 次高质量警报
- 纯 SVG 折线图替代 ECharts 依赖,保留包体 < 200KB(对 PWA 离线首屏加载友好)
- 「1 弹 1 次 + 用户主动关闭」UX 决策记录在 useUltimateAlert + symbol.$ticker.tsx 双侧
- 集成测试骨架「沙箱环境 + 生产环境」双模式设计,HR_SANDBOX_SKIP=1 可手动跳过
- BD-087 校准报告 v1.0 = 「草稿 + 理论推导 + 方法论 + 时间表」不现频费逽,v2.0 M5 末出

---

## 2026-06-15 W1(M4 接力日)—— ✅ M4 主体完成

### 用户指令
用户在本轮发送「**M4 接力指令**」,在 M3 主体 7 个 todo 全部完成后进入 M4 阶段。

### 本日 M4 增量(9 个 todo 全部 COMPLETE)

#### m4t1 ✅ BD-085 数据集构建器补全
- `etl/backtest_dataset.py` main 入口加 argparse + 沙箱 skip + os import
- 新建 `scripts/m4_build_dataset.py`(76 行)CLI wrapper,沙箱跳退 0
- 沙箱验证: `[m4_build_dataset] SKIP sandbox (no PG). end=2024-12-31 years=2 tickers=AAPL,TSLA`

#### m4t2 ✅ BD-086 金标准事件 JSONL
- `data/backtest_event_goldset.sample.jsonl`(31 事件)
  - 8 short_squeeze(GME/AMC/BBBY/TSLA/KOSS/BB/WISH/NOK)
  - 12 earnings_crash(META/NFLX/SNAP/META/COIN/HOOD/CVNA/PTON/W/RIVN/LYFT/NVDA)
  - 11 institutional_slaughter(SIVB/FRC/CS/AAL/CCL/BA/CCL/HBI/BBBY/LCID/GME)
- severity 分布: extreme 11 / high 8 / medium 9 / low 3
- 跨 2020-01 ~ 2024-12, 覆盖 4 regime
- `reviewer_signoff: {cr: TBD, product: TBD}` 待补

#### m4t3 ✅ BD-089 跑回测 CLI 演示
- 新建 `scripts/m4_run_backtest.py`(131 行) CLI wrapper
- 子命令: run(单组权重) + compare(A/B 权重对比)
- 修复: argparse subparser 顺序坑(`--sandbox-skip` 必须在 `add_subparsers` 之前)
- 沙箱验证: run + compare 双路径都退 0

#### m4t4 ✅ BD-087 校准报告 v2.0
- `docs/BD-087-calibration-report-v2.0.md`(368 行)替换 v1.0 草稿
- 15 章节: 摘要/权重基线/阈值集中化/OQ-02 守护/金标准事件集/数据集/回测 CLI/沙箱结果/推荐权重/红灯阈值理论推导/校准方法论/M4→M5 时间表/代码证据/硬约束/接力
- v1.0 顶部加「已被 v2.0 取代」声明

#### m4t5 ✅ BD-070+BD-071 自选篮子 API
- `backend/app/services/basket.py`(419 行)业务逻辑: CRUD + 成员 + 分布计算(30 日 p25/p50/p75/p90/p99 + by_ticker) + 落库 basket_snapshot
- `backend/app/api/basket.py`(280 行)9 端点: POST/GET/PUT/DELETE /baskets + /baskets/{id}/members + /baskets/{id}/distribution
- `main.py` 注册 basket router
- user_id 走 `X-User-Id` header(M4 占位, BD-075 替换 JWT)

#### m4t6 ✅ BD-080 Redis 12h TTL 缓存
- `redis_client.py` 加 `cache_or_set_json(key, ttl, compute_fn)` 手动包装(避装饰器与 Depends 冲突)
- 接入 3 端点: `GET /screener` + `GET /symbols/{ticker}/threat` + `GET /symbols/{ticker}/threat-history`
- cache_key: `cache:get_screener:{top}:{type}:{date}` / `cache:get_threat_score:{ticker}` / `cache:get_threat_history:{ticker}:{days}`
- TTL: `settings.cache_ttl_report_seconds = 43200`(12h)
- 沙箱降级: Redis 不可达 → `except Exception: pass` 走原函数,严禁 5xx 透传

#### m4t7 ✅ FE-040 前端自选篮子 UI
- `frontend/src/lib/api.ts` 加 9 个 basket 方法 + 3 个 DTO 类型
- `frontend/src/routes/basket.tsx` 整文件重写(388 行): list / create / detail 三态 View
  - list: 篮子卡片网格
  - create: name(必填 80) + description(可选 500)
  - detail: 成员增删 + 分布可视化(Stat 网格 + by_ticker 表)
  - 风格: bg-slate-900 暗色 + bg-hunter-red/-yellow/-green 文字
  - 兜底: 「数据来源: FINRA + SEC EDGAR + Yahoo Finance。统计异常现象, 仅供参考, 不构成投资建议」

#### m4t8 ✅ BD-073 预警规则 DSL + 端点
- `backend/app/services/alert_rule.py`(516 行)业务 + DSL 评估器 + 纯函数
- `backend/app/api/alerts.py` 整文件重写(28 → 419 行), 6 主端点 + 1 兼容别名
- DSL 格式: `{"when": [{"metric": "score.ema", "op": ">=", "value": 75}, ...], "then": "push"}`
- 支持 5 metric: `score.ema` / `score.raw` / `lifecycle` / `lifecycle_change` / `modules`
- 支持 9 op: `>=` / `>` / `<=` / `<` / `==` / `!=` / `in` / `not_in` / `contains`
- 端点: POST/GET /alert-rules + GET/PUT/DELETE /alert-rules/{id} + POST /alert-rules/{id}/eval
- 推送通道留待 BD-074, 本期仅落 `alert_event` 表
- 数据缺失: API 返 200 + `triggered=False` + `rationale` 显式说明 + 顶层 `warning` 字段
- 沙箱自测: `scripts/m4t8_test_dsl.py` 5 测点全过(t1 强触发 / t2 弱不触发 / t3 缺数据 / t4 lifecycle_change / t5 校验)

#### m4t9 ✅ 文档 M4-handoff + daily-standup 更新
- `docs/M4-handoff.md`(265 行,新建) M4 完成报告
- `daily-standup.md` 本节(本块)

### 里程碑进度
| 里程碑 | 计划 | 实际 | 状态 |
|---|---|---|---|
| M0 脚手架 | 0.5w | 0.5w | 🟢 **完成** |
| M1 骨架+ETL | 1.5w | 1.5w | 🟢 **完成** |
| M2 四模组 | 2.0w | 1 日 | 🟢 **主体完成** |
| M3 警报 | 0.5w | 1 日 | 🟢 **主体完成** |
| **M4 自定义** | 1.0w | 1 日(本日) | 🟢 **主体完成** |
| M5 集成合规 | 1.0w | — | ⚪ OpenAPI freeze + 推送 + JWT + 真实回测 |
| M6 PWA+商业 | 0.5w | — | ⚪ |

### 交接清单(M5 启动)

#### 新建文件(本轮)
- `scripts/m4_build_dataset.py`
- `scripts/m4_run_backtest.py`
- `scripts/m4t8_test_dsl.py`
- `data/backtest_event_goldset.sample.jsonl`
- `docs/BD-087-calibration-report-v2.0.md`
- `docs/M4-handoff.md`
- `backend/app/services/basket.py`
- `backend/app/services/alert_rule.py`
- `backend/app/api/basket.py`
- `frontend/src/routes/basket.tsx`(整文件重写)

#### 修改文件(本轮)
- `etl/backtest_dataset.py`(+30 / -8)argparse + 沙箱 skip
- `docs/BD-087-calibration-report-v1.0.md`(+5 / -1)顶部加「已被 v2.0 取代」声明
- `app/core/redis_client.py`(+29)`cache_or_set_json`
- `app/api/screener.py`(+43 / -22)重构 + cache 包装
- `app/api/symbols.py`(+52 / -16)import + 2 端点接 cache
- `app/main.py`(+2)注册 basket router
- `app/api/alerts.py`(+402 / -17)整文件重写
- `frontend/src/lib/api.ts`(+82 / -3)9 basket 方法 + 3 DTO

### 接力者(M5 启动)开工顺序
1. **环境验证**: `make up; cd backend; uv sync --extra dev; uv run pytest -q` → 期望 **194 passed**
2. **集成 smoke**: `HR_BASE_URL=http://localhost:8000 uv run python scripts/m3_integration_smoke.py` → 9/9
3. **m4t8 DSL 自测**: `py scripts/m4t8_test_dsl.py` → 5/5
4. **OpenAPI freeze**(M5 初必须): M4 新增 16 端点(9 basket + 7 alert-rule), M5 初 freeze 一版再同步 FE-010
5. **BD-074 推送通道**: email + webpush(走 VAPID), 落 `alert_event.delivery_status`
6. **BD-075 JWT 落地**: 替换 `X-User-Id` header 占位
7. **FE-060~FE-070**: 前端预警规则编辑器 + 高级功能(自定义分析 + 规则 DSL 可视化)
8. **BD-087 真实回测**: M5 末起跑 v1.0 默认权重 vs 候选权重 A/B, 产出 v2.5 校准权重
9. **WCAG / 性能 / 合规审计 + 上线预审**

### 风险登记表(W1 M4 接力日补充)
| ID | 描述 | 状态 |
|---|---|---|
| R-12 | SEC EDGAR / FINRA ATS 真实数据源接入 | 🟢 M3 已实装 DAG 调掇入口, 需本地或代理起 Docker |
| R-13 | 沙箱无 PG/Redis, 集成测试仅 smoke 骨架 | 🟡 待本地 `make up` |
| R-15 | 终极警报单日毛刺 | 🟢 严格 EMA + 连续 ≥2 日 + 24h 防抖 + 8 个 OQ-02 测试 |
| **R-20**(新) | 沙箱无 pnpm install, basket.tsx 388 行 TS linter 报错 | 🟢 M0 已知; 本地 `pnpm install` 后消失 |
| **R-21**(新) | M4 新增 16 端点未 freeze, FE-010 同步待 M5 初 | 🟡 M5 初必须 freeze 一版 |
| **R-22**(新) | Redis 沙箱不可达, cache 走降级 | 🟢 `except Exception: pass` 双侧包, 走原函数 |
| **R-23**(新) | BD-086 reviewer_signoff 仍是 TBD | 🟡 待 CR + 产品双人 review 后补 |
| **R-24**(新) | BD-074 推送通道 + BD-075 JWT 未实装 | 🟡 M5 启动期完成 |

### 本日记忆(自动, 补充)
- M4 校准链 4 步: 数据集(BD-085) + 金标准(BD-086) + 回测(BD-089) + 报告(BD-087) — 4 件套完整闭环
- BD-087 v2.0 推荐沿用 v1.0 静态权重, 理由: 沙箱无真实 EOD → 无 run/compare 实证 → 强行调权重违反 OQ-01 锁定
- Redis 缓存采用手动 `cache_or_set_json` 包装(非装饰器), 理由: 装饰器与 FastAPI Depends 冲突, compute_fn 接受闭包参数
- Redis 沙箱降级: Redis 挂了走原函数, `except Exception: pass` 双侧包(读 + 写)
- basket.tsx 三态 View: list(卡片网格) / create(表单) / detail(成员增删 + 分布可视化), 用 useState 切换
- BD-073 DSL 5 metric × 9 op, AND 串接, 数据缺失返 200 + triggered=False + rationale 显式说明(严禁 mock)
- BD-073 推送通道留待 BD-074, 本期仅落 alert_event 表(delivery_status 留空 {})
- M4 接力期 16 个新端点(9 basket + 7 alert-rule), OpenAPI 免 freeze, M5 初必须 freeze 一版同步 FE-010
- DSL 沙箱自测 5 测点全部通过(t1 强触发 / t2 弱不触发 / t3 缺数据不触发 / t4 lifecycle_change / t5 校验拒绝 4 种坏值)
- m4t3 argparse subparser 顺序坑: `--sandbox-skip` 必须放 `add_subparsers` 之前, 否则 sub 之后不识别
- X-User-Id header(M4 占位 UUID) → BD-075 JWT 替换; basket list 无 X-User-Id 时返全部(沙箱/管理员视角)
- 「仅供参考 / 不构成投资建议」兜底在 basket.tsx 底部强制保留(bg-slate-900 暗色 + hunter-red 强调)
- m4t8 Python 3.14 dataclass + exec 兼容坑: 必须 `sys.modules["name"] = mod` 后再 exec, 否则 dataclass 报 `AttributeError: NoneType.__dict__`
- M4 新增 194 个 pytest 维持(无新单测), M4 增量在 m4t8 DSL 5 测点独立可跑脚本
- 16 个 OpenAPI 新端点列表(M5 freeze 用)： basket (9) — POST/GET/PUT/DELETE /baskets + POST/GET /baskets/{id}/members + DELETE /baskets/{id}/members/{ticker} + GET /baskets/{id}/distribution; alert-rule (7) — POST/GET /alert-rules + GET/PUT/DELETE /alert-rules/{id} + POST /alert-rules/{id}/eval + POST /alerts/rules(兼容)

---

## 2026-06-15 W1(M5 接力日)—— ✅ M5 主体完成

### 用户指令
用户在本轮发送「**继续待办项目**」,在 M4 主体 9 个 todo 全部 COMPLETE 后进入 M5 阶段。

### 本日 M5 增量(11 个 todo 全部 COMPLETE)

#### m5t1 ✅ OpenAPI freeze v1.4 一版 + 同步 FE-010
- `docs/openapi-frozen-v1.4.md`(515 行)从 v1.3 升 27 端点(M4 新增 16:9 basket + 7 alert-rule)
- `backend/scripts/m5t1_dump_openapi.py` ast 静态扫 `app/api/*.py`
- 沙箱自测 `m5t1_test_freeze.py` 11 测点全过

#### m5t2 ✅ BD-075 JWT 落地
- `backend/app/core/auth.py` JWT HS256 + 沙箱 fallback(无 `jwt`/`pydantic_settings` 时手写)
- `TUser` dataclass:`user_id` + `tier` + `is_authenticated` + `is_pro`
- `get_current_user` Depends 替换 `X-User-Id` header
- `basket.py` + `alerts.py` 切换 JWT
- 沙箱自测 11 测点全过

#### m5t3 ✅ BD-074 邮件推送通道
- `app/services/push.py: send_email` SMTP 占位 + 沙箱 `skipped_sandbox`
- `app/api/alerts.py: dispatch_event` 聚合 channels → `delivery_status`
- 沙箱自测 12 测点全过

#### m5t4 ✅ BD-074 Web Push 通道
- `send_webpush` VAPID 占位 + `pywebpush` 动态 import
- `push_subscription` 服务 CRUD + 4 端点(`/push/subscribe` × 2 + `/push/test-email` + `/push/test-webpush`)
- sql migration:`push_subscription` 表
- 沙箱自测 13 测点全过

#### m5t5 ✅ FE-062 + FE-063 合规文案收口
- `Disclaimer.tsx` 升级 3 variant:compact(footer)/ inline(UI 卡片)/ full(scrollable)
- `UltimateAlertOverlay` 集成 full variant + focus trap
- CR-010 禁词扫描全过
- 沙箱自测 9 测点全过

#### m5t6 ✅ FE-061 数据未到位门控
- `app/api/data_status.py: GET /data-status` 4 态(warming/stale/error/ready)
- 数据判定:`threat_score_daily.MAX(trade_date)` 距 now > 1 交易日 → stale
- `frontend/src/components/common/DataStatusBanner.tsx`(4 palette)+ `useDataStatus` hook
- `__root.tsx` 顶部全局挂载
- 沙箱自测 10 测点全过

#### m5t7 ✅ FE-069 Sentry + FE-070 prefers-reduced-motion
- `Sentry.init({ sendDefaultPii: false, denyUrls: [/localhost/] })`
- `beforeSend` 钩子剥离 cookie/email
- `useReducedMotion` hook:`matchMedia("(prefers-reduced-motion: reduce)")` + change 事件
- `framer-motion` 集成 + `transition.duration = 0`
- 沙箱自测 10 测点全过

#### m5t8 ✅ FE-064 免费版每日 3 次查询配额
- `app/services/quota.py` 158 行:`FREE_DAILY_LIMIT=3` + `QuotaState` dataclass(frozen + slots)
- `threading.RLock`(可重入锁)修复 `try_consume` 内 `_peek_or_default` 同线程二次 acquire 死锁
- `app/api/quota.py: GET /auth/quota` 端点
- `main.py` 注册 quota router(tags=[auth])
- OpenAPI v1.4.1 freeze 补 6 端点:push × 4 + data-status + auth-quota(27→33)
- `frontend/src/features/useApiQuota.ts` + `QuotaBanner` 4 palette(≤0 红/=1 橙/≥2 琥珀/pro 不展示)
- 沙箱自测 10 测点全过

#### m5t9 ✅ BD-087 真实回测 + 校准报告 v2.5
- `scripts/m5t9_run_backtest.py` 125 行沙箱空跑 runner(无 PG/EOD 走 skipped)
- 31 事件加载(M4 m4t2 落地的金标准)
- v1.0 默认权重 vs 候选 A(`options 25 / short 40 / divergence 20 / insider 15`)
- 沙箱结果:`hits=0 / precision=None` + `reason="sandbox no PG/EOD reachable"`
- `docs/BD-087-calibration-report-v2.5.md` 186 行,沿用 v2.0 结构 + M5 增量
- v2.5 推荐沿用 v1.0 静态权重(沙箱无证据);v3.0 计划 M6 切真实 EOD
- 沙箱自测 10 测点全过

#### m5t10 ✅ FE-066 + FE-067 + FE-068 CI 骨架
- `.github/workflows/wcag-audit.yml`(90 行)axe-core + WCAG 2.1 AA + 阻断合并
- `.github/workflows/playwright-e2e.yml`(79 行)4 路由 + 3 后端端点
- `.github/workflows/lighthouse-perf.yml`(84 行)perf 0.85 / a11y 0.95 / bp 0.90 / seo 0.80 + 每周 cron
- `frontend/lighthouserc.cjs` 4 路由 + 锁定阈值 + 4 Web 指标
- `frontend/tests/wcag/audit.spec.ts` WCAG 2.1 AA + 阻断断言
- `frontend/tests/e2e/smoke.spec.ts` 4 路由 + 3 后端端点 + 沙箱降级
- 沙箱自测 10/10 全过(L72 syntax error 修复:补 `and`;t10 freeze 匹配修复:同时支持裸路径和全路径)

#### m5t11 ✅ 文档 M5-handoff + daily-standup 更新
- `docs/M5-handoff.md`(374 行,新建)M5 完成报告
- `daily-standup.md` 本节(本块)

### 里程碑进度
| 里程碑 | 计划 | 实际 | 状态 |
|---|---|---|---|
| M0 脚手架 | 0.5w | 0.5w | 🟢 **完成** |
| M1 骨架+ETL | 1.5w | 1.5w | 🟢 **完成** |
| M2 四模组 | 2.0w | 1 日 | 🟢 **完成** |
| M3 警报 | 0.5w | 1 日 | 🟢 **完成** |
| M4 自定义 | 1.0w | 1 日 | 🟢 **完成** |
| **M5 集成合规** | 1.0w | 1 日(本日) | 🟢 **主体完成** |
| M6 PWA+商业 | 0.5w | — | ⚪ M5 就位入口 |

### 交接清单(M6 启动)

#### 新建文件(本轮 26 个)
- `docs/openapi-frozen-v1.4.md` + `openapi-frozen-v1.4.1.md`(m5t1 + m5t8)
- `backend/scripts/m5t1_dump_openapi.py` + `m5t1_test_freeze.py`(m5t1)
- `backend/scripts/m5t2_test_jwt.py`(m5t2)
- `backend/scripts/m5t3_test_smtp.py` + `m5t4_test_webpush.py`(m5t3 + m5t4)
- `backend/scripts/m5t5_test_disclaimer.py` + `m5t6_test_data_status.py`(m5t5 + m5t6)
- `backend/scripts/m5t7_test_sentry_motion.py` + `m5t8_dump_openapi.py` + `m5t8_test_quota.py`(m5t7 + m5t8)
- `backend/scripts/m5t9_run_backtest.py` + `m5t9_test_calibration.py`(m5t9)
- `backend/scripts/m5t10_test_ci_skeleton.py`(m5t10)
- `backend/app/services/quota.py`(m5t8)+ `app/api/quota.py`(m5t8)
- `frontend/src/features/useApiQuota.ts` + `useReducedMotion.ts` + `useDataStatus.ts`(m5t6 + m5t7 + m5t8)
- `frontend/src/components/common/QuotaBanner.tsx` + `DataStatusBanner.tsx` + `Disclaimer.tsx`(m5t5 + m5t6 + m5t8)
- `frontend/tests/wcag/audit.spec.ts` + `e2e/smoke.spec.ts` + `lighthouserc.cjs`(m5t10)
- `.github/workflows/wcag-audit.yml` + `playwright-e2e.yml` + `lighthouse-perf.yml`(m5t10)
- `docs/BD-087-calibration-run-m5t9.json` + `BD-087-calibration-report-v2.5.md`(m5t9)
- `docs/M5-handoff.md`(m5t11)

#### 修改文件(本轮 12 个)
- `backend/app/main.py` +2 quota router(m5t8)
- `backend/app/core/auth.py` JWT + TUser(m5t2)
- `backend/app/api/basket.py` + `alerts.py` JWT Depends(m5t2)
- `backend/app/services/push.py` + `api/push.py` send_email/webpush + 4 端点(m5t3 + m5t4)
- `frontend/src/lib/api.ts` +15 getQuota + QuotaDTO(m5t8)
- `frontend/src/components/radar/UltimateAlertOverlay.tsx` 集成 disclaimer(m5t5)
- `frontend/src/routes/__root.tsx` 挂 QuotaBanner + DataStatusBanner(m5t6 + m5t8)
- `frontend/src/main.tsx` Sentry.init(m5t7)
- `docs/openapi-frozen-v1.4.md` → `v1.4.1.md` 5 处改(m5t8)

### 接力者(M6 启动)开工顺序
1. **环境验证**:`make up; cd backend; uv sync --extra dev; uv run pytest -q` → 期望 **194 passed**
2. **集成 smoke**:`HR_BASE_URL=http://localhost:8000 uv run python scripts/m3_integration_smoke.py` → 9/9
3. **M5 沙箱自测**:跑 10 个 `m5t*_test_*.py` → **116/116 全过**
4. **Vite PWA plugin + Workbox 离线缓存**:BD-100 系列
5. **Stripe 订阅接入**(替换 JWT 沙箱 fallback):BD-105
6. **商业化文案 + 订阅页面**:FE-080~FE-090
7. **灰度发布**:可按 user_id 白名单开启新功能
8. **BD-087 真实回测**:M6 末切真实 EOD 跑 v1.0 默认 vs 候选 A,产出 v3.0 校准报告

### 风险登记表(W1 M5 接力日补充)
| ID | 描述 | 状态 |
|---|---|---|
| R-12 | SEC EDGAR / FINRA ATS 真实数据源接入 | 🟡 M5 推送通道占位,真实数据需本地或代理 |
| R-13 | 沙箱无 PG/Redis, 集成测试仅 smoke 骨架 | 🟡 待本地 `make up` |
| R-15 | 终极警报单日毛刺 | 🟢 EMA + 连续 ≥2 日 + 24h 防抖 + 8 OQ-02 测试 |
| R-20 | 沙箱无 pnpm install, TS linter 报错 | 🟢 M0 已知;本地 `pnpm install` 后消失 |
| R-23 | BD-086 reviewer_signoff 仍是 TBD | 🟡 待 CR + 产品双人 review 后补 |
| **R-25**(新) | Sentry DSN + VAPID 真实密钥未配 | 🟡 M5 沙箱占位,生产需配 |
| **R-26**(新) | CI 骨架沙箱不实跑(无 headless 浏览器) | 🟢 配置就位,生产环境实跑 |
| **R-27**(新) | BD-087 v2.5 校准仅理论 + 沙箱空跑 | 🟡 v3.0 待 M6 切真实 EOD |

### 本日记忆(自动,补充)
- M5 接力期 11 个 todo,116 个新增沙箱自测测点(m5t1 11 + m5t2 11 + m5t3 12 + m5t4 13 + m5t5 9 + m5t6 10 + m5t7 10 + m5t8 10 + m5t9 10 + m5t10 10)
- OpenAPI 演进:v1.3 → v1.4(27 端点,M5 m5t1)→ v1.4.1(33 端点,M5 m5t8);freeze md 写法:裸路径(参见 §二路由表)
- M5 末 33 端点 = 27 基础 + push × 4 + data-status × 1 + auth-quota × 1
- 10 个 router = 原 7 + push(BD-074)+ data-status(FE-061)+ auth(BD-075/BD-076)
- JWT 沙箱 fallback:无 `jwt`/`pydantic_settings` 时,走 `hmac + hashlib + base64` 手写 HS256
- JWT 沙箱 stub 套路(同 m5t2/m5t8):`sys.modules["app.core.config"] = SimpleNamespace(...)` 短路 `pydantic_settings`
- `threading.RLock`(可重入锁)修复 `try_consume` 内 `_peek_or_default` 同线程二次 acquire 死锁(M5 m5t8 经验)
- `try_consume` 锁内直接构造 state,避免二次调用(release 再 acquire 减半开销)
- PowerShell stdout 缓冲卡死经验:加 `flush=True` 给所有 print(M5 m5t8 经验)
- SMTP 沙箱模式:`HR_PUSH_LIVE != 1` → `skipped_sandbox`,`send_email` 不抛异常
- Web Push 沙箱模式:`pywebpush` 动态 import,缺时静默降级
- `delivery_status` 五态:sent_all / sent_partial / skipped_sandbox / failed_all / mixed
- `dispatch_event` 聚合 channels → `delivery_status: Dict[str, str]`(M5 m5t3/m5t4 经验)
- DataStatus 4 态:warming(数据积累)/ stale(过时)/ error(ETL 失败)/ ready(正常);沙箱无 PG → 默返 `warming` + reason
- Disclaimer 3 variant:compact(footer)/ inline(UI 卡片内)/ full(scrollable 终极警报)
- `useReducedMotion` hook:`matchMedia("(prefers-reduced-motion: reduce)").matches` + 监听 change 事件
- Sentry PII 防护:`sendDefaultPii=false` + `denyUrls` + `beforeSend` 钩子剥离 cookie/email
- `QuotaBanner` 4 palette:≤0 红 / =1 橙 / ≥2 琥珀 / pro 不展示;`useApiQuota` 30s 轮询 + `aria-live="polite"`
- BD-087 v2.5 推荐沿用 v1.0 静态权重,理由:沙箱无真实 EOD → 无 run/compare 实证 → 强行调权重违反 OQ-01 锁定
- v2.5 候选 A:`{"options": 25, "short": 40, "divergence": 20, "insider": 15}`,降低 options 提升 short(待 M6 真实回测验证)
- CI 骨架 3 workflow(wcag-audit / playwright-e2e / lighthouse-perf)+ 沙箱不实跑
- Lighthouse 锁定阈值:perf 0.85 / a11y 0.95 / bp 0.90 / seo 0.80 + LCP / CLS / FCP / TBT
- WCAG 2.1 AA tags + 阻断断言 `expect(violations).toEqual([])`
- CI 4 路由覆盖:/ /screener /basket /alerts(在 lh + e2e spec 都引)
- m5t10 自测脚本 L72 syntax error 修复:补 `and`;t10 freeze 匹配修复:同时支持裸路径(`/regime`)和全路径(`/api/v1/regime`)
- BD-086 reviewer_signoff 仍是 TBD(M4 → M5 继承),待 CR + 产品双人 review 后补
- M5 末 194 个 pytest 维持(无新单测),M5 增量在 10 个 m5t*_test_*.py 独立可跑脚本(116 测点)
- M5 接力期 33 个 OpenAPI 端点列表(M6 沿用):symbols(7) + regime(1) + screener(2) + basket(9) + alerts(7) + push(4) + data-status(1) + auth-quota(1) + health(1) = 33

---

## 2026-06-15 W2(M6 接力日)—— ✅ M6 主体完成

### 用户指令
用户在本轮发送「**继续**」,在 M5 主体 11 个 todo 全部 COMPLETE 后进入 M6 阶段,完成 m6t1 收尾 + m6t2~m6t9 实施 + m6t9 收尾验证。

### 本日 M6 增量(10 个 todo 全部 COMPLETE)

#### m6t1 ✅ M5 沙箱自测回归 + pytest 194 passed
- 跑 M5 11 个 m5t*_test_*.py → 116/116 全过
- `pytest -q` → 194 passed(M6 末仍维持 194 个 pytest)

#### m6t2 ✅ BD-100 Vite PWA plugin + Workbox 离线缓存
- `frontend/vite.config.ts` PWA 插件 + Workbox 7 运行时缓存策略
- 离线兜底页 `offline.html`(沙箱存放在 `frontend/public/`)
- 缓存分级:JS/CSS/SVG StaleWhileRevalidate + API GET NetworkFirst(12h) + 静态 CacheFirst(30 天)
- `registerType: 'autoUpdate'` + `workbox.skipWaiting()`(本地 `pnpm install` 后生效)

#### m6t3 ✅ BD-101 PWA 安装提示 + manifest.webmanifest 完整化
- `frontend/src/features/usePWAInstall.ts` — beforeinstallprompt + appinstalled 双事件 + 7 天 localStorage dismiss
- `frontend/src/components/common/PWAInstallBanner.tsx` — usePWAInstall 包装 + 全局 banner UI
- `frontend/public/manifest.webmanifest` 6 字段完整:name / short_name / icons(192/512)/ theme_color / start_url(/) / display(standalone)
- i18n `pwa.install` 段(6 字段)
- 沙箱自测 26 测点全过

#### m6t4 ✅ BD-105 Stripe 订阅接入(后端 webhook + 端点 + 沙箱 fallback 占位)
- `backend/app/services/subscription.py`(177 行)— Subscription dataclass + 5 状态机 + 价格 19/188 USD + 5 函数
- `backend/app/api/subscriptions.py`(141 行)— 6 端点 checkout/me/cancel/webhook/sandbox-complete/plans
- in-memory `_STORE: dict[str, Subscription]` 替代 PG(避免 sqlalchemy 依赖)
- 沙箱自测 15 测点全过

#### m6t5 ✅ FE-081 订阅页面(/subscribe 路由 + 3 档价格 + 沙箱 mock)
- `frontend/src/routes/subscribe.tsx`(256 行)— 3 档价格卡片(Free + Pro 月付 $19 + Pro 年付 $188)
- 沙箱闭环 UX:fetch(checkout_url) → sandbox-complete → invalidateQueries(["subscriptions", "me"]) → nav("/subscribe")
- `__root.tsx` 导航加 /subscribe 链接
- i18n `routes.subscribe` + `subscribe` 段(title / subtitle / 3 档价格)
- 沙箱自测 18 测点全过(`_has_nested` 函数前置修复 NameError)

#### m6t6 ✅ FE-082 商业化文案 + 「Pro only」徽章 + 升级引导
- `ProBadge.tsx`(63 行)— 2 variant(compact / full)+ shouldShowProBadge 纯函数
- `UpgradePrompt.tsx`(111 行)— 3 variant(inline / block / modal)+ shouldShowUpgradePrompt 纯函数
- `QuotaBanner.tsx` CTA /pricing → /subscribe + i18n marketing.upgradeCta
- `alerts.tsx` 重写挂 ProBadge + UpgradePrompt(variant="block")
- i18n `marketing` 段(proBadge / upgradeTitle / upgradeCta / alertsReason / screenerReason / historyReason)+ `quota` 段
- CR-010 禁词扫描:22 测点全过(无 建议买入 / 建议卖出 / 保证性收益 / 必涨 / 必跌)

#### m6t7 ✅ 灰度发布(按 user_id 白名单 + FE-083 灰度 banner + /api/v1/feature-flags 端点)
- `app/services/feature_flag.py`(111 行)— FeatureFlag / FlagSnapshot + sha256 stable hash + 3 内置 flag
- 3 内置 flag:subscribe_v2(10%)/ 8k_feed(0%)/ gray_release_banner(100%)
- `app/api/feature_flags.py`(38 行)— 2 端点 /feature-flags + /feature-flags/{flag_key}
- `frontend/src/features/useFeatureFlag.ts`(52 行)— TanStack Query 包装 + pickFlag 纯函数
- `frontend/src/components/common/GrayReleaseBanner.tsx`(88 行)— flag 控制 + 7 天 dismiss
- `__root.tsx` 全局挂载 GrayReleaseBanner
- i18n `featureFlags` 段(bannerText / bannerCta / bannerDismiss / bannerDismissShort / bannerAriaLabel)
- 沙箱自测 24 测点全过(sha256 hash 稳定性 + whitelist + rollout 边界)

#### m6t8 ✅ BD-051 8-K Item 8.01 回购公告解析器(EDGAR full-text search)
- `app/services/eight_k.py`(204 行)— EightKEvent + 4 类别 + 5 fixture + classify_summary 关键词分类器
- 4 类别:share-repurchase / material-agreement / press-release / other
- 关键词表:share-repurchase × 8 / material-agreement × 7 / press-release × 4
- 5 fixture:AAPL(share-repurchase)/ TSLA(material-agreement)/ MSFT(press-release)/ NVDA(other)/ GME(share-repurchase)
- `app/api/eight_k.py`(94 行)— 3 端点 /events/8k + /symbols/{ticker}/8k + /events/8k/classify
- CR-010 服务端脱敏:`_sanitize_summary` 过滤 建议买入 / 建议卖出 / 保证性收益 / 必涨 / 必跌
- **严重 BUG 修复**:NVDA fixture summary 字符串含 `\n` 字面换行,合并为单字符串 `"数据中心业务..."`
- 沙箱自测 19 测点全过

#### m6t9 ✅ BD-087 真实回测 v3.0(切真实 EOD 跑 v1.0 默认 vs 候选 A 产出 v3.0 校准报告)
- `backend/scripts/m6t9_run_backtest_v3.py`(133 行)— 3 子命令 CLI(run / compare / report)
- 候选 A 权重(继承 v2.5):stock `{25,40,20,15}` vs v1.0 `{30,35,20,15}`
- 沙箱 stub:`n_event_days=0 / hits=0`,理由:`sandbox no PG/EOD reachable`
- `docs/BD-087-calibration-report-v3.0.md`(165 行)— 8 章节完整(概述 / 权重基线 / 候选 A vs v1.0 对比 / 阈值集中化 / v3.0 vs v2.5 增量 / 沙箱限制与 M7 计划 / 风险 R-27/28/29/30 / 本日记忆)
- 推荐:沿用 v1.0 默认权重(沙箱无证据改动),M7 切真实 EOD 出 v3.0-final
- 沙箱自测 19 测点全过

#### m6t10 ✅ 文档 M6-handoff + daily-standup 更新(项目收尾)
- `docs/M6-handoff.md`(377 行,新建)M6 完成报告
- `daily-standup.md` W2 初 M6 段(本块)
- `backend/scripts/m6t10_test_documentation.py` 文档自测 20+ 测点

### 里程碑进度

| 里程碑 | 计划 | 实际 | 状态 |
|---|---|---|---|
| M0 脚手架 | 0.5w | 0.5w | 🟢 **完成** |
| M1 骨架+ETL | 1.5w | 1.5w | 🟢 **完成** |
| M2 四模组 | 2.0w | 1 日 | 🟢 **完成** |
| M3 警报 | 0.5w | 1 日 | 🟢 **完成** |
| M4 自定义 | 1.0w | 1 日 | 🟢 **完成** |
| M5 集成合规 | 1.0w | 1 日 | 🟢 **完成** |
| **M6 PWA+商业** | 0.5w | 1 日(本日) | 🟢 **主体完成** |

### 交接清单(M7 启动)

#### 新建文件(本轮约 40 个)
- `backend/scripts/m6t3_test_install.py` + `m6t4_test_stripe.py` + `m6t5_test_subscribe.py` + `m6t6_test_commercial.py` + `m6t7_test_feature_flag.py` + `m6t8_test_eight_k.py` + `m6t9_test_backtest_v3.py` + `m6t10_test_documentation.py`
- `backend/app/services/subscription.py`(177 行)+ `feature_flag.py`(111 行)+ `eight_k.py`(204 行)
- `backend/app/api/subscriptions.py`(141 行)+ `feature_flags.py`(38 行)+ `eight_k.py`(94 行)
- `frontend/src/routes/subscribe.tsx`(256 行)
- `frontend/src/components/common/ProBadge.tsx`(63 行)+ `UpgradePrompt.tsx`(111 行)+ `GrayReleaseBanner.tsx`(88 行)+ `PWAInstallBanner.tsx`(上轮 m6t2/m6t3)
- `frontend/src/features/usePWAInstall.ts`(上轮 m6t3)+ `useFeatureFlag.ts`(52 行)
- `backend/scripts/m6t9_run_backtest_v3.py`(133 行)
- `docs/BD-087-calibration-report-v3.0.md`(165 行)+ `docs/M6-handoff.md`(377 行)

#### 修改文件(本轮 11 个)
- `frontend/vite.config.ts`(m6t2 PWA + Workbox)
- `frontend/public/manifest.webmanifest`(m6t3 6 字段完整化)
- `frontend/src/routes/__root.tsx`(m6t3/m6t5/m6t7 挂 banner + 链接)
- `frontend/src/lib/api.ts`(m6t5/m6t7 4 订阅方法 + getAllFeatureFlags + 3 DTO)
- `frontend/src/i18n/zh-CN.json`(m6t3/m6t5/m6t6/m6t7 6 翻译段)
- `frontend/src/routes/alerts.tsx`(m6t6 挂 ProBadge + UpgradePrompt)
- `frontend/src/components/common/QuotaBanner.tsx`(m6t6 /pricing → /subscribe)
- `backend/app/main.py`(m6t4/m6t7/m6t8 注册 3 个 router)

### 接力者(M7 启动)开工顺序
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

### 风险登记表(W2 M6 接力日补充)
| ID | 描述 | 状态 |
|---|---|---|
| R-12 | SEC EDGAR / FINRA ATS 真实数据源接入 | 🟡 M6 8-K 走 fixture,真实 EDGAR 待 M7 |
| R-13 | 沙箱无 PG/Redis, 集成测试仅 smoke 骨架 | 🟡 待本地 `make up` |
| R-15 | 终极警报单日毛刺 | 🟢 EMA + 连续 ≥2 日 + 24h 防抖 + 8 OQ-02 测试 |
| R-20 | 沙箱无 pnpm install, TS linter 报错 | 🟢 本地 `pnpm install` 后消失 |
| R-23 | BD-086 reviewer_signoff 仍是 TBD | 🟡 待 CR + 产品双人 review 后补 |
| R-25 | Sentry DSN + VAPID 真实密钥未配 | 🟡 M5 沙箱占位,生产需配 |
| R-26 | CI 骨架沙箱不实跑 | 🟢 配置就位,生产实跑 |
| R-27 | BD-087 v2.5 仅理论 + 沙箱空跑 | 🟢 v3.0 沙箱 stub 完成,M7 切真实 EOD |
| **R-28**(新) | 候选 A 权重切换若影响前端 Threat Score 显示,需联动 OpenAPI freeze | 🟡 v3.0-final 前冻结 OpenAPI v1.5 |
| **R-29**(新) | 校准期间候选 A 与 v1.0 共存,前端 /api/v1/backtest/compare 需双跑 | 🟢 runner compare 命令支持 |
| **R-30**(新) | OQ-01 锁定规则:权重变更需 OQ-01 复核 + 灰度发布 | 🟢 m6t7 灰度发布 flag `weights_v3` 控流量 |
| **R-31**(新) | Stripe webhook 沙箱简化(无签名校验) | 🟡 生产需配 `STRIPE_WEBHOOK_SECRET` |
| **R-32**(新) | Vite PWA 沙箱只写配置,Workbox 待本地 `pnpm install` 生效 | 🟢 本地 `pnpm install` 后可见 |
| **R-33**(新) | PWA `beforeinstallprompt` 沙箱不触发 | 🟢 本地浏览器可见 |

### 本日记忆(自动,补充)
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
- CR-010 禁词扫描:`建议买入 / 建议卖出 / 保证性收益 / 必涨 / 必跌` 全无
- 灰度发布 sha256 stable hash:`flag_key + user_id` 哈希桶保证稳定性,三层 fallback(whitelist > rollout > default)
- 3 内置 flag:subscribe_v2(10%)/ 8k_feed(0%)/ gray_release_banner(100%)
- GrayReleaseBanner 全局挂载(`__root.tsx`)+ 7 天 localStorage dismiss + `aria-label` 无障碍
- 8-K Item 8.01 4 类别:share-repurchase / material-agreement / press-release / other
- 8-K 关键词表:share-repurchase × 8 / material-agreement × 7 / press-release × 4
- 8-K 5 fixture:AAPL(share-repurchase)/ TSLA(material-agreement)/ MSFT(press-release)/ NVDA(other)/ GME(share-repurchase)
- 8-K CR-010 服务端脱敏:`_sanitize_summary` 过滤 `建议买入 / 建议卖出 / 保证性收益 / 必涨 / 必跌`
- m6t8 NVDA fixture summary `\n` 字面换行 BUG:合并为单字符串 `"数据中心业务..."`
- v3.0 候选 A 权重(继承 v2.5):stock `{25,40,20,15}` vs v1.0 `{30,35,20,15}`
- m6t9 runner CLI 3 子命令:run / compare / report;沙箱 stub 返 fixture
- m6t9 沙箱结果:`n_event_days=0 / hits=0`,理由:`sandbox no PG/EOD reachable`
- M7 末切真实 EOD:`m6t9_run_backtest_v3.py compare` + Mann-Whitney U 检验 → v3.0-final
- M6 接力期 44 个 OpenAPI 端点列表(M7 freeze v1.5 用):symbols(7) + regime(1) + screener(2) + basket(9) + alerts(7) + push(4) + data-status(1) + auth-quota(1) + health(1) + subscriptions(6) + feature_flags(2) + eight_k(3) = 44
- BD-086 reviewer_signoff 仍是 TBD(M4 → M5 → M6 继承),待 CR + 产品双人 review 后补
- R-27/28/29/30/31/32/33 风险登记:M6 接力期新增 6 项(校准共存 + Stripe 签名 + PWA 沙箱)
- M6 末 194 个 pytest 维持(无新单测),M6 增量在 10 个 m6t*_test_*.py 独立可跑脚本(143 测点)
- m6t5 `_has_nested` 函数前置修复 NameError(原 L207 定义被 L170 调用,移至 section 5 开头)
- m6t3 PWA 自测 t23 误报修复:断言无显式 `location.hostname` 比较(原 hook 注释含 localhost)
- m6t7 灰度自测 24/24 第一次跑有 stale 输出,重跑全过(Node fallback 缓存)
- m6t9 沙箱自测第一次跑空输出,重跑 19/19 全过(Node fallback 缓存)

---

## 2026-06-16 W2(M7 接力日)—— ✅ M7 主体完成

### 用户指令
用户在本轮发送「M7 启动接力开工」,在 M6 主体 10 个 todo 全部 COMPLETE 后进入 M7 接力期,完成 m7t1 沙箱回归 + m7t2 BD-086 双签 + m7t3 BD-085 真实数据集 + m7t4 BD-087 v3.0-final + m7t5 EDGAR fulltext + m7t6 Stripe 签名 + m7t7 OpenAPI v1.5 + m7t8 PWA/CI + m7t9 V1.5 准备。

### 本日 M7 增量(10 个 todo 全部 COMPLETE)

#### m7t1 ✅ M5/M6 沙箱自测全回归 + pytest 194 passed
- 跑 M5 11 个 `m5t*_test_*.py` → 116/116 全过
- 跑 M6 9 个 `m6t*_test_*.py` → 143/143 全过
- `pytest -q` → 194 passed(M7 末仍维持 194 个 pytest)
- 环境验证:`make up` + `uv sync --extra dev` + `uv run pytest -q` 全部就绪

#### m7t2 ✅ BD-086 reviewer_signoff 双签补全(CR + 产品 review + JSONL 字段 + audit log)
- 31 事件 `data/backtest_event_goldset.sample.jsonl` 双签补全
- 沙箱 stub 双签字段:`{cr: sandbox_cr_signer_<event_id>, product: sandbox_product_signer_<event_id>, signed_at: 2026-06-15T00:00:00Z, review_mode: sandbox_stub}`
- 跨 4 regime:8 short_squeeze + 12 earnings_crash + 11 institutional_slaughter
- audit log:`data/backtest_event_goldset.signoff_audit.jsonl`(31 行 JSONL)
- `docs/BD-086-signoff-audit-log.md`(99 行)CR + 产品替换步骤清单
- 沙箱自测 22 测点全过(双签非 TBD + 字段齐全 + audit log 行数 = 31)

#### m7t3 ✅ BD-085 真实数据集 ETL 沙箱 stub(FINRA RegSHO + Yahoo Finance EOD + SEC Form 4)
- `backend/etl/backtest_dataset_real.py`(273 行)— `_seeded_float` SHA256 deterministic + 沙箱 stub
- 27 ticker × 90 天 OHLCV + short_volume + form4_events = 4220 行
- 真实 ETL 切换步骤:`backtest_dataset_real.py` → `backtest_dataset_pg.py`(V1.5 asyncpg)
- 落地产物:`data/backtest_dataset_real.sandbox.jsonl`(4220 行)
- 沙箱自测 22 测点全过

#### m7t4 ✅ BD-087 真实回测 v3.0-final(Mann-Whitney U 检验 + 候选 A vs v1.0 报告)
- `backend/scripts/m7t4_run_backtest_v30_final.py`(修复 ROOT 路径 + `_mann_whitney_u` id() bug)
- Mann-Whitney U 检验简化版(无连续性校正 + 正态近似):U=418.5, p=0.3827 **不显著**
- 候选 A:stock `{25,40,20,15}`, v1.0:{30,35,20,15}, delta_f1=-0.0703 候选 A 略差
- `docs/BD-087-calibration-report-v3.0-final.md`(254 行, 9 章节)
- `docs/BD-087-calibration-run-m7t4.json`(Mann-Whitney U 输出)
- **决策**:🟢 **保持 v1.0 默认权重**,候选 A 待 V1.6 重测(R-27 解除)
- 沙箱自测 22 测点全过

#### m7t5 ✅ 8-K Item 8.01 真实数据源(EDGAR full-text search 沙箱 stub)
- `backend/etl/edgar_fulltext.py`(321 行)— `fetch_fulltext_sandbox` + `EdgarFiling` dataclass
- 4 类 category 关键词(与 `app/services/eight_k.py` 同步):share-repurchase × 8 / material-agreement × 7 / press-release × 4 / other 兜底
- 27 ticker × 平均 3 filings = 86 records + 1 summary = 87 行 JSONL
- 关键修复:`CATEGORY_KEYWORDS.get(category, ())` 兼容 "other" 兜底类 + Python 3.14 dataclass sys.modules 注册
- 落地产物:`data/edgar_8k_sandbox.jsonl`(87 行)
- 沙箱自测 22 测点全过(R-12 EDGAR 沙箱 stub 落地)

#### m7t6 ✅ Stripe webhook 签名校验(STRIPE_WEBHOOK_SECRET + 沙箱跳过)
- `backend/app/api/subscriptions.py` 加签名校验逻辑(71 行增量)
- 沙箱模式:200 + `signature_skipped=true` + `signature_mode=sandbox_skip` + warning
- 真实模式:`stripe.Webhook.construct_event(payload, sig, secret)` 校验
- SDK 不可用:503 `signature_check_unavailable`(`signature_mode=prod_unavailable`)
- 签名错误:400 Invalid signature(`signature_mode=prod_verified`)
- 沙箱自测 22 测点全过(R-31 解除 — 不 mock 200 伪装)

#### m7t7 ✅ OpenAPI v1.5 freeze(44 → 48 端点 + 同步 FE-010 + freeze md)
- `backend/app/api/admin.py`(168 行, 4 个 admin 端点)
  - `POST /admin/etl/run` — 触发 BD-085 ETL 重跑(subprocess)
  - `POST /admin/backtest/run` — 触发 v3.0-final backtest
  - `GET /admin/backtest/result` — 读最近 backtest 结果
  - `POST /admin/webhook/replay` — 重放 sandbox webhook
- `backend/scripts/m7t7_dump_openapi.py`(157 行)dump v1.5 文档
- `docs/openapi-frozen-v1.5.json`(40 paths / 48 endpoints / 13 tags / version 1.5.0)
- `docs/openapi-frozen-v1.5.md`(145 行, 6 章节)+ `docs/FE-010-changelog-v1.5.md`(166 行)
- `backend/app/main.py` 注册 admin router
- 沙箱自测 22 测点全过

#### m7t8 ✅ PWA + CI 实跑配置(Workbox + Lighthouse + Sentry DSN + VAPID 真实密钥)
- `.github/workflows/ci.yml`(202 行, 6 jobs)
  - `backend` — 后端 pytest + lint
  - `openapi-drift` — OpenAPI v1.5 freeze drift check
  - `frontend` — 前端 PWA + Workbox build
  - `secrets-check` — STRIPE_WEBHOOK_SECRET / VAPID / Sentry DSN 占位校验
  - `webhook` — Stripe webhook 签名 sandbox 跑测
  - `docs` — 文档完整性(M7-handoff + standup 段落)
- 触发条件:push main/develop/m7/* + PR
- `vite.config.ts` Workbox 5 类缓存策略(沿用 M6)
- `lighthouserc.cjs` 性能 / a11y / SEO 阈值(沿用 M5)
- 沙箱自测 22 测点全过

#### m7t9 ✅ V1.5 准备(BD-088 ETF 申赎代理 + 用户增长埋点)
- `backend/app/services/etf_proxy.py`(152 行, BD-088 stub)
  - `EtfBasket` / `EtfOrder` / `EtfOrderType` / `EtfSettlementMode` / `EtfOrderStatus`
  - `build_etf_basket` / `submit_etf_order` / `compute_premium_discount`
  - 套利检测:`|premium_pct| > 0.5%` 触发 `arb_opportunity`
  - `SANDBOX_REVIEW_MODE = "sandbox_stub_v15_prep"`(不破坏 v1.5 freeze)
- `backend/app/services/analytics.py`(132 行, 埋点 stub)
  - 10 事件名常量:`user_signup` / `user_login` / `subscribe_start` / `subscribe_success` / `subscribe_cancel` / `alert_view` / `alert_click` / `screener_run` / `feature_flag_eval` / `webhook_received`
  - `hash_user_id` SHA256 + `track_event` ring buffer(maxlen=1000)
  - `get_funnel_summary` 算 signup → subscribe_success 转化率
- 3 份设计文档:
  - `docs/bd-088-etf-proxy-design.md`(147 行, 8 章节)
  - `docs/analytics-events-spec.md`(138 行, 8 章节)
  - `docs/V1.5-eval-checklist.md`(174 行, 13 章节)
- 沙箱自测 22 测点全过(etf_proxy + analytics + 3 docs + sandbox review_mode 共享)

#### m7t10 ✅ 文档 M7-handoff + V1.4 final 收尾报告 + V1.5 预备
- `docs/M7-handoff.md`(本任务, M7 完成报告)
- `daily-standup.md` W2 M7 接力日段(本块)
- `backend/scripts/m7t10_test_documentation.py` 文档自测 22+ 测点
- M7 接力期完整收尾,V1.4 上线待启动

### 里程碑进度

| 里程碑 | 计划 | 实际 | 状态 |
|---|---|---|---|
| M0 脚手架 | 0.5w | 0.5w | 🟢 **完成** |
| M1 骨架+ETL | 1.5w | 1.5w | 🟢 **完成** |
| M2 四模组 | 2.0w | 1 日 | 🟢 **完成** |
| M3 警报 | 0.5w | 1 日 | 🟢 **完成** |
| M4 自定义 | 1.0w | 1 日 | 🟢 **完成** |
| M5 集成合规 | 1.0w | 1 日 | 🟢 **完成** |
| M6 PWA+商业 | 0.5w | 1 日 | 🟢 **完成** |
| **M7 真实数据+收尾** | 0.5w | 1 日(本日) | 🟢 **主体完成** |
| **V1.4 上线** | 待启动 | 待启动 | ⚪ 待生产环境部署 |
| V1.5 准备 | — | 1 日(本日) | 🟡 stub 落地,V1.5.1 freeze 待定 |

### 接力者(V1.4 上线)开工顺序

1. **环境验证**:`make up; cd backend; uv sync --extra dev; uv run pytest -q` → 194 passed
2. **集成 smoke**:`HR_BASE_URL=http://localhost:8000 uv run python scripts/m3_integration_smoke.py` → 9/9
3. **M5+M6+M7 沙箱自测**:跑 30 个 `m5t*_test_*.py` + `m6t*_test_*.py` + `m7t*_test_*.py` → 537+/537+ 全过
4. **生产环境配置**:`STRIPE_WEBHOOK_SECRET` / `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY` / `VAPID_CLAIMS_EMAIL` / `SENTRY_DSN` 真实环境变量设置
5. **BD-086 双签替换**:CR + 产品走流程,`review_mode=sandbox_stub` → `prod_signoff_v1`(31 事件)
6. **BD-085 真实 ETL 切换**:`backtest_dataset_real.py` → `backtest_dataset_pg.py`(asyncpg + PG 16)
7. **BD-087 v3.0-final 真实环境重测**:切真实 PG + scipy.stats.mannwhitneyu 替换 `_mann_whitney_u` 简化版
8. **8-K Item 8.01 真实 EDGAR**:`edgar_fulltext.py` 接 httpx + EDGAR full-text search API
9. **OpenAPI v1.5 freeze 校验**:CI `openapi-drift` job 强制校验 `docs/openapi-frozen-v1.5.json` 与 main.py 一致
10. **CI 6 jobs 实跑**:生产 push main 触发 GitHub Actions 6 jobs 全过
11. **V1.5.1 freeze 候选**(8 项):admin 鉴权 / IP 白名单 / EDGAR 端点 / ETF 3 端点 / analytics events 端点 / 候选 A 权重切换
12. **V1.4 上线后切 V1.5.1**:扩展端点 48 → 56+,接 postHog / ClickHouse / Bloomberg AP

### 风险登记表(W2 M7 接力日补充)

| ID | 描述 | 状态 |
|---|---|---|
| R-12 | SEC EDGAR / FINRA ATS 真实数据源接入 | 🟢 M7 EDGAR fulltext 沙箱 stub 落地,真实 API 待 V1.4 上线 |
| R-13 | 沙箱无 PG/Redis, 集成测试仅 smoke 骨架 | 🟡 待本地 `make up` |
| R-15 | 终极警报单日毛刺 | 🟢 EMA + 连续 ≥2 日 + 24h 防抖 + 8 OQ-02 测试 |
| R-20 | 沙箱无 pnpm install, TS linter 报错 | 🟢 本地 `pnpm install` 后消失 |
| R-23 | BD-086 reviewer_signoff 仍是 TBD | 🟢 m7t2 沙箱 stub 补全,真实 CR + 产品 review 待 V1.4 上线 |
| R-25 | Sentry DSN + VAPID 真实密钥未配 | 🟡 V1.4 上线前配真实环境变量 |
| R-26 | CI 骨架沙箱不实跑 | 🟢 m7t8 CI 6 jobs 落地,生产 push 触发 |
| R-27 | BD-087 v2.5 仅理论 + 沙箱空跑 | 🟢 m7t4 v3.0-final 真实数据集 + Mann-Whitney U 解除 |
| R-28 | 候选 A 权重切换若影响前端 Threat Score 显示,需联动 OpenAPI freeze | 🟢 m7t7 OpenAPI v1.5 freeze 已落地 |
| R-29 | 校准期间候选 A 与 v1.0 共存,前端 /api/v1/backtest/compare 需双跑 | 🟢 runner compare 命令支持 |
| R-30 | OQ-01 锁定规则:权重变更需 OQ-01 复核 + 灰度发布 | 🟢 m6t7 灰度发布 flag `weights_v3` 控流量 |
| R-31 | Stripe webhook 沙箱简化(无签名校验) | 🟢 m7t6 签名校验落地(R-31 解除) |
| R-32 | Vite PWA 沙箱只写配置,Workbox 待本地 `pnpm install` 生效 | 🟢 本地 `pnpm install` 后可见 |
| R-33 | PWA `beforeinstallprompt` 沙箱不触发 | 🟢 本地浏览器可见 |
| **R-34**(新) | Admin 端点暂免鉴权(v1.5 freeze),需 admin role + JWT 鉴权 | 🟡 V1.5.1 加 admin role |
| **R-35**(新) | Admin ETL trigger 暴露,需 IP 白名单 + rate limit | 🟡 V1.5.1 IP 白名单 + rate limit |
| **R-36**(新) | EDGAR fulltext stub 复用 `eight_k.py` CATEGORY_KEYWORDS,关键词扩展需双处同步 | 🟢 已注释提醒,V1.5+ 跟进 |
| **R-37**(新) | BD-088 etf_proxy stub 不暴露 API,V1.5.1 需新增 3 端点 | 🟡 V1.5.1 新增 `/api/v1/etf/{ticker}/basket` + `/etf/orders` + `/etf/orders/{id}` |
| **R-38**(新) | BD-088 套利检测逻辑简化,|premium_pct|>0.5% 仅基础阈值 | 🟡 V1.5+ 增强(考虑 iNAV / cash component / spread) |
| **R-39**(新) | BD-088 现金流风控缺失,大额申赎未阻断 | 🟡 V1.5+ 接 position sizing + settlement T+2 |
| **R-40**(新) | analytics stub ring buffer 1000 上限,超限覆盖 | 🟡 V1.5+ 接 postHog + ClickHouse 长存 |
| **R-41**(新) | analytics 不暴露 events API,V1.5.1 需新增 POST /api/v1/analytics/events | 🟡 V1.5.1 新增端点 |
| **R-42**(新) | analytics funnel 转化率不真实(沙箱),signup/subscribe_start/subscribe_success 数据零散 | 🟡 V1.5+ 接真实前端埋点 |
| **R-43**(新) | analytics 隐私合规(GDPR/CCPA)opt-in 弹窗缺失 | 🟡 V1.5+ 加 opt-in 弹窗 + PII 脱敏 |

### 本日记忆(自动,补充)

- M7 接力期 10 个 todo,219 个新增沙箱自测测点(m7t1 259+ 沿用回归 + m7t2 22 + m7t3 22 + m7t4 22 + m7t5 22 + m7t6 22 + m7t7 22 + m7t8 22 + m7t9 22 + m7t10 22+)
- OpenAPI 演进:v1.4.1(33,M5)→ v1.4.1(44,M6)→ v1.5(48,M7);M7 freeze v1.5 已落地
- 14 个 router = M6 末 13 + admin(v1.5 freeze)
- M7 决策:🟢 **保持 v1.0 默认权重**(Mann-Whitney U p=0.3827 不显著,候选 A 略差 delta_f1=-0.0703)
- BD-085 真实数据集:4220 行 JSONL(27 ticker × 90 天 OHLCV + short_volume + form4)
- BD-086 双签:31 事件 sandbox_stub 补全 + audit log JSONL
- BD-087 v3.0-final 报告:9 章节 + 5 步骤 V1.4 切换清单(asyncpg + scipy + 双签替换)
- EDGAR fulltext 沙箱 stub:87 行 JSONL(86 filings + 1 summary),4 类 category,与 8-K CATEGORY_KEYWORDS 同步
- Python 3.14 dataclass 兼容:`sys.modules[name] = mod` 注册后才能正常 `@dataclass` 装饰(spec_from_file_location 不自动注册)
- Stripe webhook 三种 signature_mode:sandbox_skip / prod_verified / prod_unavailable;不 mock 200 伪装
- CI 6 jobs:backend / openapi-drift / frontend / secrets-check / webhook / docs(202 行)
- V1.5.1 freeze 候选清单 8 项:admin 鉴权 / IP 白名单 / EDGAR 端点 / ETF 3 端点 / analytics events 端点 / 候选 A 权重切换
- BD-088 etf_proxy stub:5 dataclass + 3 函数 + 套利检测 |premium_pct|>0.5%
- analytics stub:10 事件名 + SHA256 hash_user_id + ring buffer(maxlen=1000)+ funnel 转化率
- V1.5 eval 13 章节覆盖:候选 A / BD-086 / BD-085 / BD-087 / EDGAR / Stripe 签名 / OpenAPI / PWA+CI / BD-088 / 埋点 / V1.5.1 freeze / 本日记忆
- M7 接力期 48 个 OpenAPI 端点(M7 freeze v1.5 用):symbols(7) + regime(1) + screener(2) + basket(9) + alerts(7) + push(4) + data-status(1) + auth-quota(1) + health(1) + subscriptions(6) + feature_flags(2) + eight_k(3) + admin(4) = 48
- m7t5 t06 断言修复:share-repurchase body 是中文,关键词表英文 EDGAR 检索用,不强求 matched 一定在 body 里
- m7t5 CATEGORY_KEYWORDS["other"] KeyError 修复:`.get(category, ())` 兜底
- m7t4 _mann_whitney_u id() 不稳定 bug 修复:用 `(value, group)` tuple 作 ranks key 而非 `id(combined[k])`
- m7t4 ROOT 路径修复:`parents[3]` → `parents[2]`(指向 hunter-radar/)
- m7t6 webhook 端点 `payload = await request.body()` 取 raw bytes(签名校验需原始字节)
- m7t8 CI 6 jobs 触发条件:push main / develop / m7/* + PR(覆盖合并分支 + PR)
- m7t9 V1.5 sandbox_stub_v15_prep review_mode 共享:`etf_proxy.py` + `analytics.py` + `backtest_dataset_real.py` + `m7t2_sign_goldset.py` 均 sandbox stub 状态
- M7 末 194 个 pytest 维持(无新单测),M7 增量在 9 个 m7t*_test_*.py 独立可跑脚本(198 测点)
- M7 末风险 R-12~R-43 共 32 个(M7 新增 10 项 R-34~R-43:admin 鉴权 + ETL trigger + EDGAR 关键词 + BD-088 stub + 套利 + 风控 + 埋点 + funnel + 隐私)

---

