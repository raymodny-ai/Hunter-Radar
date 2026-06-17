># BD-087《Threat Score 校准报告 v3.0》(M6 接力期)

> **状态**:🟡 v3.0 增量校准(候选 A vs v1.0 沙箱 stub)
> **日期**:2026-06-15(M6 接力期)
> **作者**:M6 接力 session
> **关联**:OQ-01 / OQ-02(EMA 参数)/ BD-085(数据集)/ BD-086(金标准)/ BD-089(回测框架)/ v2.5 校准报告
> **交付口径**:
> - v1.0 草稿(理论,2026-04)
> - v2.0 校准基线(M4 接力期)
> - v2.5 增量校准(M5 接力期,继承见[§五](#五、v30-vs-v25-增量))
> - **v3.0 候选 A 评估(本文,M6 接力期,沙箱 stub)**
> - v3.0-final → M7 切真实 EOD + BD-085 数据集落地后产出

---

## 一、概述

v3.0 沿用 v2.5 校准口径,聚焦**候选 A 权重**与**v1.0 默认权重**的对比评估:

- **v1.0 默认权重**(2026-04 锁定,M2 实装):
  - stock:`{options: 30, short: 35, divergence: 20, insider: 15}`
  - etf:`{options: 35, short: 45, divergence: 20}`
- **候选 A 权重**(v2.5 提出,M6 评估):
  - stock:`{options: 25, short: 40, divergence: 20, insider: 15}`
  - etf:`{options: 30, short: 50, divergence: 20}`
- **核心假设**:做空水位(FINRA RegSHO + ATS)比末日 Put 更稳定 → 削弱 options +5 / 加强 short +5

**沙箱状态**:
- ❌ 无 PG(`asyncpg` 沙箱不可装)
- ❌ 无真实 EOD 数据(BD-085 数据集尚未落地)
- ❌ 无 `httpx` SEC 代理(BD-051 EDGAR full-text search 走 fixture)
- ✅ 候选 A vs v1.0 权重定义已就位(`scripts/m6t9_run_backtest_v3.py`)
- ✅ A/B 对比 CLI 可用(`run` / `compare` / `report` 三个子命令)
- ⚠️ 命中/误报全 0,无证据证伪或证实任何权重调整

---

## 二、当前权重基线(沿用 v2.5)

| 标的类型 | options | short | divergence | insider | 备注 |
|---|---|---|---|---|---|
| **stock(v1.0)** | 30 | 35 | 20 | 15 | OQ-01 锁定,沙箱无证据改动 |
| **stock(候选 A)** | 25 | 40 | 20 | 15 | v3.0 评估目标 |
| **etf(v1.0)** | 35 | 45 | 20 | 0(关闭) | ETF 无 Form 4 insider 数据 |
| **etf(候选 A)** | 30 | 50 | 20 | 0 | 同 stock 逻辑 |

**继承自 v2.5 的硬约束**:
- OQ-02 EMA 平滑半衰期 = 2 个交易日(M3 实测稳定)
- OQ-01 红灯阈值 = 70,恐慌模式下 80(VIX>30 或 SPX<MA20)
- 连续触发天数 = 2(avoid 噪声)
- insider 模块 ETF 关闭(`insider_sell_pressure` 仅 stock 适用)

---

## 三、候选 A vs v1.0 对比(沙箱 stub)

### 3.1 模拟权重差异表

| 维度 | v1.0 默认 | 候选 A | 差异 | 预期影响 |
|---|---|---|---|---|
| options 权重(stock) | 30 | 25 | -5 | 末日 Put 信号弱化 |
| short 权重(stock) | 35 | 40 | +5 | 做空水位信号强化 |
| divergence 权重(stock) | 20 | 20 | 0 | 不变 |
| insider 权重(stock) | 15 | 15 | 0 | 不变 |
| **stock 加权综合** | 100 | 100 | 0 | 总和仍为 100 |
| options 权重(etf) | 35 | 30 | -5 | 同 stock |
| short 权重(etf) | 45 | 50 | +5 | 同 stock |
| **etf 加权综合** | 100 | 100 | 0 | 总和仍为 100 |

### 3.2 沙箱回测指标(n=0 events)

| 指标 | v1.0 | 候选 A | Δ |
|---|---|---|---|
| n_event_days | 0 | 0 | 0 |
| n_hit_event_days | 0 | 0 | 0 |
| **hit_rate** | 0.0 | 0.0 | 0.0 |
| **false_positive_rate** | 0.0 | 0.0 | 0.0 |
| precision | 0.0 | 0.0 | 0.0 |
| recall | 0.0 | 0.0 | 0.0 |
| F1 | 0.0 | 0.0 | 0.0 |

**沙箱 caveat**:n=0 时所有指标无意义,实际差异需 BD-085 真实数据集(≥30 个金标准事件,M4 已锁最小阈值)跑出。

### 3.3 候选 A 推荐决策

**当前状态**:🟡 **待真实 EOD 验证**

**推荐(无证据)**:
- 不调整 v1.0 默认权重(沿用至 BD-085 落地)
- M7 末切真实 EOD + 跑 `compare` 子命令,产出 v3.0-final
- 若 candidate A 的 hit_rate + recall 显著优于 v1.0(p < 0.05,Mann-Whitney U 检验)→ 切换默认权重
- 若无显著差异 → 沿用 v1.0,候选 A 写入 v4.0 评估清单

---

## 四、阈值集中化清单(M6 接力期增量)

沿用 v2.5 §三阈值清单 + M6 新增:

| 阈值 | 值 | 出处 | 状态 |
|---|---|---|---|
| OQ-01 红灯阈值 | 70(panic 80) | `AnomalyThresholds` | ✅ 锁定 |
| OQ-02 EMA 半衰期 | 2 交易日 | `RegimeConfig` | ✅ 锁定 |
| OQ-11 连续触发天数 | 2 | `AnomalyThresholds` | ✅ 锁定 |
| OQ-16 历史回溯 | 120 交易日 | `ThreatScore` | ✅ 锁定 |
| **m6t4 Pro 月付价格** | $19 USD | `PLAN_PRICE_USD` | ✅ 锁定 |
| **m6t4 Pro 年付价格** | $188 USD | `PLAN_PRICE_USD` | ✅ 锁定 |
| **m6t8 8-K Item 8.01 关键词** | 8 个 share-repurchase | `CATEGORY_KEYWORDS` | ✅ 锁定 |
| **m6t9 候选 A 权重** | `{25,40,20,15}` | `m6t9_run_backtest_v3.py` | 🟡 评估中 |
| m5t8 免费版配额 | 3 次/日 | `free_tier_daily_quota` | ✅ 锁定 |

---

## 五、v3.0 vs v2.5 增量

1. **沿用 v2.5 候选 A 权重定义**(stock `{options:25, short:40, divergence:20, insider:15}`)
2. **新增 runner CLI**:`scripts/m6t9_run_backtest_v3.py` 三个子命令(run / compare / report)
3. **沙箱 fixture 跑通**:命中/误报全 0(n=0 events)
4. **v3.0 报告口径明确**:推荐"沿用 v1.0 至 BD-085 真实数据落地"
5. **M7 末切真实 EOD 计划**:挂 `BD-087-calibration-run-m6t9.json` 输出

---

## 六、沙箱限制与 M7 计划

| 项 | 沙箱状态 | M7 真实环境 |
|---|---|---|
| `asyncpg` | ❌ 无 | ✅ PG 16 |
| `httpx` EDGAR | ❌ 无 | ✅ SEC 代理 |
| `backtest_dataset` 表 | ❌ 无 fixture | ✅ BD-085 数据集 |
| `backtest_event_goldset` | ✅ 31 个事件(M4 fixture) | ✅ 同上 |
| `compare` 子命令 | ✅ 沙箱返 fixture | ✅ 真实对比 |
| `report` 子命令 | ✅ 读 JSON 输出 | ✅ 同 |

**M7 接力期任务清单(BD-087 收尾)**:
1. 落地 BD-085 真实数据集(ETL: FINRA RegSHO + Yahoo Finance EOD + SEC Form 4)
2. 跑 `m6t9_run_backtest_v3.py compare --weights-a v1.0 --weights-b candidate_a`
3. Mann-Whitney U 检验 hit_rate / recall / precision 差异
4. 若候选 A 显著优 → 切换默认权重 + 更新 `settings.threat_weights_default`
5. 出 v3.0-final 报告,提交 OQ-01 复核

---

## 七、风险与遗留

| ID | 风险 | 缓解 |
|---|---|---|
| **R-27**(沿用) | BD-087 v2.5 仅理论 + 沙箱空跑,v3.0 仍无真实证据 | M7 末切 BD-085 真实数据 |
| **R-28**(新) | 候选 A 权重切换若影响前端 Threat Score 显示,需联动 openapi-freeze | v3.0-final 前冻结 openapi v1.5 |
| **R-29**(新) | 校准期间候选 A 与 v1.0 共存,前端 /api/v1/backtest/compare 需双跑 | runner compare 命令支持 |
| **R-30**(新) | OQ-01 锁定规则:权重变更需 OQ-01 复核 + 灰度发布 | m6t7 灰度发布 flag `weights_v3` 控流量 |

---

## 八、本日记忆(本日关键决策)

1. **v3.0 候选 A vs v1.0 沙箱 stub 完成**(runner CLI + 权重定义)
2. **沿用 v1.0 默认权重**(沙箱无证据改动,OQ-01 锁定)
3. **M7 末切真实 EOD**:`compare` 子命令 + Mann-Whitney U 检验
4. **R-27/28/29/30 风险登记**:校准期间候选 A 与 v1.0 共存,需灰度
5. **OpenAPI v1.5 freeze 待定**:候选 A 若切换默认权重需冻结

---

> **下一步**:M6-t10 文档接力(m6t10 文档 M6-handoff + daily-standup 更新)