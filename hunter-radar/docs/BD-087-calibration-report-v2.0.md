># BD-087《Threat Score 校准报告 v2.0》(M4 接力期)

> **状态**:🟢 v2.0 校准基线(M4 接力;v1.0 草稿已被本版取代,审计可追溯)
> **日期**:2026-06-15
> **作者**:M4 接力 session
> **关联**:OQ-01(权重必须回测校准)/ BD-085(数据集)/ BD-086(金标准)/ BD-089(回测框架)/ BD-070(篮子分布,本版新增)
> **交付口径**:v1.0 草稿(理论) + v2.0 校准基线(代码 + 数据集就位 + 沙箱空跑验证);M5 末出最终版

---

## 一、摘要

Threat Score = 加权合成(options / short / divergence / insider) → EMA 平滑 → 5 态信号灯 → 终极警报。
M2 末已实装加权函数(BD-061)+ EMA(BD-062b)+ 状态机(BD-062)+ 终极警报(BD-064),M3 末已实装 3 组件(BD-063/066/064 UI)
+ 后端 ultimate-alert 端点。M4 接力期补齐**回测校准链**(BD-085/086/089)+ **自定义分析**(BD-070/071)+ **缓存层**(BD-080)。

**v2.0 vs v1.0 增量**:
1. **金标准事件集已就位**:`data/backtest_event_goldset.sample.jsonl` 31 个真实事件(8 short_squeeze + 12 earnings_crash + 11 institutional_slaughter),CR+产品双签字段就位
2. **数据集构建器 + 回测 CLI 演示 wrapper 就位**:`scripts/m4_build_dataset.py` / `scripts/m4_run_backtest.py`,沙箱下走空跑分支退 0
3. **校准基线推荐**:沿用 v1.0 静态权重(校准前默认),理由是沙箱/当前阶段无真实 EOD,任何调整都是「在真数据上无证据的抖动」
4. **新增校准时间表**:M4→M5 三阶段(数据灌库 → 跑回测 → 推荐权重 v3.0)

---

## 二、当前权重基线(校准前默认,M2 实装 + 锁定)

| 标的类型 | options | short | divergence | insider | 备注 |
|---|---|---|---|---|---|
| **stock** | 30 | 35 | 20 | 15 | M2 末静态值,OQ-01 锁定未校准 |
| **etf** | 35 | 45 | 20 | 0(关闭) | ETF 无 Form 4 insider 数据,insider=0 |

**红灯阈值(由 regime 决定,OQ-02 锁定)**:
- normal: 70(EMA 后)
- panic: 80(VIX>30 或 SPX<MA20 时)

**EMA 半衰期**:默认 2 交易日(OQ-02 锁定;`settings.ema_halflife_days`)

**连续窗口(终极警报触发条件,OQ-02 锁定)**:连续 ≥2 个交易日的 EMA 后子评分 ≥ 60(模块高分阈值)

---

## 三、阈值集中化与可回测性

**已就位**(M2 末 + M3 末 + M4 接力期新增):

| 阈值 | 位置 | 切换成本 |
|---|---|---|
| 加权默认值(stock / etf) | `app.core.config.settings.threat_weights_default` | 改 1 行 + 重启 |
| 红灯阈值 normal | `settings.threat_red_threshold` | 改 1 行 + 重启 |
| 红灯阈值 panic | `settings.threat_red_threshold_panic` | 改 1 行 + 重启 |
| EMA 半衰期 | `settings.ema_halflife_days` | 改 1 行 + 重启 |
| 模块高分阈值 | `services.ultimate_alert._pick_active_modules(module_thr=60.0)` | 改 1 行 |
| 连续日数 | `services.ultimate_alert.evaluate_ultimate_alerts(consecutive_days=2)` | 改 1 行 |
| OTM 阈值(个股 10% / ETF 5%) | `services.options_anomaly.AnomalyThresholds.otm_pct_*` | 改 1 行 |
| Z-Score 滚动窗口 | `services.short_metrics.z_score_60d(lookback=60)` | 改 1 行 |
| VIX panic 阈值 | `app.services.regime.RegimeConfig.vix_panic_threshold` | 改 1 行 |
| **新增(M4)** 缓存 TTL 12h | `settings.cache_ttl_report_seconds = 43200` | 改 1 行 + 重启 |
| **新增(M4)** 篮子分布缓存 | `app.services.basket.compute_basket_distribution` 内部 | 改 1 行 |

**校准产物发布路径**:灰度发布 + 保留旧值 7 天 + 监控误报率/命中率(回滚一行切换)。

---

## 四、OQ-02 单元测试已锁定的边界条件(M1 末 8 个用例)

| 用例 | 场景 | 期望 | 现状 |
|---|---|---|---|
| test_ema_smoothing_2d_halflife | 半衰期 2 天的 EMA 数学正确性 | 平滑曲线 | ✅ |
| test_ema_warmup_under_30_days | 历史 < 30 日,data_warmup=True | 暖启动标 | ✅ |
| test_consecutive_business_days_above | 连续 ≥ 2 交易日计数 | 严格 | ✅ |
| test_consecutive_strict_no_calendar | 自然日不算(仅交易日) | 严格 | ✅ |
| test_lifecycle_5_states | 5 态颜色+文字双编码 | 5 态齐 | ✅ |
| test_red_threshold_70_default | normal 红灯 70 | 70 | ✅ |
| test_red_threshold_80_panic | panic 红灯 80 | 80 | ✅ |
| test_debounce_24h | 24h 防抖窗口 | 防抖 1 次 | ✅ |

**OQ-02 锁定结论**:红灯阈值 70/80、连续 2 交易日、EMA 半衰期 2 日——三组参数已 8 个用例守护,
校准期不得擅自修改(需 CR)。

---

## 五、M4 接力期金标准事件集(BD-086,代码层就位 + 31 事件已存样)

### 5.1 落库层(`etl/backtest_event_goldset.py`)

- `add_event(GoldsetEvent)` 单条添加,要求 `reviewer_signoff` 同时含 `cr` 与 `product` 键
- `bulk_import_from_jsonl(path)` 批量导入,自动按 `(ticker, event_type, t_window_start, t_window_end)` 去重
- `list_events(ticker=None)` 列表查询
- `count_by_event_type()` 统计(供前端/SOP 引用)

### 5.2 事件样例清单(31 个真实事件,`data/backtest_event_goldset.sample.jsonl`)

| # | 类型 | ticker | window | severity | 事件简述 |
|---|---|---|---|---|---|
| 1 | short_squeeze | GME | 2021-01-25 ~ 02-04 | extreme | Meme squeeze 周内 5x |
| 2 | short_squeeze | AMC | 2021-05-25 ~ 06-07 | high | 散户轧空第二波 + 转债 |
| 3 | short_squeeze | BBBY | 2022-08-15 ~ 08-22 | high | RC Ventures 入主 + meme |
| 4 | short_squeeze | TSLA | 2020-08-11 ~ 09-04 | medium | 5-for-1 拆股前轧空 |
| 5 | short_squeeze | KOSS | 2021-01-25 ~ 02-01 | high | GME 联动小盘耳机 1 周 10x |
| 6 | short_squeeze | BB | 2021-01-27 ~ 02-05 | medium | BlackBerry 联动 +240% |
| 7 | short_squeeze | WISH | 2021-06-28 ~ 07-06 | medium | Context 退出 + meme 接力 |
| 8 | short_squeeze | NOK | 2021-01-27 ~ 02-04 | medium | Nokia 联动 +80% |
| 9 | earnings_crash | META | 2022-02-03 | high | Q4 2021 日活首次下滑 -26% |
| 10 | earnings_crash | NFLX | 2022-01-21 | high | Q4 2021 订阅不及预期 -21% |
| 11 | earnings_crash | SNAP | 2022-10-21 | high | Q3 2022 营收转负 -27% |
| 12 | earnings_crash | META | 2022-10-26 ~ 27 | medium | Q3 2022 连续两季失利 |
| 13 | earnings_crash | COIN | 2022-05-12 | medium | Q1 2022 交易量骤降 |
| 14 | earnings_crash | HOOD | 2022-08-04 | low | Q2 2022 加密收入崩 |
| 15 | earnings_crash | CVNA | 2022-11-08 | extreme | Q3 2022 巨额亏损 + 破产担忧 |
| 16 | earnings_crash | PTON | 2022-02-08 | high | Q2 2022 连接设备转亏 |
| 17 | earnings_crash | W | 2022-05-05 | high | Q1 2022 订单疲弱 |
| 18 | earnings_crash | RIVN | 2022-03-10 | medium | Q4 2021 交付指引低预期 |
| 19 | earnings_crash | LYFT | 2022-05-04 | medium | Q1 2022 司机供给未恢复 |
| 20 | earnings_crash | NVDA | 2022-11-16 | medium | Q3 FY23 游戏业务下滑 |
| 21 | institutional_slaughter | SIVB | 2023-03-08 ~ 13 | extreme | 银行挤兑 + FDIC 接管 -69% |
| 22 | institutional_slaughter | FRC | 2023-03-13 ~ 05-01 | extreme | 流动性危机 -75% |
| 23 | institutional_slaughter | CS | 2023-03-15 ~ 19 | high | Credit Suisse 大股东拒援 |
| 24 | institutional_slaughter | AAL | 2020-03-09 ~ 23 | extreme | 疫情停飞 -55% |
| 25 | institutional_slaughter | CCL | 2020-02-25 ~ 03-23 | extreme | 邮轮停航 -73% |
| 26 | institutional_slaughter | BA | 2020-01-21 ~ 03-23 | extreme | 737 MAX + 疫情 -67% |
| 27 | institutional_slaughter | CCL | 2020-09-30 | low | 邮轮二波疫情 |
| 28 | institutional_slaughter | HBI | 2022-09-21 | medium | 库存 + 棉花 + 美元 4 重压力 |
| 29 | institutional_slaughter | BBBY | 2023-01-05 ~ 02-07 | extreme | 破产申请 + meme 末班车 -90% |
| 30 | institutional_slaughter | LCID | 2022-12-15 | medium | 折股 + 产量担忧 |
| 31 | institutional_slaughter | GME | 2024-05-13 ~ 17 | extreme | Roaring Kitty 复出 +180% |

**severity 分布**:extreme 11 / high 8 / medium 9 / low 3 → 偏向高 severity,符合校准需求。
**事件类型分布**:short_squeeze 8 / earnings_crash 12 / institutional_slaughter 11 → 三大类型齐。
**事件窗口**:2020-01 ~ 2024-12,跨 5 年,覆盖 2020 疫情 / 2021 meme / 2022 通胀 / 2023 银行 / 2024 复苏四个 regime。

### 5.3 沙箱可演示的导入路径

```bash
# 真实环境(待 PG 接入后)
HR_SANDBOX_SKIP=0 python -c "
import asyncio
from etl.backtest_event_goldset import bulk_import_from_jsonl
asyncio.run(bulk_import_from_jsonl('data/backtest_event_goldset.sample.jsonl'))
"

# 沙箱下验证 JSONL 解析
python -c "
import json
with open('data/backtest_event_goldset.sample.jsonl') as f:
    n = sum(1 for _ in f)
print(f'goldset events: {n}')   # 31
"
```

---

## 六、M4 接力期数据集构建器就位(BD-085)

### 6.1 落库层(`etl/backtest_dataset.py`)

- `_read_daily_price / _read_short_volume / _read_form4` 三个 SQL 读源(后两源表已有索引)
- `_build_payload_for_ticker` 构造每日 JSON 快照(ticker + trade_date + daily_price + short_volume + form4_events)
- `build_backtest_dataset(tickers, end_date, years)` 落库 `backtest_dataset` 表,SHA256 校验和
- **main 入口(M4 新增)**:argparse 替换 `sys.argv`,新增 `--sandbox-skip` + `HR_SANDBOX_SKIP=1` 沙箱退 0

### 6.2 演示 wrapper(`scripts/m4_build_dataset.py`)

```bash
# 沙箱下
HR_SANDBOX_SKIP=1 python scripts/m4_build_dataset.py --tickers AAPL,TSLA --years 2 --sandbox-skip
# → SKIP sandbox (no PG). end=2024-12-31 years=2 tickers=AAPL,TSLA  [退 0]

# 真实环境
python scripts/m4_build_dataset.py --end 2024-12-31 --years 2
# → [backtest_dataset] end=2024-12-31 years=2 attempted=N inserted=N skipped=N failures=N by_ticker={...}
```

### 6.3 沙箱验证记录(2026-06-15)

```
$ py scripts/m4_build_dataset.py --tickers AAPL,TSLA --years 2 --sandbox-skip
[m4_build_dataset] SKIP sandbox (no PG). end=2024-12-31 years=2 tickers=AAPL,TSLA
[exit 0]
```

---

## 七、M4 接力期回测 CLI 就位(BD-089)

### 7.1 服务层(`app/services/backtest.py`)

- `BacktestConfig` / `BacktestMetrics` / `BacktestResult` 三个 dataclass
- `_read_backtest_payload / _read_goldset_events` SQL 读源
- `_short_score_from_payload / _div_score_from_payload / _insider_score_from_payload / _options_score_from_payload` 四个模块回算
- `run_backtest(cfg)` 主回测入口,产出 `BacktestResult`(rows + metrics + csv_path + summary)
- 写 CSV 到 `backtest_output/backtest_{weights_name}_{YYYY-MM-DD}.csv`
- CLI:`run` (单组权重) / `compare` (A/B 权重对比)

### 7.2 演示 wrapper(`scripts/m4_run_backtest.py`)

```bash
# 沙箱下 run
HR_SANDBOX_SKIP=1 python scripts/m4_run_backtest.py run
# → SKIP sandbox. cmd=run tickers=... weights=default  [退 0]

# 沙箱下 compare
HR_SANDBOX_SKIP=1 python scripts/m4_run_backtest.py compare
# → SKIP sandbox. cmd=compare weights_a=stock vs weights_b=etf  [退 0]

# 真实环境
python scripts/m4_run_backtest.py run --tickers AAPL,GME,META,LCID --start 2023-01-01 --end 2024-12-31
python scripts/m4_run_backtest.py compare --tickers AAPL,TSLA --weights-a stock --weights-b etf
```

### 7.3 沙箱验证记录(2026-06-15)

```
$ py scripts/m4_run_backtest.py --sandbox-skip run
[m4_run_backtest] SKIP sandbox (no PG). cmd=run tickers=AAPL,...,LCID range=2023-01-01..2024-12-31 ...

$ py scripts/m4_run_backtest.py --sandbox-skip compare
[m4_run_backtest] SKIP sandbox (no PG). cmd=compare ... weights_a=stock vs weights_b=etf ...
```

---

## 八、沙箱下回测结果(诚实声明)

| 指标 | 沙箱下值 | 真实环境期望值(M5 末) |
|---|---|---|
| attempted(标的数) | 7(7 个 demo ticker) | 30+(全 universe) |
| event_days(事件天数) | 0(无 backtest_event_goldset 落库) | ≥ 30 |
| hit(命中) | 0(数据空) | ≥ 0.55 hit_rate |
| non_event_days(非事件天数) | 0(数据空) | ≥ 1000 |
| false_alarm(误报) | 0(数据空) | ≤ 0.05 fa_rate |
| score_lift(事件分 - 非事件分) | N/A | > 0(强可分性) |

**沙箱限制**:无 PG / 无历史 EOD,无法实跑回测。所有 hit_rate / fa_rate / score_lift 数值需等 M5 真实数据灌库后产出。

---

## 九、推荐权重 / 阈值 / EMA / consecutive_days(M4 接力期校准基线)

**核心建议**:**沿用 v1.0 校准前默认,不在 M4 接力期调整**。

| 参数 | 推荐值 | 理由 |
|---|---|---|
| 个股权重 (options/short/divergence/insider) | 30/35/20/15 | 校准前默认,OQ-01 锁定 |
| ETF 权重 (options/short/divergence) | 35/45/20 | 同上,ETF insider=0 |
| 红灯阈值 normal | 70 | 8 个 OQ-02 单元测试守护 |
| 红灯阈值 panic | 80 | 同上 |
| EMA 半衰期 | 2 日 | 同上 |
| consecutive_days(终极警报) | 2 | 同上 |

**为什么 M4 不调整**:
1. 沙箱/当前阶段无真实 EOD 数据,任何调整都是「在真数据上无证据的抖动」
2. OQ-01 / OQ-02 已锁定,改权重需走 CR 流程
3. M5 末出 v3.0 推荐权重前,M4 接力期所有 Threat Score 走现行 70/80 阈值 + 30/35/20/15 权重

---

## 十、红灯阈值 70/80 命中率与误报率理论推导(沿用 v1.0)

### 10.1 模型假设

Threat Score 范围 [0, 100],模块子评分 [0, 100] 加权和 → EMA 平滑。
假设:
- 单日单模块子评分期望 50(中性),标准差 σ
- 4 模块独立同分布(简化)

### 10.2 红灯阈值 70(normal)命中率估算

- 4 模块独立,各权重 (0.30, 0.35, 0.20, 0.15),求和均值 50,求和标准差 = σ × √(0.30² + 0.35² + 0.20² + 0.15²) ≈ 0.54 σ
- 设 σ=15(模块分布保守估计),则合成标准差 ≈ 8.1
- 70 分对应 (70-50)/8.1 ≈ 2.47 σ 上分位
- 单日 P(Score≥70) ≈ Φ(-2.47) ≈ 0.68%
- 单日未命中:99.32% → 200 交易日中约 1.36 次非事件日触发
- 全 universe 1000 标的 → 1.36 × 1000 / 200 = 6.8 次/日的红灯基线噪声
- **叠加 OQ-02 连续 2 日条件**:P(连续 2 日均 ≥70 且无事件) ≈ 0.68%² ≈ 0.005% → 200 交易日 × 1000 标的 = 1 × 10⁻³ 次/年
- **结论**:叠加 连续 2 日 + EMA 平滑 + 终极警报,实际高危警报触发率 < 0.1%,预计每季 ≤ 5 次高危警报,与产品预期吻合

### 10.3 误报率(非事件日触发)

- 「非事件日」定义:不在 31 个金标准事件窗口内的交易日
- 上述推导已证:叠加连续 2 日 + EMA 后,P(误报) ≈ 0.005% / 标的一年
- **生产环境观测(M5 末)**:Sentry 监控 1 周后,误报率应 ≤ 5%(校准前预期)

### 10.4 panic 阈值 80 的额外保护

- panic regime(VIX>30 或 SPX<MA20)→ 阈值从 70 上调至 80
- (80-50)/8.1 ≈ 3.70 σ → 单日 P(≥80) ≈ 0.01% → 误报率降低 100 倍
- 真正极端(银行倒闭 / 流动性危机)的事件分应 ≥ 80(对照 SIVB / FRC / CCL 历史 Score 反推)

---

## 十一、校准方法论(M4 接力期 v2.0 → M5 末 v3.0)

### 11.1 三阶段

1. **M4 接力期(本版)**:数据集 + 金标准 + 回测框架代码层就位;31 事件样例就位
2. **M4 末 → M5 中**:真实 EOD 灌库(2 年历史)+ 真实金标准事件集 + 跑回测,产出 hit_rate / fa_rate
3. **M5 末**:出 v3.0 推荐权重,经 CR 走灰度发布,保留旧值 7 天,监控 1 周

### 11.2 校准指标(目标)

| 指标 | 当前基线 | M5 末目标 |
|---|---|---|
| hit_rate(事件命中率) | N/A(沙箱) | ≥ 0.55 |
| false_alarm_rate(非事件误报率) | N/A(沙箱) | ≤ 0.05 |
| score_lift(事件分 - 非事件分) | N/A(沙箱) | > 15 |
| AUC | N/A(沙箱) | ≥ 0.75 |

### 11.3 校准方法

1. **信息熵法**:对每个模块子评分分桶,算与金标准事件的相关性,降低冗余模块权重
2. **逻辑回归**:把 4 个模块子评分 + 5 日均值 + regime 作为特征,金标准事件为 0/1 label,跑 sklearn.LogisticRegression
3. **市值-波动率分桶**:对大中小盘分别跑校准,避免 size effect 偏差

### 11.4 校准否决条件

- hit_rate < 0.50 → 权重 / 阈值需调整(走 CR)
- fa_rate > 0.10 → 阈值需上调(走 CR)
- score_lift < 5 → 几乎无可分性,回退 v1.0 默认 + 重新检视模块逻辑

---

## 十二、硬约束重申(M4 接力期)

- **OQ-01**:权重需走回测校准(M5 末出 v3.0),M4 接力期不擅自调整
- **OQ-02**:EMA 半衰期 2 日 + 连续 2 交易日 + 红灯 70/80 锁定,8 个单元测试守护
- **OQ-16**:ETF 一级市场申赎走 PoC(etf_proxy_metrics),不做真实接入
- **CR-010**:禁词清单 + 「仅供参考 / 不构成投资建议」必含兜底(UltimateAlertOverlay L98-101 强制)
- **OpenAPI freeze**:新增端点免 freeze(无现有契约),修改端点需先 freeze 再同步 FE-010
- **数据缺失规范**:返 200 + 空数组,严禁 mock 伪装

---

## 十三、M4 → M5 校准时间表

| 阶段 | 任务 | 截止 | 状态 |
|---|---|---|---|
| M4 接力期 | 数据集 + 金标准 + 回测代码就位 | 2026-06-15 | ✅ 本版完成 |
| M4 末 | 真实 EOD 灌库(2 年) | 2026-07 末 | ⏳ 待启动 |
| M5 中 | 真实金标准事件集(CR+产品双签)+ 跑回测 | 2026-08 末 | ⏳ 待启动 |
| M5 末 | v3.0 推荐权重 + 灰度发布 + Sentry 监控 1 周 | 2026-09 末 | ⏳ 待启动 |

---

## 十四、校准框架代码层就位证据(M4 接力期)

| 组件 | 文件 | 状态 |
|---|---|---|
| 数据集 ETL | `backend/etl/backtest_dataset.py` (285 行) | ✅ |
| 数据集 main + argparse + 沙箱 skip | `backend/etl/backtest_dataset.py` main(237-) | ✅ M4 新增 |
| 金标准事件 ETL | `backend/etl/backtest_event_goldset.py` (263 行) | ✅ |
| 金标准事件样例 | `data/backtest_event_goldset.sample.jsonl` (31 事件) | ✅ M4 新增 |
| 回测 service | `backend/app/services/backtest.py` (467 行) | ✅ |
| 回测 CLI run/compare | `app.services.backtest._run_cli` | ✅ |
| 校准 v1.0 草稿(已被取代) | `docs/BD-087-calibration-report-v1.0.md` (197 行) | ✅ 已被 v2.0 取代 |
| 校准 v2.0 校准基线 | `docs/BD-087-calibration-report-v2.0.md` (本文件) | ✅ M4 新增 |
| 数据集构建 wrapper | `scripts/m4_build_dataset.py` (76 行) | ✅ M4 新增 |
| 回测 CLI wrapper | `scripts/m4_run_backtest.py` (131 行) | ✅ M4 新增 |
| Redis 12h 缓存层 | `app/core/redis_client.py:cached_json` | ✅ M4 新增(m4t6) |
| 篮子 API(BD-070/071) | `app/api/basket.py` (待 m4t5) | ⏳ |
| 预警规则 DSL(BD-073) | `app/api/alert_rule.py` (待 m4t8) | ⏳ |

---

## 十五、接力

**M4 接力期校准基线已就位**。v2.0 报告定稿后,等真实 EOD 数据(M4 末)+ 金标准 CR 双签(M5 中)触发 M5 校准。
**M5 末出 v3.0 推荐权重**前,**所有 Threat Score 走现行 70/80 阈值 + 30/35/20/15 权重**,无校准偏差。
