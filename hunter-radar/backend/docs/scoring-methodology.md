# Hunter-Radar 评分方法论 (Scoring Methodology)

> 版本: 2026-08-02 · 方案 2.4 (CA-09) 文档化交付
> 目的: 明确 4 大威胁模块的归一化方式, 保证量纲一致 (均映射到 **0-100**), 供审计与调参。

---

## 总评分公式

```
total_raw = Σ(module_score_k × weight_k)  /  Σ(weight_k)      # active 模块加权
ema       = EMA(total_raw, halflife=config.ema_halflife_days)  # 默认半衰期 2 交易日
total     = min(100, ema)                                      # Min(Score,100) 硬截断
data_quality / confidence   # 见威胁分质量标记
```

- **权重重分配 (2.2 CA-14)**: 模块分 ≥ `config.signal_high_thresholds` 判 HIGH → 权重提升至 `_HIGH_BOOST=0.40` (多个 HIGH 均分), 其余 Normal 模块按原比例压缩。
- **单模块保护 (2.1 CA-11)**: 有效模块 < `MIN_ACTIVE_MODULES=2` → 不出分 (`confidence=insufficient_data`)。
- **信号灯 (decide_lifecycle)**: `raw >= panic(80)` 尖峰覆盖→red; `ema >= red(70)`→red; `[50,70)`→yellow; `[30,50)`→gray; `<30`→green。

---

## 各模块归一化方式

### 1. 期权异常 (options) — `_options_module_score` (load_threat_score.py)

末日 Put 异常命中数 → 0-100

| 命中数 (hit_count, 末日 DTE≤3 Put 异常) | 分数 |
|---|---|
| 0 (无异常) | 30.0 (中性偏低) |
| 1 ~ top_n-1 | `30 + (hit/top_n)×70` 线性 |
| ≥ top_n (默认 10) | 100.0 (满档) |

### 2. 做空压力 (short) — `z_to_anomaly_score` (short_metrics.py)

short_ratio 的 Z-Score (60d 窗口) → 0-100

```
z=None (冷启动) → 50.0 (中性)
score = clip(50 + (z/3.0)×50, 0, 100)
# z=0→50, z=+2→83, z=+3→100, z=-2→17
```

### 3. 量价背离 (divergence) — `divergence_to_score` (divergence.py) + 流动性门禁

detect_divergence 结果 + 成交量百分位 → 0-100

| 条件 | 分数 |
|---|---|
| is_divergent (量价背离) | 90.0 |
| p_volume > 0.7 | 60.0 |
| p_volume > 0.5 | 40.0 |
| 否则 (正常) | 20.0 |

- **流动性门禁 (2.3 CA-06)**: 20 日均量 < `MIN_AVG_VOLUME_20D=100_000` 的标的**不参与**背离检测 (低流动性天然百分位波动大易误报), 计入 `liquidity_skipped`。

### 4. 内部人交易 (insider) — `_insider_module_score` (load_threat_score.py)

由 2 个 0-100 子评分加权合成 (量纲一致, 均映射 [0,100]):

```
press (抛压)   = insider_sell_pressure_score(sells)   # 60% 权重
cover (掩护)   = cover_up_score(cover_up_alert(pairs)) # 40% 权重
module_insider = press×0.6 + cover×0.4
```

**press (insider_sell_pressure_score, insider.py)** — key insider S 事件 qty 分档:

| 关键内部人卖出总额 (20 日窗口) | 分数 |
|---|---|
| ≥ 500,000 | 90.0 |
| ≥ 100,000 | 70.0 |
| ≥ 10,000 | 50.0 |
| 有窗口事件但 < 10,000 | 30.0 |
| 无窗口事件 | 20.0 (中性) |

**cover (cover_up_score, insider.py)** — S 事件与 8-K 回购公告的掩护配对数:

| cover_up_alert 配对数 | 分数 |
|---|---|
| ≥ 3 | 95.0 |
| ≥ 1 | 80.0 |
| 0 | 10.0 |

> ETF 无限内部人模块: `module_insider = 0.0` (权重 dict 也相应不含 insider)。
> **归一化说明**: press/cover 均为分档式 0-100, 天然同量纲。方案参考用 percentile_rank(历史分布) 归一化 — 因当前数据流无历史卖出分布表, 保留分档式 (M1/M2 阶段), 未来接入历史分布可平滑替换, 不影响量纲一致性。

---

## 权重默认值

| 模块 | stock | etf |
|---|---|---|
| options | 0.30 | 0.35 |
| short | 0.35 | 0.45 |
| divergence | 0.20 | 0.20 |
| insider | 0.15 | — (0) |

- 总和恒 = 1.0 (reallocate_weights 保证)
- ML 动态权重 (V1.6.0): 历史 ≥90 天时用 `weight_optimizer.get_ml_weights` 作 base, 再叠加重分配

---

## 数据质量标记

| data_quality | 含义 |
|---|---|
| complete | 所有输入表完整 (覆盖率 ≥95%) |
| degraded | 部分数据源降级 (一表 degraded/partial) |
| stale | 无状态记录 (数据可能过期) |
| insufficient | 有效模块 < MIN_ACTIVE_MODULES (CA-11, 不出分) |

## 关键超参 (config.py)

| 参数 | 默认 | 说明 |
|---|---|---|
| threat_red_threshold | 70 | red 阈值 |
| threat_red_threshold_panic | 80 | 尖峰覆盖 red |
| ema_halflife_days | 2 | EMA 半衰期 (交易日) |
| signal_high_thresholds | options 75 / short 70 / divergence 80 / insider 65 | HIGH 判定 (2.2 CA-14) |
| MIN_ACTIVE_MODULES | 2 | 单模块保护 (2.1 CA-11) |
| MIN_AVG_VOLUME_20D | 100_000 | 背离流动性门禁 (2.3 CA-06) |
