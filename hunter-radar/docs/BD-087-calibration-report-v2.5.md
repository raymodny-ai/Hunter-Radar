># BD-087《Threat Score 校准报告 v2.5》(M5 接力期)

> **状态**:🟡 v2.5 增量(M5 接力期补 v1.0 → v2.0 → v2.5 双锁;v3.0 待 M6 切真实 EOD)
> **日期**:2026-06-15(M5 接力期,W1 末)
> **作者**:M5 接力 session
> **关联**:OQ-01(权重必须回测校准)/ BD-085(数据集)/ BD-086(金标准)/ BD-089(回测框架)/ BD-070(篮子分布)/ **BD-074(推送通道,M5 新增)/ BD-075(JWT,M5 新增)/ BD-076(配额,M5 新增)**
> **交付口径**:
> - v1.0 草稿(理论,2026-04)
> - v2.0 校准基线(M4 接力期,代码 + 数据集就位 + 沙箱空跑)
> - **v2.5 增量校准(本文,M5 接力期,M5 末出文 v2.5-final)**
> - v3.0 最终推荐(M6 切真实 EOD 后)

---

## 一、v2.5 vs v2.0 增量(M5 接力期)

1. **回测 runner 落地**:`scripts/m5t9_run_backtest.py` 沙箱可跑,产出 `docs/BD-087-calibration-run-m5t9.json` 静态报告
2. **金标准事件集未变**:`data/backtest_event_goldset.sample.jsonl` 31 个事件(8 short_squeeze + 12 earnings_crash + 11 institutional_slaughter)
3. **v1.0 默认权重 vs 候选 A 沙箱空跑**:
   - v1.0: stock {options:30, short:35, divergence:20, insider:15}
   - 候选 A: stock {options:25, short:40, divergence:20, insider:15}(加大 short 比重)
   - 沙箱无 PG/EOD → 命中/误报全 0,无证据推荐任何权重调整
4. **阈值集中化清单扩展**:新增 quota / push / sentry 等 M5 落地产物
5. **校准时间表更新**:M5 末(本文 v2.5)→ M6 切真实 EOD(跑 v3.0)
6. **OpenAPI freeze 同步**:v1.4 → v1.4.1(6 端点 + 4 DTO 新增,见 `docs/openapi-frozen-v1.4.1.md`)

---

## 二、当前权重基线(校准前默认,M2 实装 + v1.0 锁定 → v2.5 继续沿用)

| 标的类型 | options | short | divergence | insider | 备注 |
|---|---|---|---|---|---|
| **stock** | 30 | 35 | 20 | 15 | v1.0 默认,沙箱无证据改动 → v2.5 沿用 |
| **etf** | 35 | 45 | 20 | 0(关闭) | ETF 无 Form 4 insider 数据,insider=0 |

**候选 A(stock 备选,v3.0 评估候选)**:
| 标的类型 | options | short | divergence | insider | 假设 |
|---|---|---|---|---|---|
| **stock** | 25 | 40 | 20 | 15 | 假设做空水位比末日 Put 更稳定,削弱 options +5 / 加强 short +5 |

**红灯阈值(由 regime 决定,OQ-02 锁定)**:
- normal: 70(EMA 后)
- panic: 80(VIX>30 或 SPX<MA20 时)

**EMA 半衰期**:默认 2 交易日(OQ-02 锁定;`settings.ema_halflife_days`)

**连续窗口(终极警报触发条件,OQ-02 锁定)**:连续 ≥2 个交易日的 EMA 后子评分 ≥ 60

**M5 新增业务约束**:
- 免费版每日 3 次查询配额(BD-076,`HR_FREE_DAILY_LIMIT=3` 锁定) — 不影响权重
- 推送通道(BD-074 邮件 + Web Push)— 不影响权重
- JWT 鉴权(BD-075)— 不影响权重

---

## 三、阈值集中化与可回测性(v2.5 扩展)

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
| 缓存 TTL 12h(M4) | `settings.cache_ttl_report_seconds = 43200` | 改 1 行 + 重启 |
| 篮子分布缓存(M4) | `app.services.basket.compute_basket_distribution` 内部 | 改 1 行 |
| **新增(M5)** 免费版日配额 | `app.services.quota.FREE_DAILY_LIMIT` / `HR_FREE_DAILY_LIMIT` | env 改 1 行 + 重启 |
| **新增(M5)** SMTP host | `HR_SMTP_HOST` / `app.services.push.SMTP_HOST` | env 改 1 行 + 重启 |
| **新增(M5)** VAPID | `HR_VAPID_PRIVATE_KEY` / `HR_VAPID_PUBLIC_KEY` | env 改 1 行 + 重启 |
| **新增(M5)** 推送 live 开关 | `HR_PUSH_LIVE` | env 改 1 行 + 重启 |
| **新增(M5)** Sentry traces 采样率 | `app.services.main.sentry_sdk.init(traces_sample_rate=0.1)` | 改 1 行 |
| **新增(M5)** reduced-motion 类过滤 | `usePrefersReducedMotion.reduceMotionClasses` | 改 1 行 |
| **新增(M5)** 沙箱 PG 开关 | `HR_PG_OK` | env 改 1 行 + 重启 |

**校准产物发布路径**(沿用 v2.0):灰度发布 + 保留旧值 7 天 + 监控误报率/命中率(回滚一行切换)。

---

## 四、OQ-02 单元测试已锁定的边界条件(M1 末 8 个用例 — 沿用未动)

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

## 五、M4 接力期金标准事件集(BD-086 — 31 事件未动,沿用 v2.0)

| # | 类型 | ticker | window | severity | 事件简述 |
|---|---|---|---|---|---|
| 1 | short_squeeze | GME | 2021-01-25 ~ 02-04 | extreme | Meme squeeze 周内 5x |
| 2 | short_squeeze | AMC | 2021-05-25 ~ 06-07 | high | 散户轧空第二波 + 转债 |
| ... | ... | ... | ... | ... | (其余 29 事件见 v2.0 §5.2 / jsonl) |

---

## 六、v2.5 沙箱回测结果(`docs/BD-087-calibration-run-m5t9.json`)

```json
{
  "run_id": "m5t9-2026-06-15",
  "is_sandbox": true,
  "weights_v10": {"options": 30, "short": 35, "divergence": 20, "insider": 15},
  "weights_candidate_A": {"options": 25, "short": 40, "divergence": 20, "insider": 15},
  "metrics_v10": {
    "n_events_total": 31,
    "n_by_type": {"short_squeeze": 8, "earnings_crash": 12, "institutional_slaughter": 11},
    "hits": 0, "false_positives": 0, "misses": 0,
    "precision": null, "recall": null, "f1": null,
    "reason": "sandbox no PG/EOD reachable,设 HR_BACKTEST_LIVE=1 + 真数据后重跑"
  },
  "metrics_candidate_A": { "...": "同 metrics_v10(空跑全 0)" },
  "diff": {
    "delta_hits": 0,
    "delta_fp": 0,
    "recommendation": "sandbox 模式下无证据推荐任何权重调整;沿用 v1.0 静态值直到生产环境 HR_BACKTEST_LIVE=1 跑出真实 F1。"
  }
}
```

**沙箱空跑结论**:
- 31 事件成功加载(分类齐:8/12/11)
- 命中/误报全 0:无 PG/EOD 可达,纯 sanity check
- 候选 A 相对 v1.0 无差异:沙箱无证据

**v2.5 校准推荐**:**沿用 v1.0 默认权重** + 锁定 OQ-02 三组参数(红灯阈值 / 连续日数 / EMA 半衰期),等 M6 切真实 EOD 后跑 v3.0 评估候选 A。

---

## 七、v3.0 校准计划(M6 切真实 EOD 后)

1. **数据灌库**(BD-085)
   - daily_price EOD 灌库 ≥ 1 年
   - short_volume FINRA 灌库 ≥ 1 年
   - form4_events SEC EDGAR 灌库 ≥ 1 年
2. **回测跑全量**:`uv run python -m app.services.backtest run --tickers <universe> --start 2024-01-01 --end 2026-06-15`
3. **A/B 对比**:v1.0 vs 候选 A 同时跑,产出 F1 / precision / recall
4. **v3.0 报告产出**:`docs/BD-087-calibration-report-v3.0.md`,含:
   - 推荐权重(若 v3.0 F1 显著高于 v1.0)
   - 阈值微调(红灯 / 连续日数 / EMA 半衰期)
   - 灰度发布路径
5. **灰度发布**:新权重 5% → 25% → 50% → 100% 四档,监控 7 天误报率

---

## 八、OQ-01 / OQ-02 / OQ-16 守护校准不重启(沿用 M4 锁定)

| 锁 | 守护对象 | 状态 |
|---|---|---|
| OQ-01 | 权重必须回测校准才能上线 | 🟡 v1.0 → v2.0 → v2.5,推荐 v3.0 待 M6 |
| OQ-02 | 红灯阈值 / 连续日数 / EMA 半衰期 8 用例锁定 | ✅ |
| OQ-16 | CR-010 禁词扫描 + 兜底文案 | ✅ |

---

## 九、§9 交付清单(M5 接力期)

- [x] `scripts/m5t9_run_backtest.py`(125 行,沙箱可跑)
- [x] `docs/BD-087-calibration-run-m5t9.json`(空跑结果)
- [x] `docs/BD-087-calibration-report-v2.5.md`(本文)
- [x] 沙箱自测 `scripts/m5t9_test_calibration.py`(10 测点)

---

## 十、关联文档

- 上版:`docs/BD-087-calibration-report-v2.0.md`(M4 接力期)
- 上上版:`docs/BD-087-calibration-report-v1.0.md`(M3 末草稿,理论)
- 回测框架:`backend/app/services/backtest.py`(BD-089)
- 金标准事件集:`data/backtest_event_goldset.sample.jsonl`
- M5-handoff:见 `docs/M5-handoff.md`(待 m5t11)
