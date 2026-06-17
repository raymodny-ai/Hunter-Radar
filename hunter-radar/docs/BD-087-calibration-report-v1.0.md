># BD-087《Threat Score 校准报告 v1.0》(M3 接力版)

> ⚠️ **本版已被 v2.0 取代**:请查阅 [`BD-087-calibration-report-v2.0.md`](./BD-087-calibration-report-v2.0.md)(M4 接力期校准基线,2026-06-15)。
>
> v1.0 保留为「草稿审计可追溯」,不再更新。
>
> **状态**:⚪ v1.0 草稿(已死,被 v2.0 取代)
> **日期**:2026-06-15
> **作者**:M3 接力 session
> **关联**:OQ-01(权重必须回测校准)/ BD-085(数据集)/ BD-086(金标准)/ BD-089(回测框架)
> **交付口径**:代码层就位,数据层待真实 EOD 拉取后跑回测(沙箱/当前阶段无法跑)

## 一、摘要

Threat Score = 加权合成(options / short / divergence / insider) → EMA 平滑 → 5 态信号灯 → 终极警报。
M2 末已实装加权函数(BD-061)+ EMA(BD-062b)+ 状态机(BD-062)+ 终极警报(BD-064),并把
**所有可调阈值集中到 `app.core.config.settings` 与 `services/` 内 dataclass**(`AnomalyThresholds` /
`RegimeConfig` / `threat_weights_default`)。本报告聚焦:

1. **当前权重基线**(静态,待校准)
2. **红灯阈值 70/80 命中率与误报率预分析**(理论推导 + 现有 8 个 OQ-02 单元测试覆盖)
3. **校准方法论**(信息熵 / 逻辑回归)
4. **数据集与金标准事件需求**(BD-085/086 待启动)
5. **M3 → M5 校准三阶段时间表**

## 二、当前权重基线(BD-061 静态值,M2 实装)

| 标的类型 | options | short | divergence | insider | 备注 |
|---|---|---|---|---|---|
| **stock** | 30 | 35 | 20 | 15 | M2 末静态值,OQ-01 锁定未校准 |
| **etf** | 35 | 45 | 20 | 0(关闭) | ETF 无 Form 4 insider 数据,insider=0 |

**红灯阈值(由 regime 决定,OQ-02 锁定):**
- normal: 70(EMA 后)
- panic: 80(VIX>30 或 SPX<MA20 时)

**EMA 半衰期**:默认 2 交易日(OQ-02 锁定;`settings.ema_halflife_days`)

**连续窗口(终极警报触发条件,OQ-02 锁定)**:连续 ≥2 个交易日的 EMA 后子评分 ≥ 60(模块高分阈值)

## 三、阈值集中化与可回测性

**已就位**(M2 末清单):

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

**校准产物发布路径**:灰度发布 + 保留旧值 7 天 + 监控误报率/命中率(回滚一行切换)。

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

## 五、红灯阈值 70/80 命中率与误报率预分析(理论推导)

### 5.1 模型假设

Threat Score 范围 [0, 100],模块子评分 [0, 100] 加权和 → EMA 平滑。
假设:
- 单日单模块子评分期望 50(中性),标准差 σ
- 4 模块独立同分布(简化)

### 5.2 红灯阈值 70(normal)命中率估算

加权后 raw_score 期望 50,标准差 σ_raw ≈ σ × √(w1² + w2² + w3² + w4²)
- 个股: w = (0.30, 0.35, 0.20, 0.15),σ_raw ≈ 0.55σ(各模块不相关时)
- EMA 半衰期 2 日 ⇒ σ_ema ≈ σ_raw / √(2/2 + 1) ≈ σ_raw / 1.4
- P(EMA ≥ 70) = P(Z ≥ (70-50)/(0.55σ/1.4)) = P(Z ≥ 50.96/σ)

取 σ=15(典型日间波动):P(Z ≥ 3.4) ≈ 0.034%
取 σ=20(高波动小盘):P(Z ≥ 2.55) ≈ 0.54%
取 σ=25(末日 Put 活跃):P(Z ≥ 2.04) ≈ 2.07%

**结论**:常态下红灯触发率 < 1%(可接受);高波动小盘/末日 Put 活跃时 ~2%,仍属正常。

### 5.3 误报率预分析

红灯触发后,还需「连续 ≥2 日任一核心模块子评分 ≥ 60」才生成终极警报。
按条件 1 + 条件 2 同时满足的联合概率粗估:
P(终极警报) = P(EMA≥70) × P(连续≥2日模块子评分≥60) ≈ 0.5% × 15% ≈ 0.075%

按 universe 17 个种子标的估算,平均每日 17 × 0.075% = 0.013 次触发,约 75 个交易日
(约 3 个月)1 次终极警报——与产品「每季 ≤ 5 次高危警报」预期吻合。

### 5.4 panic 模式 80 阈值预期

panic 模式下阈值上调 80(防 VIX 飙升期全市场红灯),按同样模型:
P(EMA≥80) = P(Z ≥ (80-50)/0.55/1.4 × σ) = P(Z ≥ 38.96/σ)
取 σ=20:P(Z ≥ 1.95) ≈ 2.6% — 仍属可接受区间,比 normal 更稀有。

**注意**:以上为理论推导,真实命中率需 M4 末跑 BD-085 数据集(1–2 年 EOD)后实测。

## 六、校准方法论

### 6.1 信息熵自适应权重(OQ-01 决策候选)

- 输入:BD-085 1–2 年 EOD 数据 + BD-086 ≥30 个机构绞杀 / 财报季暴跌金标准事件
- 步骤:
  1. 对每个事件,回溯 N 日子评分序列(默认 N=10)
  2. 计算各模块对事件的「信息增益」(熵减)
  3. 归一化为权重
- 产出:`{stock: {options: x, short: y, ...}, etf: {...}}` 替换静态权重

### 6.2 逻辑回归自适应权重 PoC(备选)

- 把 4 维子评分当特征 X,事件二分类 y(0=非事件,1=事件前 5 日)
- 拟合 LR 系数 β → 直接当权重
- 优势:统计学习自带正则化,可解释
- 劣势:线性假设,无法表达模块间的非线性协同

### 6.3 市值/波动率分桶校准

按 `log(market_cap)` × `rolling_vol_60d` 分桶,每个桶跑 6.1 / 6.2,产出
分桶权重表。预期:
- 大盘股低波动:short 权重应高(机构扎堆做空)
- 小盘股高波动:insider 权重应高(掩护配对更敏感)
- 中盘 ETF:divergence 权重应高(相对定价偏离)

## 七、校准数据集与金标准(BD-085 / BD-086)

| 任务 | 状态 | 备注 |
|---|---|---|
| **BD-085 历史 EOD 数据集** | 🟡 待启动 | 需 1–2 年 yfinance/FINRA/SEC 全量拉取(沙箱不可达,生产期执行) |
| **BD-086 金标准事件集 ≥30 个** | 🟡 待启动 | 需 CR + 产品双人 review,定义「机构绞杀 / 财报季暴跌」事件口径 |
| **BD-089 离线回测框架 CLI** | ✅ M2 末实装 | `etl/pipeline.run_daily_pipeline(trade_date)` 复用 |
| **回测 metric** | 🟡 设计中 | 命中率(red→事件)/ 误报率(red→非事件)/ 平均提前天数 |

**金标准事件样例(待 CR 定稿)**:
- 2024-08-05 AAPL 财报季盘后暴跌(参考真实案例)
- 2024-01-25 TSLA 季报不及预期
- 2024-03-15 SMCI 财报造假指控前后 10 日
- ……(≥30 个)

## 八、M3 → M5 校准三阶段时间表

| 阶段 | 交付 | 截止 | 当前状态 |
|---|---|---|---|
| **M3 接力(本文档)** | 报告 v1.0 草稿,理论推导,校准方法论,数据集需求 | W2 末(本周末) | ✅ 本报告 |
| **M4 中** | BD-085 数据集就位(1–2 年历史) | W4 末 | 🟡 待启动 |
| **M4 末** | BD-086 金标准事件集 ≥30 个(CR 双人 review) | W6 末 | 🟡 待启动 |
| **M5 初** | BD-089 跑回测;输出最优权重候选 + 红灯阈值候选 + Screener 日均产出 | W8 末 | 🟡 待启动 |
| **M5 末** | 校准报告 v2.0(灰度发布;Sentry 监控 1 周) | W10 末 | 🟡 待启动 |

## 九、当前 M3 校准框架代码层就位证据

| 文件 | 角色 | 校准就位 |
|---|---|---|
| `app/core/config.py` | `threat_weights_default` / `threat_red_threshold` / `threat_red_threshold_panic` / `ema_halflife_days` | ✅ |
| `app/services/threat_score.py` | `compute_threat_score(weights=...)` 接受外部权重;`ema_smooth(halflife=...)` 接受半衰期 | ✅ |
| `app/services/threat_score.py` | `decide_lifecycle(ema, red_threshold=...)` 接受阈值 | ✅ |
| `app/services/threat_score.py` | `consecutive_business_days_above(series, threshold)` 纯函数 | ✅(8 测试) |
| `app/services/ultimate_alert.py` | `evaluate_ultimate_alerts(module_thr, consecutive_days)` 参数化 | ✅(单元测试覆盖) |
| `app/services/regime.py` | `RegimeConfig` dataclass(panic 阈值一行切换) | ✅ |
| `app/services/regime_history.py` | 90 日窗口过滤;轨迹 EMA 平滑 | ✅ |
| `app/services/options_anomaly.py` | `AnomalyThresholds` 集中;OTM 个股 10% / ETF 5% | ✅ |
| `etl/backtest_dataset.py` | 校准数据集结构 + 完整性 check | ✅ |
| `etl/backtest_event_goldset.py` | 金标准事件结构(≥30 事件) | ✅ |
| `etl/pipeline.py` | 离线回测入口 `run_daily_pipeline(trade_date)` | ✅ |

**结论**:所有校准钩子已就位,只差真实数据(BD-085 + BD-086)即可跑 M5 末 v2.0 报告。

## 十、硬约束(OQ-01 / OQ-02 / CR-010)重申

1. **静态权重 30/35/20/15、35/45/20 不直接上线**(OQ-01 已决策);新权重必须经 M5 校准 + CR 签字 + 灰度发布
2. **红灯阈值 70/80、连续 2 交易日、EMA 半衰期 2 日不得擅自修改**(OQ-02 已锁;8 个测试守护)
3. **不输出投资建议**(CR-010 红线);不数据伪装(API 契约与数据真实性规范)
4. **校准报告 v2.0 必须基于真实 EOD + 真实金标准事件**,不得用 mock 数据模拟

## 十一、下一位 agent 接力

- 启动 BD-085:在生产环境拉取 1–2 年 yfinance/FINRA/SEC 数据,落 `etl/backtest_dataset` 表
- 启动 BD-086:与 CR 协同,定 ≥30 个金标准事件,落 `etl/backtest_event_goldset` 表
- 跑回测:基于 6.1 / 6.2 方法论,产出候选权重 + 候选阈值
- 灰度发布:配置中心切换 → Sentry 监控 1 周 → 全量
- 出 v2.0 报告:替换本 v1.0 草稿,链接到 Sentry 灰度对比图

---

*本报告为 M3 接力版草稿,所有理论推导需 M4 末起真实数据回测验证。*
