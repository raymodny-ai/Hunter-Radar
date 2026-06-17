# 📂 Hunter Radar V1.4 — 会话关闭总包(W0 末 历史档案)

> **⚠️ 历史状态**:本会话由 AI agent 在 2026-06-15 W0 Day 1 完成 M0 + M1 计算层后,**用户主动选择「暂停」(代号 2)**。
> **⏩ 已于同日恢复执行**:见 [M1-handoff.md](M1-handoff.md) 顶部「M1 收尾完成」区段,本仓库 M1 末(ETL 落库层)已于 W0 末收尾完成。
>
> 本文档保留作为 W0 末的「状态快照 + 一站式交接」,后续 M2/M3 接力请直接看 [M1-handoff.md](M1-handoff.md)。

---

## 0. 一句话状态

| 项 | 状态 |
|---|---|
| **工程可启可测** | ✅ `cd hunter-radar && make up && uv run pytest -q`(本地) |
| **M0 脚手架** | ✅ 完成(100%) |
| **M1 计算服务** | ✅ 完成(100%,**核心 IP 全部在代码层落地**) |
| **M1 ETL 落库** | ⛔ 0%(下一棒) |
| **M2 四模组实装** | ⛔ 0% |
| **M3 警报/M4 自定义/M5 集成/M6 商业** | ⛔ 0% |
| **测试用例数** | 79 个 pytest 用例,**未在本沙箱执行**(沙箱无 Python/Node/Docker) |

---

## 1. 关键决策(锁定,后续请勿重开)

| 决策 | 落地位置 | 备注 |
|---|---|---|
| **OQ-01:Threat Score 权重必须回测校准** | `services/` 全部阈值集中到 dataclass(AnomalyThresholds/RegimeConfig);BD-085~BD-087 已列入 M2 | 静态权重 30/35/20/15、35/45/20 不直接上线 |
| **OQ-02:「持续 2 日」= 连续 2 个交易日** | `threat_score.consecutive_business_days_above()` | 不是自然日 |
| **OQ-02:EMA 半衰期默认 2 交易日** | `threat_score.ema_smooth(halflife_days=2)` | 8 个 OQ-02 测试已锁,禁止修改 |
| **OQ-09 / OQ-11:项目忽略** | `Hunter-Radar-v1.4-implementation-todo.md` §7 中标 ⊘ | 后续**不要重启讨论** |
| **OQ-16:ETF 申赎数据先用代理指标** | `short_metrics.etf_proxy_anomaly_score()` | 真实 NSCC/Bloomberg 数据采购延后到 V1.5 |
| **合规红线:禁词清单** | `scripts/compliance_check.py` | "建议买入/卖出/建仓时机/必涨/必跌/清仓/保证收益/稳赚/无风险" |
| **自治边界:仅资金/法务/范围变更需请示** | 本会话默认承担其他所有 | 详见 `Hunter-Radar-v1.4-implementation-todo.md` §10 |

---

## 2. 仓库结构(实际产出)

```
d:\Financial Project\Hunter Radar\
├── Hunter-Radar-v1.4-implementation-todo.md   ← 140 条 Todo 总览
├── frontend-plan.md                           ← 原始输入
├── Hunter Radar-v1.3-1.4-merged-reference.md  ← 原始输入
├── daily-standup.md                           ← 站会(W0 上午 + 下午暂停)
└── hunter-radar/                              ← 实际工程
    ├── README.md
    ├── Makefile
    ├── .gitignore
    ├── .github/workflows/ci.yml               ← 后端 ruff+pytest / 前端 eslint+typecheck / 合规扫描
    ├── infra/
    │   └── docker-compose.yml                 ← PG + Redis + Airflow(3 容器)
    ├── scripts/
    │   └── compliance_check.py                ← CR-010 红线 CI 必跑
    ├── docs/
    │   ├── M0-completion-report.md
    │   ├── M1-handoff.md                      ← §6 记录本轮增量 + 仍需接力项
    │   └── SESSION-CLOSED.md                  ← 本文档
    ├── backend/
    │   ├── pyproject.toml
    │   ├── .env.example
    │   ├── sql/00_init.sql                    ← 19 张表 + 视图
    │   ├── dags/hunter_radar_eod.py           ← Airflow DAG 模板
    │   ├── app/
    │   │   ├── main.py                        ← FastAPI 入口(5 router)
    │   │   ├── core/{config,database,redis_client}.py
    │   │   ├── api/{health,symbols,regime,screener,alerts}.py
    │   │   ├── models/__init__.py             ← 19 张表 ORM
    │   │   └── services/
    │   │       ├── threat_score.py            ← ⭐ OQ-02 EMA + 状态机
    │   │       ├── options_anomaly.py         ← BD-020/021/022
    │   │       ├── short_metrics.py           ← BD-030/031/032 + OQ-16 PoC
    │   │       ├── divergence.py              ← BD-040/041/042
    │   │       ├── insider.py                  ← BD-050/051/052
    │   │       └── regime_history.py          ← BD-063/066
    │   ├── etl/
    │   │   ├── finra_short.py
    │   │   ├── sec_form4.py
    │   │   ├── yfinance_pull.py
    │   │   └── symbol_seed.py                 ← 17 个种子标的
    │   └── tests/                             ← 6 个测试文件
    │       ├── test_threat_score.py           ← 8 用例(OQ-02)
    │       ├── test_options_anomaly.py        ← 14 用例
    │       ├── test_short_metrics.py          ← 17 用例
    │       ├── test_divergence.py             ← 12 用例
    │       ├── test_insider.py                ← 17 用例
    │       └── test_regime_history.py         ← 11 用例
    │                                          ← 累计 79 个 pytest 用例
    └── frontend/
        ├── package.json
        ├── vite.config.ts                     ← PWA + /api 代理 :8000
        ├── tailwind.config.js                 ← 信号灯色板
        ├── tsconfig.json
        ├── README.md
        ├── index.html
        └── src/
            ├── main.tsx, router.tsx, routeTree.ts
            ├── i18n/{index.ts,zh-CN.json}
            ├── lib/{api.ts, queryClient.ts}
            ├── routes/
            │   ├── __root.tsx
            │   ├── index.tsx                  ← 首页(搜索 + Top 10)
            │   ├── symbol.$ticker.tsx         ← ⭐ 核心页
            │   ├── screener.tsx
            │   ├── basket.tsx
            │   └── alerts.tsx
            └── components/
                ├── common/Disclaimer.tsx
                └── radar/
                    ├── ThreatScoreGauge.tsx   ← 圆形仪表盘(纯 SVG)
                    ├── ModuleSignalLight.tsx  ← 单模块灯
                    └── RegimeBanner.tsx       ← 顶部市场状态横幅
```

---

## 3. 接力者第一周(Week 1)开工顺序

### Day 1:环境验证
```bash
cd "d:\Financial Project\Hunter Radar\hunter-radar"
make up                                           # 起 PG/Redis/Airflow
cd backend
uv sync --extra dev                               # 安装依赖
uv run python -m etl.symbol_seed                  # 导入 17 个种子标的
uv run pytest -q                                  # 期望 79 passed
cd ../frontend
pnpm install
pnpm dev                                          # :5173
# 浏览器开 http://localhost:5173
# 后端文档:http://localhost:8000/docs
```

### Day 2:ETL 落库层(M1 末剩余)
按 [M1-handoff.md §2.1](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/docs/M1-handoff.md) 顺序:
1. `etl/load_short_volume.py`(BD-004 落库,ON CONFLICT DO NOTHING)
2. `etl/load_ats_short.py`(BD-005 切分 venue)
3. `etl/load_options_chain.py`(BD-009 落库 + 调 `services.options_anomaly.filter_top_anomaly_puts`)
4. `etl/load_form4.py` + `etl/load_buyback.py`(BD-006/051)
5. `etl/refresh_data_status.py`(BD-011 每个 task 尾部写状态灯)
6. Airflow DAG `hunter_radar_eod.py` 任务依赖连线

### Day 3–5:前端接通真实 API
1. `api.ts` 增加 5 个真实端点(getThreatScore / getOptionsAnomaly / getShortMetrics / getDivergence / getInsiderTimeline / getRegime / getHistory)
2. 移除各 api.py 中的 `NotImplementedError` 占位
3. 跑 Playwright E2E 验证关键路径

### Day 5:BD-085 / BD-086 / BD-087(M2 启动)
1. BD-085 拉 1–2 年 EOD 历史数据集(标普 500 + 纳指 100 + 中概 + 主流 ETF)
2. BD-086 标 ≥30 个「机构绞杀/财报季暴跌」金标准事件
3. BD-087 跑校准,出《Threat Score 校准报告 v1.0》

---

## 4. 风险登记表(W0 末快照)

| ID | 描述 | 状态 | 缓解 |
|---|---|---|---|
| R-01 | FINRA 反爬漏抓 | 🟡 缓解中 | BD-012 限流;`pending_disclosure` 兜底 |
| R-02 | Threat Score 静态权重误报 | 🟢 已规划 | BD-085~BD-087 回测链;阈值 dataclass 化 |
| R-03 | 单日毛刺信号误触发 | 🟢 已落地 | BD-062b EMA + 8 测试锁 |
| R-04 | 合规文案漏检 | 🟢 已落地 | `compliance_check.py` + CI 必跑 |
| R-05 | 数据缺失伪装实时 | 🟡 缓解中 | `data_ingestion_status` 视图已建,API 集成待 M2 |
| R-10 | 量价背离回归窗口误配 | 🟢 已规划 | `lookback=10, history_lookback=120` 显式参数化 |

---

## 5. 给「下一位 agent」的红线清单(请勿触碰)

| 红线 | 原因 |
|---|---|
| `services/threat_score.py` 中 `ema_smooth` / `consecutive_business_days_above` | OQ-02 决策,8 个测试锁住 |
| `scripts/compliance_check.py` 禁词清单 | CR-010 红线,加词需 CR 签字 |
| `Hunter-Radar-v1.4-implementation-todo.md` §7 中标 ⊘ 的 OQ-09 / OQ-11 | 用户明确「项目忽略」,勿重启 |
| `services/short_metrics.etf_proxy_anomaly_score` 之外的"真实"申赎数据接入 | OQ-16 推 V1.5,本期不碰 |
| 修改 `THREAT_RED_THRESHOLD` 等配置类阈值(`.env.example`) | M2 回测后才有定稿值,目前用 PRD 建议默认值 |

---

## 6. 22 项剩余 OQ 自动推进原则

(已写入 `Hunter-Radar-v1.4-implementation-todo.md` §9,这里只列规则)

| OQ 类型 | 处理 |
|---|---|
| 仅影响默认值/UI 文案/排序 | **直接按"建议默认"实现**,commit message 注明 |
| 影响多模块协同 | 写 `docs/oq/<id>.md` 一页备忘录,M5 末复盘 |
| 涉及付费数据采购/法务/跨里程碑 | **必请示用户** |

---

## 7. 联系上下文

- 用户偏好:中文沟通,极简回复(参见 memory:「复杂项目自治执行模式与 EMA 参数决策」)
- 工作目录:`d:\Financial Project\Hunter Radar`(PowerShell,**不要用 `&&`,用 `;`**)
- 系统时间:2026-06-15(项目实际启动日)
- 项目技术栈:Python 3.12 + FastAPI + TS 5 + Vite 5 + React 18(详见各 README)

---

*本文档由 AI agent 于 2026-06-15 会话关闭时自动生成。*
*下一位接手者读完本文档 + [M1-handoff.md](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/docs/M1-handoff.md) 即可零上下文启动。*
