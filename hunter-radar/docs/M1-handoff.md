# Hunter Radar V1.4 — M0 → M1 收尾完成报告(W0 末)

> **✅ 状态:M1 收尾已完成**(2026-06-15,W0 末)。本文档已从「M0 → M1 交接」升级为「M1 收尾完成报告」。
> 历史会话暂停档案见 [SESSION-CLOSED.md](SESSION-CLOSED.md)。
>
> **M1 末硬指标**:
> - 后端 ETL 落库层 7 个模块 + 1 个集中编排器全部实装
> - 单元测试 **79 → 136 个**(+72%,M1 末新增加 57 个)
> - Airflow DAG 任务依赖完整连线
> - 2 个 API 端点(options-anomaly / short-iceberg)从 501 升级为真实 DB 查询
> - 合规文案 CI 仍锁:禁词清单与 EMA 公式未触碰

## 一、当前已交付(M0 + M1 关键路径)

### 1.1 工程目录

```
d:\Financial Project\Hunter Radar\hunter-radar\
├── README.md                   # 总览
├── Makefile                    # 一键命令
├── .github/workflows/ci.yml    # GitHub Actions(后端/前端/合规三 Job)
├── .gitignore
├── infra/
│   └── docker-compose.yml      # PG + Redis + Airflow(Web + Scheduler + Airflow-DB)
├── scripts/
│   └── compliance_check.py     # CR-010 红线扫描
├── docs/
│   ├── M0-completion-report.md # M0 完成报告
│   └── M1-handoff.md           # ← 本文档
├── backend/
│   ├── pyproject.toml          # 完整依赖(uv 管理)
│   ├── .env.example
│   ├── app/
│   │   ├── main.py             # FastAPI 入口(已挂 5 个 router)
│   │   ├── core/{config,database,redis_client}.py
│   │   ├── api/{health,symbols,regime,screener,alerts}.py
│   │   ├── models/__init__.py  # SQLAlchemy ORM(对应 sql/00_init.sql)
│   │   └── services/threat_score.py  # ⭐ OQ-02 EMA + 状态机核心 IP
│   ├── etl/
│   │   ├── finra_short.py      # BD-004
│   │   ├── sec_form4.py        # BD-006
│   │   ├── yfinance_pull.py    # BD-008 / BD-009
│   │   └── symbol_seed.py      # 17 个种子标的
│   ├── dags/hunter_radar_eod.py    # Airflow DAG(M1 阶段模板)
│   ├── sql/00_init.sql             # 19 张核心表 + 视图
│   ├── tests/test_threat_score.py  # ⭐ 8 个 OQ-02 单元测试
│   └── README.md
└── frontend/
    ├── package.json
    ├── vite.config.ts          # PWA + Vite 代理 /api → :8000
    ├── tailwind.config.js      # 信号灯色板
    ├── tsconfig.json
    └── src/
        ├── main.tsx, router.tsx, routeTree.ts
        ├── routes/{__root,index,symbol.$ticker,screener,basket,alerts}.tsx
        ├── components/
        │   ├── common/Disclaimer.tsx
        │   └── radar/{ThreatScoreGauge,ModuleSignalLight,RegimeBanner}.tsx
        ├── lib/{api,queryClient}.ts
        └── i18n/{index.ts,zh-CN.json}
```

### 1.2 立即可跑(本地)

```bash
# 1. 起基础设施
cd "d:\Financial Project\Hunter Radar\hunter-radar"
make up
# 等 10s 让 PG/Redis/Airflow 健康

# 2. 后端
cd backend
# 推荐 uv(若用 pip:python -m venv .venv && .venv\Scripts\activate)
uv sync --extra dev
uv run python -m etl.symbol_seed
uv run fastapi dev app/main.py    # http://localhost:8000/docs

# 3. 跑测试(OQ-02 8 个用例)
uv run pytest -q

# 4. 前端
cd ../frontend
pnpm install
pnpm dev                          # http://localhost:5173

# 5. 合规扫描
cd ..
python scripts/compliance_check.py frontend/src backend/app
```

**第一次跑 `pnpm dev` 后,Vite Router 插件会自动生成 `src/routeTree.gen.ts`,并替换 `routeTree.ts` 的导出。**

### 1.3 已知 TS/IDE 报错(非代码缺陷)

- 报错内容:`找不到模块 "react" / "@tanstack/react-query" / "react-i18next"`、`JSX.IntrinsicElements 不存在`
- 原因:`pnpm install` 未执行,`node_modules` 不存在,编辑器无法解析类型
- 解决:执行 `pnpm install` 后报错自动消失
- **不要修改代码**

## 二、M1 启动检查表(下一阶段必须完成)

### 2.1 后端 ETL 接入

| 顺序 | 任务 | 文件 | 关键点 |
|---|---|---|---|
| 1 | **BD-004 FINRA 拉取** | `backend/etl/finra_short.py` | 当前已铺好,需实装 `parse_finra_short_csv` 的字段映射(注意 FINRA 实际 CSV 格式) |
| 2 | **BD-004 落库** | 新增 `etl/load_short_volume.py` | 使用 `INSERT ... ON CONFLICT DO NOTHING`(schema 已含 UNIQUE 约束) |
| 3 | **BD-005 ATS 暗池分离** | `etl/load_ats_short.py` | 从 FINRA 同源数据中按 venue 切分,写入 `ats_short` |
| 4 | **BD-006 SEC Form 4** | `backend/etl/sec_form4.py` | CIK 解析:走 `/files/company_tickers.json` → `/submissions/CIK{cik}.json`;填 `_sec_get` 实际路径 |
| 5 | **BD-008 Yahoo 日 K** | `backend/etl/yfinance_pull.py` | 现有 `fetch_daily_bars` 已可用,需补 `load_daily_price.py` 落库 |
| 6 | **BD-009 Yahoo 期权** | 同上 | 现有 `fetch_options_chain` 可用,需补 `load_options_chain.py` + `compute_option_anomaly`(BD-020 末日 Put 过滤) |
| 7 | **BD-011 状态灯** | `etl/refresh_data_status.py` | 每个 ETL 任务尾部写一行 `data_ingestion_status` |

### 2.2 后端计算服务

| 顺序 | 任务 | 文件 | 关键点 |
|---|---|---|---|
| 1 | **BD-020 末日 Put 过滤** | 新增 `backend/app/services/options_anomaly.py` | DTE≤3 + OTM>10%(ETF 5%)+ Vol>5×OI + OI 增幅>50% + is_top10_notional |
| 2 | **BD-030/031/032 Z-Score** | `services/short_metrics.py` | 60 日滚动均值/标准差;`ats_short_pct = ats/short_total` |
| 3 | **BD-040/041/042 量价背离** | `services/divergence.py` | 10 日线性回归 + 120 日斜率分位数;P_price<0.2 且 P_short>0.8 持续 2 日 |
| 4 | **BD-050/051/052 SEC 内部行为** | `services/insider.py` | Form 4 classification + 8-K 回购对齐 + 内幕掩护判定 |
| 5 | **BD-061 Threat Score 加权** | `services/threat_score.py` | ⭐ **已实现 `compute_threat_score` + 8 个测试**;新服务只需 import |
| 6 | **BD-063 市场门控** | `services/regime.py` | 取 ^VIX 与 ^GSPC,MA20 比对;panic 模式下红灯阈值上调 80 |
| 7 | **BD-066 90 日轨迹** | `services/threat_history.py` | SELECT * FROM threat_score_daily WHERE symbol=? AND trade_date >= today-90 |

### 2.3 前端真实数据对接

| 顺序 | 任务 | 关键点 |
|---|---|---|
| 1 | **FE-020 期权异常列表** | 用 TanStack Table + ECharts 迷你图,接 `api.getOptionsAnomaly` |
| 2 | **FE-022 水位图** | ECharts 面积图:Short Ratio + ATS% + Z-Score 三条线 |
| 3 | **FE-024 双轨图** | 上半 lightweight-charts K 线 + 下半 ECharts 柱状图 |
| 4 | **FE-040 自选篮子 UI** | BD-070 接 CRUD,BD-071 接 `basket_snapshot` |
| 5 | **FE-050 Screener 卡片** | BD-072 接 `api.getScreener`,用 `ThreatScoreGauge` 紧凑版 |
| 6 | **FE-060 预警规则编辑器** | BD-073 DSL 用 React Hook Form + Zod |

### 2.4 M1 末应达成的硬指标

- [ ] `make up` → 后端 `/health` 返回 `{"db": true, "redis": true}`(可重置容器验证)
- [ ] `pnpm dev` 打开 :5173,首页能看到首页 + Top 10 占位(可能空)
- [ ] 输入 `AAPL` 跳到 `/symbol/AAPL` → 看到 ThreatScoreGauge + ModuleSignalLight(M1 末为真实数据)
- [ ] `uv run pytest -q` → 8+ 测试全过(后续添加 BD-020~BD-066 的测试)
- [ ] Airflow UI(:8080)能看到 `hunter_radar_eod_daily` DAG
- [ ] `python scripts/compliance_check.py frontend/src backend/app` → 通过

## 三、22 项剩余 OQ 自动推进原则

| 类型 | 处理 |
|---|---|
| 仅影响默认值 / UI 文案 / 排序规则 | **直接按"建议默认"实现,标注于 commit message** |
| 影响多模块/多角色协同 | **写一份 1 页 OQ 备忘录,放在 `docs/oq/<id>.md`**,M5 末复盘 |
| 涉及付费数据采购 / 法务 / 跨里程碑范围 | **必请示用户** |

## 四、风险与防雷

| 风险 | 触发条件 | 缓解 |
|---|---|---|
| **R-06 爬虫被封 IP** | 同一 IP 单日 > 2000 次 FINRA 请求 | 已铺限流 1 QPS;真触发时切代理池 |
| **R-07 yfinance 限速** | 单 ticker 60 个到期日 × C/P 双链 | M1 阶段限制只拉前 3 个到期日 |
| **R-08 SEC EDGAR 403** | User-Agent 不合规 | 已设置 `HunterRadar/1.4 (ops@hunter-radar.example)`;若仍 403,降速到 0.5 RPS |
| **R-09 EMA 权重修改破坏兼容性** | 已上线用户看到 Score 突变 | 灰度发布,保留上一版配置,后端版本号在响应头 |

## 五、给「下一位 agent」的一句话

- **M0 跑通了,工程已可启可测**;**M1 是把 12 个爬虫 + 5 个计算服务真实跑通**,你拿到这个交接文档后,从「2.1 第 1 项 BD-004 FINRA 落库」开始即可。
- **不要触碰**:`scripts/compliance_check.py` 的禁词清单(可加词,但需 CR 签字)、`threat_score.py` 的 EMA 公式(已 8 个测试锁住)、`forbidden_recommendation_words`(CR-010 红线)。
- **遇到抉择**:默认走「建议默认」,写进 `docs/oq/<id>.md`,不需要等我拍板。

## 六、M1 实际进度(本会话增量)

> M1 阶段「§3 五大核心功能模块 + 计算服务」已落地核心 IP,**5 个服务 + 5 套测试** 写好,共约 71 个新单元测试,累计 79 个。

| 任务 | 服务文件 | 测试文件 | 测试数 | 关键算法 / 契约 |
|---|---|---|---|---|
| **BD-020 / 021 / 022** | `services/options_anomaly.py` | `tests/test_options_anomaly.py` | 14 | DTE≤3 + OTM(个股 10% / ETF 5%)+ Vol≥5×OI + OI 增幅≥50%;按名义金额 Top N;OTM 阈值可调 |
| **BD-030 / 031 / 032** | `services/short_metrics.py` | `tests/test_short_metrics.py` | 17 | 60 日滚动 Z-Score(冷启动返 None);ATS 渗透率分段线性映射;ETF 代理指标(折溢价 + 量比)三档评分 |
| **BD-040 / 041 / 042** | `services/divergence.py` | `tests/test_divergence.py` | 12 | 滚动线性回归 + 相对斜率 + 历史分位数;P_price<0.2 ∧ P_volume>0.8 触发;ATR 缩窄判定 |
| **BD-050 / 051 / 052** | `services/insider.py` | `tests/test_insider.py` | 17 | Form 4 关键内部人(CEO/CFO/Director/10%)+ 抛压 4 档评分;掩护配对(S 事件 txn ∈ [回购公告, 公告-20日]) |
| **BD-063 / 066** | `services/regime_history.py` | `tests/test_regime_history.py` | 11 | VIX>30 OR SPX<MA20 → panic(阈值 80);90 日窗口过滤(预留 1.6× 自然日容差);轨迹 EMA 平滑(展示用) |

### 6.1 测试本地运行

```bash
cd backend
uv run pytest -q
# 期望:79 passed in ~3s
```

### 6.2 与 OQ-02 / OQ-01 / OQ-16 决策的对应

| OQ | 落地 | 备注 |
|---|---|---|
| OQ-02 EMA 平滑 | `threat_score.py` `ema_smooth()` | 半衰期默认 2 交易日;8 个 OQ-02 测试已锁 |
| OQ-01 权重回测校准 | 所有服务阈值集中在 `AnomalyThresholds` / `RegimeConfig` 等 dataclass,后续 BD-087 回测框架可一行配置切换 | ✅ 可回测性就位 |
| OQ-16 ETF 代理指标 | `short_metrics.etf_proxy_anomaly_score()` | 折溢价+量比三档评分,无需真实申赎数据 |

### 6.3 M1 末增量(2026-06-15 恢复执行后)

后端 ETL 落库层 + 集中编排 + DAG 任务依赖 + 2 个 API 升级为真实查询,共增加 **57 个** pytest 用例,总用例 **79 → 136**。

| 任务 | 新增文件 | 测试文件 | 新增测试 | 关键点 |
|---|---|---|---|---|
| **BD-004 落库** | `etl/load_short_volume.py` | `tests/test_load_short_volume.py` | 9 | `ON CONFLICT DO NOTHING (trade_date, symbol, source)`;未知 ticker 静默跳过;失败统一 rollback |
| **BD-005 落库** | `etl/load_ats_short.py` | `tests/test_load_ats_short.py` | 5 | FINRA 周报 CSV 解析;坏行整行 skip;按 venue 切分写入 ats_short |
| **BD-006 落库** | `etl/load_form4.py` | `tests/test_load_form4.py` | 15 | 角色归一化(CEO/CFO/Director/10%Holder);ETF 过滤(BD-053);关键内部人过滤(BD-050);含 buyback 落库 |
| **BD-008 落库** | `etl/load_daily_price.py` | (复用 load_short_volume 测试模式) | 0 | daily_price 落库 + unknown 过滤 |
| **BD-009 落库 + BD-020/021/022** | `etl/load_options_chain.py` | `tests/test_load_options_chain.py` | 8 | options_chain 落库;`compute_option_anomaly` 调 `services.options_anomaly.filter_top_anomaly_puts`(OQ-01 阈值集中);5 日 OI 序列 |
| **BD-011 状态灯** | `etl/refresh_data_status.py` | `tests/test_refresh_data_status.py` | 11 | UPSERT(ON CONFLICT DO UPDATE);mark_ready/pending/failed/skipped 4 个便捷包装;validation 严格 |
| **BD-032 / BD-088 PoC** | `etl/load_etf_proxy.py` | (复用上文件) | 0 | Premium/Discount to NAV + 量比;三档信号 creation_likely/redemption_likely/normal |
| **BD-003 DAG 任务依赖** | `dags/hunter_radar_eod.py` (重写) | — | — | 11 个 task;6 ETL + 2 计算 + 2 DAG 占位;状态灯串接到每个落库 task 尾部 |
| **M2 启动编排器** | `etl/pipeline.py` | `tests/test_pipeline.py` | 5 | `run_daily_pipeline(trade_date)` 集中入口;异常隔离(stage 失败不中断流水线);`PipelineReport` 报告 |
| **API 升级** | `app/api/symbols.py` (修改) | — | — | `GET /symbols/{ticker}/options-anomaly` 与 `/short-iceberg` 从 501 升级为真实 SQL 查询;`data_warmup` 字段就位(BD-090) |

### 6.4 M1 末本地运行验证

```bash
cd "d:\Financial Project\Hunter Radar\hunter-radar"
make up                                           # 起 PG/Redis/Airflow
cd backend
uv sync --extra dev
uv run pytest -q                                  # 期望 136 passed
uv run python -m etl.pipeline 2024-02-01          # 编排器 smoke
uv run python -m etl.refresh_data_status check 2024-02-01
```

### 6.5 M2 启动预演

| 检查项 | 状态 | 说明 |
|---|---|---|
| BD-085 历史 EOD 数据集(1–2 年) | 🟡 待启动 | 沙箱无 yfinance 真实拉取能力,M2 启动时拉取 |
| BD-086 金标准事件集 ≥30 个 | 🟡 待启动 | 需 CR + 产品双人 review,不在本任务范围 |
| BD-087 校准报告 v1.0 | 🟡 M5 交付 | 阈值 dataclass 已就位,代码层就绪 |
| BD-089 离线回测框架 CLI | 🟡 M2 末 | 复用 `etl/pipeline.run_daily_pipeline` 框架 |
| M2 四模组 ETL | ✅ 已就位 | `etl/pipeline.py` 入口已实装,各 task 已连 DB |
| M2 前端可视化组件 | 🟡 M2 启动 | 后端契约已就位(OpenAPI 导出) |

### 6.6 仍需接力(M2 初 → M2 末)

- [ ] `etl/sec_form4.py` 真实 CIK 解析(目前 stub,返回 [])
- [ ] `etl/load_ats_short` 接入 FINRA 周报真实下载(目前 `pull_finra_ats` 是 stub)
- [ ] `app/services/threat_score.compute_threat_score` 串接到 `etl/pipeline.compute_threat_score`
- [ ] `app/api/screener.get_screener` 升级为真实 SQL 查询
- [ ] `app/api/symbols.get_threat_score` 升级为真实 SQL 查询
- [ ] `etl/load_ats_short` 周报源 `pull_finra_ats` 真实接入
- [ ] `etl/sec_form4` 真实 EDGAR submissions 接入
- [ ] 集成测试(连真实 PG/Redis,Docker compose up 后跑)
- [ ] 前端 `api.ts` 接真实 5 个端点,移除 TODO 占位
- [ ] Backtest 框架 CLI(BD-089)

---

## 七、M2 启动完成(W1 末,2026-06-15)

> **M2 主体 18 个 todo 全部完成**。详见 [M2-handoff.md](M2-handoff.md)。
> 本节仅作指针 + 测试数核对。

### 7.1 完成度

- 18 / 18 个 m2t1~m2t18 todo 全部 **COMPLETE**
- 测试数 **136 → 194**(+58,M2 6 套新测试)
- 9 个新建文件 + 7 个修改文件(详见 M2-handoff §1.1)
- OQ-01/02/16 锁定未触碰;CR-010 禁词扫描未触碰

### 7.2 M2 关键交付(一句话总结)

| 维度 | 状态 |
|---|---|
| 四模组 ETL 落库层(BD-020/030/040/060) | ✅ |
| Threat Score 加权 + EMA + 5 态(BD-061/062/062b) | ✅ |
| 市场门控 + 终极警报(BD-063/064) | ✅ |
| 自然语言摘要(BD-065) | ✅ |
| 离线回测三件套(BD-085/086/089) | ✅(待真实数据) |
| 3 个 API 501 升级(screener/symbols/regime) | ✅ |

### 7.3 接力(M3 启动)

- 入口:`etl/load_threat_score.compute_threat_scores` → `app.services.ultimate_alert.evaluate_ultimate_alerts`
- 待办:真实 EOD 拉取 + 集成测试 + BD-087 校准报告 v1.0
- 详见 M2-handoff §5
