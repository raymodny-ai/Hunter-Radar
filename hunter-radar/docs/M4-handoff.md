># Hunter Radar V1.4 — M4 收尾完成报告

> **✅ 状态:M4 主体 9 个 todo 全部 COMPLETE**(2026-06-15,W1 末)
> 前置:[M3-handoff.md](M3-handoff.md)
> 后续:M5 集成合规 — 灰度发布 + FE-060~070 预警规则编辑器 + WCAG / 性能 / 合规审计

## 一、M4 范围与交付

### 1.1 完成度

| 任务 | 状态 | 关键产出 |
|---|---|---|
| m4t1 BD-085 数据集构建器补全 | ✅ COMPLETE | `etl/backtest_dataset.py` main 入口 + argparse + 沙箱 skip + `scripts/m4_build_dataset.py` CLI |
| m4t2 BD-086 金标准事件 JSONL | ✅ COMPLETE | `data/backtest_event_goldset.sample.jsonl` 31 个真实事件(2020-2024 × 4 regime) |
| m4t3 BD-089 回测 CLI 演示 | ✅ COMPLETE | `scripts/m4_run_backtest.py` run/compare A/B 权重对比 + CSV 输出 + 沙箱 skip |
| m4t4 BD-087 校准报告 v2.0 | ✅ COMPLETE | `docs/BD-087-calibration-report-v2.0.md`(368 行,替换 v1.0 草稿) |
| m4t5 BD-070+BD-071 篮子 API | ✅ COMPLETE | 9 端点 CRUD + 成员增删 + 分布计算(带落库 basket_snapshot) |
| m4t6 BD-080 Redis 12h TTL 缓存 | ✅ COMPLETE | `cache_or_set_json` 手动包装 + 3 端点接入(threat + screener + threat-history) |
| m4t7 FE-040 篮子 UI | ✅ COMPLETE | `frontend/src/routes/basket.tsx` 整文件重写(388 行,list/create/detail 三态) |
| m4t8 BD-073 预警规则 DSL + 端点 | ✅ COMPLETE | 7 端点 + DSL 评估器 + 5 测点沙箱自测通过 |
| m4t9 文档 handoff + standup | ✅ COMPLETE | 本文档 + `daily-standup.md` W1(M4 接力日)末段 |

### 1.2 交付清单

**新建文件(10 个):**

| 路径 | 行数 | 角色 |
|---|---|---|
| `scripts/m4_build_dataset.py` | 76 | 数据集构建 CLI wrapper(沙箱 skip) |
| `scripts/m4_run_backtest.py` | 131 | 回测 CLI wrapper(run/compare) |
| `data/backtest_event_goldset.sample.jsonl` | 31 | 金标准事件集(8 short_squeeze + 12 earnings_crash + 11 institutional_slaughter) |
| `docs/BD-087-calibration-report-v2.0.md` | 368 | 校准报告 v2.0(替换 v1.0 草稿) |
| `backend/app/services/basket.py` | 419 | 篮子业务逻辑(CRUD + 分布 + 落库 basket_snapshot) |
| `backend/app/api/basket.py` | 280 | 篮子路由(9 端点) |
| `backend/app/services/alert_rule.py` | 516 | 预警规则业务 + DSL 评估器 + 纯函数 |
| `backend/scripts/m4t8_test_dsl.py` | 126 | m4t8 DSL 评估器沙箱自测(5 测点) |
| `frontend/src/routes/basket.tsx` | 388 | 篮子 UI 整文件重写(list/create/detail 三态) |
| `docs/M4-handoff.md` | (本文件) | M4 完成报告 |

**修改文件(8 个):**

| 路径 | 变更 | 角色 |
|---|---|---|
| `backend/etl/backtest_dataset.py` | +30 / -8 | main 入口加 argparse + 沙箱 skip + os import |
| `docs/BD-087-calibration-report-v1.0.md` | +5 / -1 | 顶部加「已被 v2.0 取代」声明 |
| `backend/app/core/redis_client.py` | +29 | 加 `cache_or_set_json` 手动包装(避装饰器与 Depends 冲突) |
| `backend/app/api/screener.py` | +43 / -22 | 重构 _compute_screener + cache 包装 |
| `backend/app/api/symbols.py` | +52 / -16 | 加 import + 改 get_threat_score / get_threat_history 接 cache |
| `backend/app/main.py` | +2 | 注册 basket router |
| `frontend/src/lib/api.ts` | +82 / -3 | 加 9 个 basket 方法 + 3 个 DTO |
| `backend/app/api/alerts.py` | +402 / -17 | 整文件重写(28 → 419 行),6 主端点 + 1 兼容别名 |

## 二、M4 关键设计

### 2.1 校准链:数据集 + 金标准 + 回测 + 报告(BD-085 → BD-089 → BD-087)

- **数据集**:`etl/backtest_dataset.py` 走 yfinance 取近 N 年 EOD;CLI 支持 `--end/--years/--tickers/--sandbox-skip`
- **金标准**:`data/backtest_event_goldset.sample.jsonl` 31 事件,跨 2020-2024 × 4 regime
  - 8 short_squeeze(GME/AMC/BBBY/TSLA/KOSS/BB/WISH/NOK)
  - 12 earnings_crash(META/NFLX/SNAP/META/COIN/HOOD/CVNA/PTON/W/RIVN/LYFT/NVDA)
  - 11 institutional_slaughter(SIVB/FRC/CS/AAL/CCL/BA/CCL/HBI/BBBY/LCID/GME)
  - severity 分布:extreme 11 / high 8 / medium 9 / low 3
  - `reviewer_signoff: {cr: TBD, product: TBD}` 待实际 review 补
- **回测**:`app/services/backtest.py run/compare` + `scripts/m4_run_backtest.py` wrapper,沙箱自动 skip
- **校准报告 v2.0**:368 行,15 章节(摘要/权重基线/阈值集中化/OQ-02 守护/金标准事件集/数据集/回测 CLI/沙箱结果/推荐权重/红灯阈值理论推导/校准方法论/M4→M5 时间表/代码证据/硬约束/接力)

### 2.2 BD-087 v2.0 推荐策略:**沿用 v1.0 静态权重,不在 M4 接力期调整**

- 沙箱无真实 EOD 数据 → 无 run/compare 跑出 hit_rate / fa_rate / score_lift 实证
- 强行调整权重会违反「OQ-01 校准前不得修改」锁定
- 保留 v1.0 校准前默认(stock 30/35/20/15,etf 35/45/20)作为 M4 末基线
- M5 末起跑真实回测 → v2.5 校准权重接 production

### 2.3 Redis 12h TTL 缓存(BD-080)

- 模式:`cache_or_set_json(key, ttl, compute_fn)` 手动包装(避免装饰器与 FastAPI Depends 冲突)
- 接入 3 端点:`GET /screener` + `GET /symbols/{ticker}/threat` + `GET /symbols/{ticker}/threat-history`
- cache_key:`cache:get_screener:{top}:{type}:{date}` / `cache:get_threat_score:{ticker}` / `cache:get_threat_history:{ticker}:{days}`
- TTL:`settings.cache_ttl_report_seconds = 43200` (12h)
- 沙箱降级:Redis 不可达 → `except Exception: pass` 走原函数
- 不缓存 POST/PUT/DELETE(写操作必穿透)

### 2.4 自选篮子三件套(BD-070 / BD-071 / FE-040)

- **后端 service**:`backend/app/services/basket.py` 419 行
  - CRUD:create / list / get / update / delete
  - 成员:list / add / remove
  - 分布:`compute_basket_distribution(basket_id, days=30)` 取近 30 日 threat_score_daily,算 p25/p50/p75/p90/p99 + by_ticker 详情
  - 落库:`basket_snapshot` (basket_id + trade_date + score_distribution JSONB) 用 `pg_insert ON CONFLICT DO UPDATE` upsert
- **后端 API**:`backend/app/api/basket.py` 280 行,9 端点
  - `POST/GET/PUT/DELETE /baskets` + `POST/GET /baskets/{id}/members` + `DELETE /baskets/{id}/members/{ticker}` + `GET /baskets/{id}/distribution`
- **前端 UI**:`frontend/src/routes/basket.tsx` 388 行,3 态 View
  - list:篮子卡片网格,点击进 detail
  - create:name(必填 80) + description(可选 500)
  - detail:成员增删(input 解析 `,` 空格分隔) + 分布可视化(Stat 网格 + by_ticker 表)
  - 风格:bg-slate-900 暗色 + bg-hunter-red/-yellow/-green 文字
  - 兜底:「数据来源:FINRA + SEC EDGAR + Yahoo Finance。统计异常现象,仅供参考,不构成投资建议」

### 2.5 预警规则 DSL(BD-073)

- **DSL 数据格式**(落 `alert_rule.dsl` JSONB):
  ```json
  {
    "when": [
      {"metric": "score.ema", "op": ">=", "value": 75},
      {"metric": "lifecycle", "op": "in", "value": ["red","yellow"]},
      {"metric": "modules",   "op": "contains", "value": "short"},
      {"metric": "lifecycle_change", "op": "in", "value": ["gray->red","init->red"]}
    ],
    "then": "push"
  }
  ```
- **评估器**:`evaluate_dsl_for_snapshot` AND 串接,全部 `condition.passed=True` → `triggered=True`
- **支持 metric**(5 个):`score.ema` / `score.raw` / `lifecycle` / `lifecycle_change` / `modules`
- **支持 op**(9 个):`>=` / `>` / `<=` / `<` / `==` / `!=` / `in` / `not_in` / `contains`
- **then action**:`push` / `log` / `silent`(M4 阶段仅 `log`/`silent` 实际生效,`push` 仅落 `alert_event` 表)
- **端点**:6 主 + 1 兼容别名
  - `POST /alert-rules`(主) + `POST /alerts/rules`(兼容别名,M3 占位)
  - `GET /alert-rules` / `GET /alert-rules/{id}`
  - `PUT /alert-rules/{id}` / `DELETE /alert-rules/{id}`
  - `POST /alert-rules/{id}/eval` — 给 ticker 列表 + as_of,返 `EvalSummary(evaluated/triggered/no_data/results)`
- **推送通道**留待 BD-074 二期,本期仅落 `alert_event` 表
- **数据缺失**:API 返 200 + `triggered=False` + `rationale="无 threat_score_daily 数据(...不 mock 伪装)"` + 顶层 `warning` 字段

### 2.6 user_id 临时方案(M4 接力期)

- 走 `X-User-Id` HTTP header(沙箱占位 UUID `00000000-...`)
- 列表端点:无 X-User-Id 时返全部(管理员/沙箱视角)
- BD-075 JWT 落地后替换为 token 解析

## 三、M4 关键决策与硬约束

### 3.1 OQ 决策锁定(未触碰)

- OQ-01 权重回测校准:M4 沿用 v1.0 静态权重(校准前默认),M5 末起跑真实回测
- OQ-02 EMA 半衰期 2 日 + 连续 2 交易日:8 个单元测试守护
- OQ-16 ETF 代理指标 PoC:已就位,真实申赎数据二期接
- OQ-09 / OQ-11:项目忽略

### 3.2 CR 红线(未触碰)

- CR-010 禁词清单:`scripts/compliance_check.py` 锁定
- 「仅供参考 / 不构成投资建议」必含兜底(篮 UI 强制)
- API 契约与数据真实性规范:数据缺失返 200 + 空数组,严禁 mock 伪装(BD-073 评估端点 / basket 分布端点均落实)

### 3.3 新增硬约束(M4 接力期)

- **OpenAPI 变更先 freeze 再同步 FE-010**:M4 新增 16 个端点(9 basket + 7 alert-rule),免 freeze(无现有契约),M5 初必须 freeze 一版后再同步 FE-010
- **数据缺失返 200 + 空数组,严禁 mock 伪装**:
  - BD-073 评估端点:无 `threat_score_daily` → `triggered=False` + `rationale` 显式说明
  - basket 分布端点:无数据 → 200 + `ticker_count=0` + `mean=0` + `by_ticker=[]`
  - screener / threat / threat-history:Redis 不可达降级到原函数,不走 mock
- **Redis 缓存沙箱降级**:Redis 挂了走原函数,严禁异常透传 5xx
- **X-User-Id 占位**:M4 接力期所有 user_id 必走 header,BD-075 JWT 落地后替换
- **TS linter 报错**(M0/M3 已知):沙箱无 `pnpm install`,TS 报「JSX.IntrinsicElements 不存在」,**不修复**(本地执行 `pnpm install` 后消失)

## 四、M4 未完成 / 已知遗留

### 4.1 沙箱限制

- `pnpm install` 未执行 → basket.tsx 388 行 TS 报错(本地 `pnpm install` 即可消)
- 无 PG / Redis / 真实 EOD 数据 → 集成测试仅 smoke 骨架
- BD-087 v2.0 校准仅理论,M4 末起跑真实回测
- BD-073 评估器沙箱下走 SQL 失败 → API 返 503;纯函数部分(DSL 解析 + 评估逻辑 + 校验)已用 `scripts/m4t8_test_dsl.py` 5 测点验证通过
- `data/backtest_event_goldset.sample.jsonl` 中 `reviewer_signoff.cr/product` 仍是 `TBD`,待 CR + 产品双人 review 后补

### 4.2 二期待启动

- **BD-074 推送通道**:email + webpush(走 VAPID),alert_event.delivery_status 由二期写入
- **BD-075 JWT 落地**:替换 X-User-Id header 占位
- **8-K Item 8.01 回购公告解析器**(BD-051):DAG 调 `load_buyback([])` 空跑不阻塞,二期接 EDGAR full-text search
- **BD-086 reviewer_signoff 双签补全**:CR + 产品双签,需走流程
- **BD-087 真实回测**:M5 末起跑 v1.0 默认权重 vs 候选权重 A/B,产出 v2.5 校准权重

### 4.3 测试数变化

- M3 末:194 个 pytest
- M4 末:**仍 194 个**(M4 未新增 pytest,均依赖现有 threat_score / basket / backtest 单测)
- M4 增量:5 测点 DSL 沙箱自测脚本(`scripts/m4t8_test_dsl.py`),独立可跑
- 前端无 Vitest 测试(M0 已知,二期接 vitest 框架)

## 五、立即可跑(本地)

```bash
# 1. 起基础设施 + 后端
cd "d:\Financial Project\Hunter Radar\hunter-radar"
make up
cd backend
uv sync --extra dev
uv run python -m etl.symbol_seed
uv run fastapi dev app/main.py    # http://localhost:8000/docs

# 2. 跑后端测试
uv run pytest -q                  # 期望 194 passed

# 3. 跑 EOD 流水线
uv run python -m etl.pipeline 2024-02-01

# 4. 跑校准数据构建(BD-085)
uv run python scripts/m4_build_dataset.py --end 2024-12-31 --years 2 --tickers AAPL,TSLA

# 5. 跑回测(BD-089) — run 单组权重 / compare A/B
uv run python scripts/m4_run_backtest.py run --tickers AAPL,TSLA,GME,AMC,META
uv run python scripts/m4_run_backtest.py compare --a-weights '{"options":0.30,"short":0.35,"divergence":0.20,"insider":0.15}' --b-weights '{"options":0.25,"short":0.40,"divergence":0.20,"insider":0.15}'

# 6. 跑 m4t8 DSL 自测(沙箱可跑)
py scripts/m4t8_test_dsl.py        # 期望 5/5 PASSED

# 7. 跑集成 smoke test
HR_BASE_URL=http://localhost:8000 uv run python scripts/m3_integration_smoke.py

# 8. 前端
cd ../frontend
pnpm install                       # 消 TS linter 报错
pnpm dev                           # http://localhost:5173/basket
# 看到:list(篮子卡片网格) → create → detail(成员增删 + 分布可视化)
```

## 六、M5 启动接力

### 6.1 接力入口

- **后端 main**:`backend/app/main.py` 已注册 basket / alert-rule router
- **OpenAPI 文档**:`http://localhost:8000/docs`(沙箱无 PG 启不起来,需本地 `make up`)
- **前端自定义分析入口**:`http://localhost:5173/basket`(m4t7) + 预警规则 UI(m5 启)
- **校准报告**:`docs/BD-087-calibration-report-v2.0.md` v2.0 就位

### 6.2 M5 开工顺序

1. **环境验证**:`make up; cd backend; uv sync --extra dev; uv run pytest -q` → 194 passed
2. **集成 smoke**:`HR_BASE_URL=http://localhost:8000 uv run python scripts/m3_integration_smoke.py` → 9/9
3. **OpenAPI freeze**:M5 初必须 freeze 一版(M4 新增 16 端点 + 既有端点),同步 FE-010 文档
4. **BD-074 推送通道**:email + webpush(走 VAPID),落 alert_event.delivery_status
5. **BD-075 JWT 落地**:替换 X-User-Id header 占位
6. **FE-060~FE-070**:前端预警规则编辑器 + 高级功能(自定义分析 + 规则 DSL 可视化)
7. **BD-087 真实回测**:M5 末起跑 v1.0 默认权重 vs 候选权重 A/B,产出 v2.5 校准权重
8. **WCAG / 性能 / 合规审计 + 上线预审**

### 6.3 给下一位 agent 的一句话

- M4 主体 9 个 todo 全 COMPLETE,代码层就位,数据层待真实 EOD(沙箱不可达,需本地或代理)
- M4 范围**不输出投资建议**(CR-010 红线);**不数据伪装**(BD-073 评估 + basket 分布均落实 200+空 严禁 mock)
- 进入 M5 时请先读 [M4-handoff.md](M4-handoff.md) §4.1 沙箱限制,合理安排 smoke / 集成测试
- M5 重点是 OpenAPI freeze + 推送通道 + JWT + 真实回测
- BD-087 v2.5 出 v2.0 时,保留 v2.0 §一/§二/§三/§五/§六章节结构

## 七、本日记忆(自动,补充)

- M4 校准链 4 步:数据集(BD-085) + 金标准(BD-086) + 回测(BD-089) + 报告(BD-087) — 4 件套完整闭环
- BD-087 v2.0 推荐沿用 v1.0 静态权重,理由:沙箱无真实 EOD → 无 run/compare 实证 → 强行调权重违反 OQ-01 锁定
- Redis 缓存采用手动 `cache_or_set_json` 包装(非装饰器),理由:装饰器与 FastAPI Depends 冲突,compute_fn 接受闭包参数
- Redis 沙箱降级:Redis 挂了走原函数,`except Exception: pass` 双侧包(读 + 写)
- basket.tsx 三态 View:list(卡片网格) / create(表单) / detail(成员增删 + 分布可视化),用 useState 切换
- BD-073 DSL 5 metric × 9 op,AND 串接,数据缺失返 200 + triggered=False + rationale 显式说明(严禁 mock)
- BD-073 推送通道留待 BD-074,本期仅落 alert_event 表(delivery_status 留空 {})
- M4 接力期 16 个新端点(9 basket + 7 alert-rule),OpenAPI 免 freeze,M5 初必须 freeze 一版同步 FE-010
- DSL 沙箱自测 5 测点全部通过(t1 强触发 / t2 弱不触发 / t3 缺数据不触发 / t4 lifecycle_change / t5 校验拒绝 4 种坏值)
- m4t3 argparse subparser 顺序坑:`--sandbox-skip` 必须放 `add_subparsers` 之前,否则 sub 之后不识别
- X-User-Id header(M4 占位 UUID)→ BD-075 JWT 替换;basket list 无 X-User-Id 时返全部(沙箱/管理员视角)
- 「仅供参考 / 不构成投资建议」兜底在 basket.tsx 底部强制保留(bg-slate-900 暗色 + hunter-red 强调)

---

*本文档为 M4 接力版完成报告。下一位 agent 从 §6 M5 启动接力开工。*
