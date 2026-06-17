# Hunter Radar V1.4 — M1 → M2 启动完成报告(W0 + W1 末)

> **✅ 状态:M2 四模组实装已完成**(2026-06-15,W1 末)。
> 本文为 M1 → M2 启动接续的总结报告;M1 收尾报告保留于 [M1-handoff.md](M1-handoff.md)。
> 历史会话档案见 [SESSION-CLOSED.md](SESSION-CLOSED.md)。
>
> **M2 末硬指标**:
> - 四模组 ETL 计算层全实装(BD-020/030/040/060 + BD-061 加权)
> - Threat Score 串接到 `etl/pipeline.py`,实装 4 模组 → 5 态信号灯 → 落库全链路
> - 市场门控(BD-063)+ 状态机(BD-062/062b)+ 终极警报(BD-064)就位
> - 自然语言摘要(BD-065)+ 90 日轨迹(BD-066)服务化
> - 离线回测三件套(BD-085/086/089)就绪,等真实 EOD 数据 + 金标准事件集 review
> - 6 套新测试覆盖,测试数 136 → 194(+58)
> - 合规文案 CI 仍锁,EMA 公式与 OQ-01/02/16 决策未触碰

## 一、M2 增量交付清单(本会话增量)

### 1.1 新增 / 升级文件清单

| 类型 | 路径 | 行数 | 关键职责 |
|---|---|---|---|
| **新建(etl 计算层)** | `etl/load_short_ratio.py` | 287 | BD-030/031/032 短仓比 + 60 日 Z-Score + ATS% 落库;OQ-01 阈值集中 |
| **新建(etl 计算层)** | `etl/load_divergence.py` | 284 | BD-040/041/042 量价背离落库;连续 ≥2 日 rising→confirmed 升级 |
| **新建(etl 计算层)** | `etl/load_threat_score.py` | 511 | BD-060/061/062/062b 4 模组加权 + EMA 平滑 + 5 态信号灯 + 落库 |
| **新建(etl 回测)** | `etl/backtest_dataset.py` | 265 | BD-085 历史 EOD 数据集构造 + SHA256 payload 锁 |
| **新建(etl 回测)** | `etl/backtest_event_goldset.py` | 263 | BD-086 金标准事件集管理 + reviewer_signoff 强制 |
| **新建(services)** | `app/services/regime.py` | 160 | BD-063 市场门控(SPX MA20 + VIX 阈值 + panic 模式) |
| **新建(services)** | `app/services/backtest.py` | 467 | BD-089 离线回测 CLI(run/compare)+ A/B 权重对比 |
| **新建(services)** | `app/services/nl_summary.py` | 173 | BD-065 自然语言摘要(stock/etf 双模板 + CR-010 禁词扫描) |
| **新建(services)** | `app/services/ultimate_alert.py` | 330 | BD-062/064 状态机 + 终极警报(EMA 后分 + 连续 ≥2 日 + 24h 防抖) |
| **修改(etl 拉取层)** | `etl/load_options_chain.py` | (10 行修复) | 修复 `_to_candidates` dte bug(`if False else 0` 写死为 0) |
| **修改(etl 拉取层)** | `etl/load_ats_short.py` | (+111 行) | 新增 `pull_finra_ats` 真实下载入口 + `main_weekly` CLI |
| **重写(etl 拉取层)** | `etl/sec_form4.py` | 287 | CIK 解析:走 SEC `/files/company_tickers.json` + `/submissions/CIK{cik}.json`;角色归一化 |
| **重写(api)** | `app/api/screener.py` | 96 | 真实 SQL 查询 threat_score_daily + symbol_master 联表 |
| **修改(api)** | `app/api/symbols.py` | (+144 行) | 3 个 501 升级:threat/divergence/threat-history |
| **重写(api)** | `app/api/regime.py` | (重写) | 真实 SQL 查询 + RegimeDTO(threshold_red/banner_text) |
| **修改(etl 编排)** | `etl/pipeline.py` | (+76 行) | 串接 compute_short_ratio / compute_divergence / compute_regime / compute_threat_score + regime 回填 |
| **新建(tests)** | `tests/test_load_short_ratio.py` | 125 | 5 纯函数 + 2 集成 mock |
| **新建(tests)** | `tests/test_load_divergence.py` | 132 | 2 纯函数 + 3 集成 mock |
| **新建(tests)** | `tests/test_load_threat_score.py` | 142 | 4 子评分纯函数 + 1 暖启动 + 2 集成 mock |
| **新建(tests)** | `tests/test_nl_summary.py` | 196 | 7 纯函数 + 5 render_summary + 2 render_simple_etf_proxy |
| **新建(tests)** | `tests/test_ultimate_alert.py` | 220 | 2 纯函数 + 5 集成 mock(覆盖 below/no_continuous/debounce/success 四分支) |
| **新建(tests)** | `tests/test_backtest.py` | 186 | 6 类纯函数 + dataclass 基础 |

### 1.2 测试增量统计

| 阶段 | 测试数 | 累计 |
|---|---|---|
| M0 末 | — | 8(仅 OQ-02 8 个) |
| M1 计算层 | +71 | 79 |
| M1 末 ETL + 编排 | +57 | **136** |
| **M2 启动新增 6 套** | **+58** | **194** |

## 二、关键设计决策与契约

### 2.1 阈值集中(OQ-01 锁定)

- 全部阈值走 `app.core.config.settings.*` 集中 dataclass:
  - `AnomalyThresholds`(末日 Put 过滤)
  - `RegimeConfig`(VIX/SPX 门控)
  - `threat_weights_default["stock" / "etf"]`(Threat Score 加权)
  - `threat_red_threshold` / `threat_red_threshold_panic`
  - `ema_halflife_days`(默认 2)
- 任何阈值改动:仅改 `settings.py`,不碰 service 文件 → BD-087 校准报告一行切换

### 2.2 EMA 平滑 + 状态机(OQ-02 锁定)

- `app.services.threat_score` 提供 5 个原语:
  - `ema_smooth(history, halflife_days=2)` — 平滑
  - `consecutive_business_days_above(series, threshold)` — 严格连续 N 日
  - `decide_lifecycle(ema, red_threshold)` — 5 态(red/yellow/gray/green/init)
  - `z_score_to_score(z)` / `percentile_to_score(p)` — 0-100 映射
  - `compute_threat_score(modules, weights, history, ema_halflife)` — 4 模组加权
- 8 个 OQ-02 单元测试锁住 EMA 公式,严禁改动
- 连续 ≥2 交易日窗口由 `consecutive_business_days_above` 严格定义

### 2.3 落库模式(本仓库确立)

| 表 | 模式 | 用途 |
|---|---|---|
| `short_volume_daily` | `ON CONFLICT DO NOTHING (trade_date, symbol, source)` | FINRA 每日做空,主键不重 |
| `ats_short` | 同上 | FINRA 周报 |
| `form4_event` / `buyback_event` | 同上 | SEC 不可变事件 |
| `daily_price` | `ON CONFLICT DO UPDATE` | 修正 yfinance 历史回填 |
| `options_chain` | `ON CONFLICT DO NOTHING` | Yahoo 期权合约 |
| `option_anomaly` | `ON CONFLICT DO UPDATE` | 末日 Put 重算可覆盖 |
| **`short_ratio_daily`** | `ON CONFLICT DO UPDATE` | Z-Score 重算可覆盖 |
| **`divergence_window`** | `ON CONFLICT DO UPDATE` | 量价背离重算可覆盖 |
| **`threat_score_daily`** | `ON CONFLICT DO UPDATE` | Threat Score 重算可覆盖 |
| **`ultimate_alert`** | `ON CONFLICT DO NOTHING (trade_date, symbol)` | 终极警报(同交易日同 symbol 不重) |

### 2.4 终极警报触发(BD-062/064 决策)

- 严格三连条件(同时满足才触发):
  1. Score EMA ≥ 阈值(normal=70, panic=80)
  2. 至少 1 个核心模块(EMA 后子评分 ≥ 60)**连续 ≥2 个交易日**同时高分
  3. 24 小时内未触发(防抖)
- **严禁** 仅基于单日 EMA 前原始分触发
- 状态机按 OQ-02 决策:连续 N 日 = EMA 后连续 ≥ 阈值

### 2.5 自然语言摘要(BD-065)

- 模板集中:`MODULE_TEMPLATES_STOCK` / `MODULE_TEMPLATES_ETF`
- 阈值常量:`_THRESHOLD_HIGH=70`, `_THRESHOLD_MID=50`
- 禁词兜底:`_sanitize` 扫描 `settings.forbidden_recommendation_words`,命中即抛 ValueError
- 不使用 emoji 与营销词(CR-003 / CR-009)
- 末日文案:`"无投资建议"` 兜底

## 三、立即可跑(本地)

```bash
cd "d:\Financial Project\Hunter Radar\hunter-radar"
make up
cd backend
uv sync --extra dev

# 1) M1 末基础数据
uv run python -m etl.symbol_seed
uv run python -m etl.pipeline 2024-02-01          # 编排器 smoke

# 2) M2 启动
uv run python -m etl.load_short_ratio 2024-02-01  # 短仓比 + Z
uv run python -m etl.load_divergence 2024-02-01   # 量价背离
uv run python -m app.services.regime 2024-02-01   # 市场门控
uv run python -m etl.load_threat_score 2024-02-01 # 4 模组加权 + 5 态
uv run python -m app.services.ultimate_alert 2024-02-01  # 终极警报
uv run python -m app.services.nl_summary 2024-02-01 AAPL # 自然语言摘要

# 3) 回测三件套
uv run python -m etl.backtest_dataset 2024-02-01 2
uv run python -m etl.backtest_event_goldset add \
    --ticker AAPL --start 2024-01-15 --end 2024-01-25 \
    --severity high --type insider_dump \
    --reviewer "cr+product"
uv run python -m app.services.backtest run \
    --tickers AAPL --start 2023-01-01 --end 2024-01-01

# 4) 全部测试
uv run pytest -q                                    # 期望 194 passed

# 5) 合规扫描
cd ..
python scripts/compliance_check.py frontend/src backend/app
```

## 四、已知风险与防雷

| ID | 风险 | 状态 | 缓解 |
|---|---|---|---|
| R-12 | SEC EDGAR / FINRA ATS 真实数据源沙箱不可达 | 🟡 M2 启动已实现入口,需本地或代理 | httpx + tenacity 限流;失败时返回 `pending_disclosure`(BD-081) |
| R-13 | 沙箱无 PG,集成测试仅 Mock 验证 | 🟡 待本地集成 | 沙箱跑测试 → 静态 mock;本地 `make up` 后跑真实集成 |
| R-14 | EMA 公式修改破坏历史 Score 对比 | 🟢 8 个 OQ-02 测试锁 | 灰度发布 + 配置版本号 |
| R-15 | 终极警报单日触发毛刺 | 🟢 严格 EMA + 连续 ≥2 日 + 24h 防抖 | 决策写入 `docs/oq/BD-062-decision.md` |
| R-16 | `etl/pipeline.compute_threat_score` 之前是占位 | 🟢 M2 已实装 | 串接 4 模组 → 5 态 → 落库 → regime 回填 |

## 五、给「M3 接力者」的一句话

- **M2 主体已就绪**:四模组 ETL + Threat Score + 终极警报 + 自然语言摘要 + 回测三件套,共 **194 个测试** 静态可过。
- **M3 启动入口**:`etl/load_threat_score.compute_threat_scores` → `app.services.ultimate_alert.evaluate_ultimate_alerts` → `app.services.nl_summary.render_summary`
- **不要触碰**:
  - `scripts/compliance_check.py` 禁词清单(可加,需 CR)
  - `app.services.threat_score` 的 EMA 公式(8 个 OQ-02 测试守护)
  - `settings.forbidden_recommendation_words`(CR-010 红线)
- **M3 待办**(M2 末未做,留给 M3):
  - [ ] 真实 EOD 拉取(yfinance/本地缓存),跑通 `etl/pipeline` 真实数据链路
  - [ ] BD-085 历史数据集 1-2 年 EOD 真实落库
  - [ ] BD-086 金标准事件集 ≥30 个(CR + 产品双人 review)
  - [ ] BD-087 校准报告 v1.0
  - [ ] 前端 5 个 API 真实对接(`api.ts` 移除 TODO 占位)
  - [ ] 集成测试(`make up` 后跑 `tests/test_load_*.py`)
  - [ ] Airflow DAG 切到生产模式(去掉 `M1 阶段模板`注释)

## 六、OQ 决策锁定

| OQ | 决策 | 落地点 |
|---|---|---|
| OQ-01 权重回测校准 | 阈值集中在 `settings.*` dataclass | `app/core/config.py` + 6 个 services |
| OQ-02 EMA 半衰期 2 日 + 连续 2 交易日 | `app/services/threat_score.py` 8 个测试 | `tests/test_threat_score.py` |
| OQ-16 ETF 代理指标 PoC | `short_metrics.etf_proxy_anomaly_score()` | `app/services/short_metrics.py` |
| OQ-09 / OQ-11 | **项目忽略** | 不在范围 |
| OQ-22 数据暖启动 | `data_warmup` 字段就位 + UI 提示 | `api.getThreatScore` 返回值 + `nl_summary._warmup_text` |
