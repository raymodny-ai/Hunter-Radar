># Hunter Radar V1.4.1 — OpenAPI Freeze v1.4.1

> **🧊 Freeze 时点:2026-06-15(M5 接力期补 freeze,W1 末 v1.4 → v1.4.1 增量)**
> 配套:本仓库后端 `app/api/*.py` 共 **33 个端点**(9 router + 2 health;v1.4 起 27 + 6 新增)
> 配套:本仓库后端 DTO **27+ 个**(v1.4 起 24 + 本轮新增 QuotaState / DataStatusResponse / PushSubscription / VAPIDPublicKey 4 个)
> 同步:本 freeze 是 FE-010(`openapi-typescript` 自动生成)与机构版复制方的前置依赖
> 解除 freeze 流程:见 §八 变更流程
> 上一 freeze 版:v1.4(2026-06-15 W1 末,27 端点)→ `docs/openapi-frozen-v1.4.{json,md}`

## 一、概述

### 1.1 范围

- **base URL**:`http://localhost:8000`(开发)/ `https://api.hunter-radar.example`(生产)
- **OpenAPI 3.0.3**(FastAPI 0.136.3 自动生成)
- **不包含**:Sentry / Redis / Postgres 内部接口
- **包含**:`/api/v1/*` 业务端点 + `/health` 运维端点 + `/` 根描述

### 1.2 自动生成命令(生产环境)

```bash
cd backend
uv run fastapi dev app/main.py   # 起服务
curl http://localhost:8000/openapi.json > docs/openapi-frozen-v1.4.1.json
# 或用 Python 一次性导出:
uv run python -c "from app.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > docs/openapi-frozen-v1.4.1.json
```

> **沙箱 fallback**(无 PG / Redis / asyncpg / sentry_sdk):
> 本仓库 `docs/openapi-frozen-v1.4.1.json` 由 `scripts/m5t8_dump_openapi.py` 静态扫描
> `app/api/*.py` 的 `@router.{get,post,put,delete}` + DTO 字段产出,
> 等同于人读版 §二 / §三 / §四的机器可读形态。生产环境务必用 `uv run` 覆盖一次。

### 1.3 与 OpenAPI freeze 硬约束(沿用 M3 / M4)

- **新增端点**:必须在 freeze 解除流程中登记,不得私下增路由
- **修改端点**(字段 / 路径 / 状态码 / 错误体):必须先 freeze 解除,改完再 freeze
- **删除端点**:必须先 freeze 解除,标 deprecated 90 天后才物理删除
- **数据缺失语义**:统一返 200 + 空数组 / 空对象,严禁 5xx 透传(Redis 沙箱降级到原函数)

## 二、服务端点总览(33 个,v1.4 起 +6)

### 2.1 按 router 分组

| # | Method | Path | 角色 | 状态 | 备注 |
|---|---|---|---|---|---|
| — | — | — | **health 路由器**(tags=[health],前缀无) | — | — |
| 1 | GET | `/health` | 健康检查 | M0 | DB+Redis 探活 |
| 2 | GET | `/` | 根描述 | M0 | 返回 name / version / docs / openapi |
| — | — | — | **symbols 路由器**(tags=[symbols],前缀=`/api/v1`) | — | — |
| 3 | GET | `/symbols/lookup` | 搜索自动补全 | M0(M1 stub) | BD-077 pg_trgm 索引待实装 |
| 4 | GET | `/symbols/{ticker}/threat` | 最新 Threat Score | M1+ | **BD-080 12h 缓存** |
| 5 | GET | `/symbols/{ticker}/options-anomaly` | 末日 Put 异常合约 | M1+ | BD-020 |
| 6 | GET | `/symbols/{ticker}/short-iceberg` | 水位图 | M1+ | BD-033,`data_warmup` 字段 |
| 7 | GET | `/symbols/{ticker}/divergence` | 量价背离 | M1+ | BD-042 |
| 8 | GET | `/symbols/{ticker}/threat-history` | 90 日 Threat Score 轨迹 | M2+ | **BD-080 12h 缓存**,BD-066 |
| 9 | GET | `/symbols/{ticker}/ultimate-alert` | 最近一条终极警报 | M3+ | BD-064 / FE-031;404 视为 null |
| — | — | — | **regime 路由器**(tags=[regime],前缀=`/api/v1`) | — | — |
| 10 | GET | `/regime` | 市场状态门控 | M2+ | BD-063,VIX/SPX → panic 红灯阈值上调 |
| — | — | — | **screener 路由器**(tags=[screener],前缀=`/api/v1`) | — | — |
| 11 | GET | `/screener` | 每日猎物榜单 | M2+ | **BD-080 12h 缓存**,BD-072 |
| — | — | — | **basket 路由器**(tags=[basket],前缀=`/api/v1`,M4 新增) | — | — |
| 12 | POST | `/baskets` | 创建自选篮 | M4 | BD-070,201 + BasketDTO |
| 13 | GET | `/baskets` | 列自选篮 | M4 | 无 X-User-Id 时返全部 |
| 14 | GET | `/baskets/{basket_id}` | 篮详情 | M4 | 404 if not found |
| 15 | PUT | `/baskets/{basket_id}` | 改名/改描述 | M4 | 局部更新 |
| 16 | DELETE | `/baskets/{basket_id}` | 删除篮(级联成员+快照) | M4 | 204 |
| 17 | POST | `/baskets/{basket_id}/members` | 增成员 | M4 | 返 `{basket_id, inserted, submitted}` |
| 18 | DELETE | `/baskets/{basket_id}/members/{ticker}` | 删成员 | M4 | 204 |
| 19 | GET | `/baskets/{basket_id}/members` | 列成员 | M4 | `ticker, added_at` |
| 20 | GET | `/baskets/{basket_id}/distribution` | 篮分布(30 日 p25/50/75/90/99) | M4 | BD-071,带落库 basket_snapshot |
| — | — | — | **alerts 路由器**(tags=[alerts],前缀=`/api/v1`,M4 新增) | — | — |
| 21 | POST | `/alert-rules` | 创建预警规则 | M4 | BD-073,201 + AlertRuleDTO |
| 22 | GET | `/alert-rules` | 列预警规则 | M4 | 同 basket list |
| 23 | GET | `/alert-rules/{rule_id}` | 规则详情 | M4 | 404 if not found |
| 24 | PUT | `/alert-rules/{rule_id}` | 改规则(名/DSL/channels/is_active) | M4 | 局部更新 |
| 25 | DELETE | `/alert-rules/{rule_id}` | 删规则(级联 alert_event) | M4 | 204 |
| 26 | POST | `/alert-rules/{rule_id}/eval` | 评估规则(给 tickers + as_of) | M4 | 返 EvalSummary(triggered/evaluated/no_data) |
| 27 | POST | `/alerts/rules` | 兼容别名(指向 #21) | M4 | M3 占位,内部转发 |
| — | — | — | **push 路由器**(tags=[push],前缀=`/api/v1`,**M5 m5t4 新增**) | — | — |
| 28 | GET | `/push/vapid-public-key` | VAPID 公钥(前端订阅前置) | M5 | 无需鉴权;沙箱返空字符串 |
| 29 | POST | `/push/subscriptions` | 注册/更新 web push 订阅 | M5 | upsert,401 沙箱占位 UUID 仍可写 |
| 30 | GET | `/push/subscriptions` | 列出当前用户所有订阅 | M5 | 不返 p256dh / auth,只返元数据 |
| 31 | DELETE | `/push/subscriptions/{sub_id}` | 软删订阅 | M5 | 204 |
| — | — | — | **data-status 路由器**(tags=[data-status],前缀=`/api/v1`,**M5 m5t6 新增**) | — | — |
| 32 | GET | `/data-status` | 全局数据状态(ready/warming/stale/error) | M5 | FE-061,沙箱无 PG 返 warming + reason |
| — | — | — | **auth 路由器**(tags=[auth],前缀=`/api/v1`,**M5 m5t8 新增**) | — | — |
| 33 | GET | `/auth/quota` | 当前用户当日查询配额 | M5 | FE-064 / BD-076;沙箱内存计数 |

### 2.2 HTTP 方法分布

| Method | Count | 比例 |
|---|---|---|
| GET | 11 | 41% |
| POST | 8 | 30% |
| PUT | 3 | 11% |
| DELETE | 4 | 15% |
| PATCH | 0 | 0% |
| **合计** | **27** | **100%** |

### 2.3 状态码分布

| 状态码 | 出现端点 | 语义 |
|---|---|---|
| 200 | GET 全部 + POST 评估 + 部分 POST 创建 | 正常返数据 |
| 201 | POST `/baskets` + POST `/alert-rules` + POST `/alerts/rules` | 创建成功 |
| 204 | 全部 DELETE | 删除成功,无 body |
| 400 | PUT/POST 校验 + Header 解析 | 请求格式错 |
| 404 | GET 详情 + DELETE / PUT 不存在资源 | 资源不存在 |
| 409 | POST `/alert-rules/{id}/eval` is_active=False | 规则非活跃,暂不评估 |
| 503 | 沙箱无 PG / 业务失败 | 服务降级 |

## 三、DTO 字典(28 个,v1.4 起 +4)

### 3.1 screener 路由器

#### ScreenerRowDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| rank | int | ✓ | 1..top |
| symbol | str | ✓ | ticker |
| name | str | ✓ | 来自 symbol_master |
| symbol_type | str | ✓ | `stock` / `etf` |
| threat_score | float | ✓ | 0-100,原始加权(非 EMA) |
| signal_lifecycle | str | ✓ | `init`/`red`/`yellow`/`gray`/`green` |
| modules_active | list[str] | ✓ | 子评分 ≥ 60 的模块名 |
| nl_summary | str \| None | ✗ | 自然语言摘要(CR-010 禁词扫描) |

#### ScreenerDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| trade_date | date | ✓ | ISO 格式 |
| rows | list[ScreenerRowDTO] | ✓ | 长度 ≤ top |
| total_scanned | int | ✓ | 当日 type 过滤下的全市场行数 |

### 3.2 basket 路由器(M4 新增)

#### BasketCreateDTO

| 字段 | 类型 | 必含 | 约束 |
|---|---|---|---|
| name | str | ✓ | 1..80 字符 |
| description | str \| None | ✗ | ≤ 500 字符 |

#### BasketDTO

| 字段 | 类型 | 必含 |
|---|---|---|
| id | int | ✓ |
| user_id | UUID | ✓ |
| name | str | ✓ |
| description | str \| None | ✓ |
| member_count | int | ✓ |
| created_at | str | ✓ (ISO 8601) |
| updated_at | str | ✓ (ISO 8601) |

#### BasketUpdateDTO

| 字段 | 类型 | 必含 | 约束 |
|---|---|---|---|
| name | str \| None | ✗ | 1..80 字符 |
| description | str \| None | ✗ | ≤ 500 字符 |

#### BasketAddMembersDTO

| 字段 | 类型 | 必含 | 约束 |
|---|---|---|---|
| tickers | list[str] | ✓ | 长度 1..200,大写化 |

#### BasketMemberDTO

| 字段 | 类型 | 必含 |
|---|---|---|
| ticker | str | ✓ |
| added_at | str | ✓ (ISO 8601) |

#### BasketDistributionByTickerDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| ticker | str | ✓ | |
| latest | float \| None | ✓ | 最新 EMA 分(可空) |
| mean | float | ✓ | 30 日均值 |
| max | float | ✓ | 30 日最大 |
| lifecycle | Literal | ✓ | 5 态枚举 |

#### BasketDistributionDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| basket_id | int | ✓ | |
| trade_date | str | ✓ | ISO 8601 |
| ticker_count | int | ✓ | 实际有数据 ticker 数 |
| day_count | int | ✓ | 实际有数据日数 |
| mean | float | ✓ | |
| p25/p50/p75/p90/p99 | float | ✓ | 分位数 |
| min_score / max_score | float | ✓ | |
| by_ticker | list[BasketDistributionByTickerDTO] | ✓ | |

### 3.3 alerts 路由器(M4 新增)

#### RuleConditionDTO

| 字段 | 类型 | 必含 | 枚举 |
|---|---|---|---|
| metric | str | ✓ | `score.ema` / `score.raw` / `lifecycle` / `lifecycle_change` / `modules` |
| op | str | ✓ | `>=` / `>` / `<=` / `<` / `==` / `!=` / `in` / `not_in` / `contains` |
| value | any | ✓ | 视 metric/op 而定:float / str / list[str] |

#### RuleDSLDTO

| 字段 | 类型 | 必含 | 约束 |
|---|---|---|---|
| when | list[RuleConditionDTO] | ✓ | 长度 1..20(AND 串接) |
| then | str | ✓ | `push` / `log` / `silent`(M4 仅 log/silent 实际生效) |

#### AlertRuleCreateDTO

| 字段 | 类型 | 必含 | 约束 |
|---|---|---|---|
| name | str | ✓ | 1..64 字符 |
| dsl | RuleDSLDTO | ✓ | 至少 1 条 when |
| channels | list[str] | ✗ | 默认 `["email"]` |

#### AlertRuleUpdateDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| name | str \| None | ✗ | 1..64 |
| dsl | RuleDSLDTO \| None | ✗ | |
| channels | list[str] \| None | ✗ | |
| is_active | bool \| None | ✗ | |

#### AlertRuleDTO

| 字段 | 类型 | 必含 |
|---|---|---|
| id | int | ✓ |
| user_id | UUID | ✓ |
| name | str | ✓ |
| dsl | RuleDSLDTO | ✓ |
| channels | list[str] | ✓ |
| is_active | bool | ✓ |
| created_at | str | ✓ |
| updated_at | str | ✓ |

#### AlertRuleEvalRequestDTO

| 字段 | 类型 | 必含 | 约束 |
|---|---|---|---|
| tickers | list[str] | ✓ | 长度 1..200 |
| as_of | date \| None | ✗ | 默认今天 |
| persist | bool | ✗ | 是否落 alert_event(默认 false = dry-run) |

#### ConditionEvalDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| metric | str | ✓ | |
| op | str | ✓ | |
| expected | any | ✓ | DSL 中的 value |
| actual | any | ✓ | 实际值(None / str / float) |
| passed | bool | ✓ | |
| rationale | str | ✓ | 调试用 |

#### AlertRuleEvalResultDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| ticker | str | ✓ | |
| trade_date | date | ✓ | |
| rule_id | int \| None | ✓ | |
| triggered | bool | ✓ | |
| ema_score / raw_score | float \| None | ✓ | |
| lifecycle | str | ✓ | 5 态 |
| condition_evals | list[ConditionEvalDTO] | ✓ | 调试用 |
| rationale | str | ✓ | |
| event_id | int \| None | ✓ | persist=true 时回填 |

#### AlertRuleEvalSummaryDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| rule_id | int | ✓ | |
| as_of | date | ✓ | |
| requested | int | ✓ | 请求 ticker 数 |
| evaluated | int | ✓ | 实际返回结果数 |
| triggered | int | ✓ | triggered=True 计数 |
| no_data | int | ✓ | threat_score_daily 缺失计数 |
| results | list[AlertRuleEvalResultDTO] | ✓ | |
| warning | str \| None | ✓ | 沙箱无 PG / 数据缺失提示 |

### 3.4 symbols 路由器

#### ThreatScoreDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| ticker | str | ✓ | |
| trade_date | date | ✓ | |
| total | float | ✓ | 原始加权(0-100) |
| ema | float | ✓ | EMA 平滑(半衰期 2 日) |
| signal_lifecycle | str | ✓ | 5 态 |
| module_options / short / divergence / insider | float | ✓ | 子评分 |
| modules_active | list[str] | ✓ | |
| nl_summary | str \| None | ✗ | |
| consecutive_days_red | int | ✓ | OQ-02 连续 ≥ red 阈值日数 |
| data_warmup | bool | ✓ | < 30 日历史返 True |

#### OptionsAnomalyDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| trade_date | date | ✓ | |
| symbol | str | ✓ | |
| contract | str | ✓ | O:AAPL240621C00200000 |
| dte | int | ✓ | |
| oi_increase_pct | float | ✓ | |
| volume_oi_ratio | float | ✓ | |
| notional | float | ✓ | |
| is_top10_notional | bool | ✓ | |
| has_known_catalyst | bool | ✓ | |
| catalyst_note | str \| None | ✗ | |

#### ShortIcebergDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| trade_date | date | ✓ | |
| symbol | str | ✓ | |
| short_ratio | float | ✓ | |
| ats_short_pct | float \| None | ✓ | |
| z_score_60d | float \| None | ✓ | BD-031 |
| data_warmup | bool | ✓ | < 60 日历史返 True |

#### DivergenceDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| trade_date | date | ✓ | |
| symbol | str | ✓ | |
| p_price | float | ✓ | 价斜率分位 |
| p_short | float | ✓ | 量斜率分位 |
| state | Literal | ✓ | `none` / `rising` / `confirmed` |

#### UltimateAlertDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| triggered_at | str | ✓ | UTC ISO 8601(去重 key) |
| trade_date | date | ✓ | |
| symbol | str | ✓ | |
| threat_score | float | ✓ | |
| raw_score | float | ✓ | |
| ema_score | float | ✓ | |
| modules_active | list[str] | ✓ | |
| regime | Literal | ✓ | `normal` / `panic` |
| consecutive_days | int | ✓ | OQ-02 守护 |

### 3.6 push 路由器(M5 m5t4 新增)

#### VAPIDPublicKeyDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| publicKey | str | ✓ | VAPID 公钥(base64url,沙箱返空字符串) |
| subject | str | ✗ | 邮箱/mailto,默认 `mailto:noreply@hunter-radar.example` |

#### PushSubscriptionDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| id | int | ✓ | |
| user_id | UUID | ✓ | |
| endpoint | str | ✓ | push service URL |
| user_agent | str \| None | ✗ | |
| is_active | bool | ✓ | 软删后 False |
| created_at | str | ✓ (ISO 8601) | |
| last_seen_at | str \| None | ✗ | |
| **不返** | p256dh / auth | — | **M3-FE:不在响应中泄霉,只用于真发** |

### 3.7 data-status 路由器(M5 m5t6 新增)

#### DataStatusResponse

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| status | Literal | ✓ | `ready` / `warming` / `stale` / `error` |
| reason | str | ✓ | 人类可读原因 |
| data_warmup | bool | ✓ | 冷启动期标志 |
| last_data_date | str \| null | ✓ | ISO date |
| is_stale | bool | ✓ | 距 last_data_date > 1 交易日 |
| db_ok | bool | ✓ | |
| redis_ok | bool | ✓ | |

### 3.8 auth 路由器(M5 m5t8 新增)

#### QuotaState

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| tier | Literal | ✓ | `free` / `pro` |
| used | int | ✓ | 当日已消耗查询数 |
| limit | int | ✓ | -1 代表无限(pro) |
| remaining | int | ✓ | -1 代表无限(pro) |
| reset_at | str | ✓ (ISO 8601) | UTC 次日 00:00:00 |
| is_sandbox | bool | ✓ | `HR_QUOTA_LIVE != 1` 走沙箱内存计数 |
| source | Literal | ✓ | `memory` / `sandbox_default` |

**硬约束**:HR_FREE_DAILY_LIMIT 环境变量可调,但本 freeze 锁定为 3。

### 3.5 regime 路由器

#### RegimeDTO

| 字段 | 类型 | 必含 | 备注 |
|---|---|---|---|
| trade_date | date | ✓ | |
| regime | Literal | ✓ | `normal` / `panic` |
| vix | float \| None | ✗ | |
| spx_vs_ma20 | float \| None | ✗ | (spx - ma20) / ma20 |
| threshold_red | int | ✓ | panic 时 80,normal 时 70 |
| banner_text | str | ✓ | 顶栏显示文案 |

## 四、tags 列表

| tag | router | 端点数 | 角色 |
|---|---|---|---|
| `health` | health | 2 | 运维探活(无前缀) |
| `symbols` | symbols | 7 | 单标的多维分析 + 终极警报 |
| `regime` | regime | 1 | 市场门控 |
| `screener` | screener | 1 | 每日猎物榜单 |
| `basket` | basket | 9 | 自选篮(BD-070/071) |
| `alerts` | alerts | 7 | 预警规则(BD-073) |

## 五、M4 新增端点专项说明(16 端点)

M4 接力期(沿用免 freeze 模式)新增的 16 个端点必须在 M5 启动期 freeze 住,
**禁止** 私下增 / 改 / 删。详见 §八 变更流程。

### 5.1 basket 新增 9 端点

- user_id 走 `X-User-Id` header(M4 占位,沙箱/未登录态用 `00000000-0000-0000-0000-000000000000`)
- 列表端点无 X-User-Id 时返全部(管理员/沙箱视角)
- 删除为硬删 + 级联(成员 + snapshot)
- 分布端点带落库 `basket_snapshot(basket_id, trade_date, score_distribution JSONB)`,ON CONFLICT DO UPDATE upsert

### 5.2 alerts 新增 7 端点

- 同样 user_id 占位机制
- DSL 5 metric × 9 op AND 串接
- 评估端点 `persist=true` 时落 `alert_event(triggered_at, payload, delivery_status)`,`delivery_status` 默认空 dict(BD-074 推送留待)
- 数据缺失语义:`triggered=False` + `rationale="无 threat_score_daily 数据(...不 mock 伪装)"` + 顶层 `warning` 字段
- 兼容别名 `/alerts/rules` 内部转发到 `/alert-rules`,M3 占位保留

## 六、错误码规范

| 状态码 | 触发条件 | response body |
|---|---|---|
| 400 | 字段校验失败 / Header 解析失败 | `{"detail": "invalid X-User-Id (must be UUID)"}` |
| 404 | 资源不存在 | `{"detail": {"message": "...", "id": 1, "ticker": "AAPL"}}` |
| 409 | 规则非活跃(eval 端点) | `{"detail": {"message": "rule is_active=False,暂不评估", "id": 1}}` |
| 422 | FastAPI 自动校验失败 | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` |
| 503 | 沙箱无 PG / Redis / 业务失败 | `{"detail": "basket.create failed(沙箱无 PG 或 schema 未初始化,设 HR_PG_OK=1 后重试)"}` |

> **500 仅在 Sentry 上报,不向客户端返 5xx 详情**(`{"detail": "internal error, see sentry event_id"}`)

## 七、鉴权方案(M4 占位 / M5 BD-075 落地)

### 7.1 M4 占位(M5 启动日生效)

- 所有 user_id 必含字段走 `X-User-Id: <UUID>` header
- 无 header:沙箱 / 未登录态用占位 UUID `00000000-0000-0000-0000-000000000000`
- 列表端点:无 header 时返全部(沙箱/管理员视角)
- 其他端点(创建/修改/删除):无 header 时也用占位 UUID(M4 简化)

### 7.2 M5 BD-075 落地后(计划)

- `Authorization: Bearer <JWT>` header
- 解析 payload 拿 `sub`(user UUID)+ `tier`(free/pro) + `exp`
- X-User-Id header 废弃(冻结)
- 配额校验(BD-076)接 free_tier_daily_quota=3,Redis 原子计数
- 退场:M4 占位 UUID 用户在迁移期数据 merge

## 八、版本与变更流程

### 8.1 版本号

- OpenAPI 版本与 `app/main.py` `version="1.4.0"` 同步
- 升级:patch 改动不改 freeze;minor 改动必须解除 freeze;major 改动走 `/api/v2` 双轨

### 8.2 解除 freeze 流程

1. 提 RFC:在仓库 `docs/openapi-rfcs/` 写 `RFC-NNN-{topic}.md`,列出改动端点 + 字段 + 影响面
2. CR + 产品双 review(签名写入 RFC 头部)
3. 解冻:本文件 `§一 Freeze 时点` 标「⏸ freeze 解除(YYYY-MM-DD)」
4. 改代码:在 `app/api/*.py` 落实
5. 重 freeze:跑 `uv run python -c "from app.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > docs/openapi-frozen-v1.4.1.json`,人读版同步更新 + 顶部冻结时点更新
6. 同步 FE-010:见 §九

### 8.2.1 本轮变更记录(v1.4 → v1.4.1, 2026-06-15 M5 接力期)

| RFC | 变动类型 | 路由 | 备注 |
|---|---|---|---|
| m5t4-BD-074 | +4 端点 | `/push/vapid-public-key` + `/push/subscriptions`(GET/POST/DELETE) | Web Push 通道(需 VAPID + pywebpush) |
| m5t6-FE-061 | +1 端点 | `/data-status` | 全局数据状态 4 态 |
| m5t8-FE-064 | +1 端点 | `/auth/quota` | 免费版每日 3 次查询配额 |
| **合计** | **+6 端点** | 9 router → 10 router(新增 tags=[push] / [data-status] / [auth]) | **27 → 33 端点** |
| m5t4 | +2 DTO | VAPIDPublicKeyDTO / PushSubscriptionDTO | |
| m5t6 | +1 DTO | DataStatusResponse | |
| m5t8 | +1 DTO | QuotaState | **24 → 28 DTO** |

### 8.3 删除端点流程

- 标记 `@router.deprecated` + 响应头 `Deprecation: true` + 90 天
- 90 天后从 router 物理删除
- freeze 解除/重 freeze 各走一次

### 8.4 FE-010 同步变更

- v1.4 → v1.4.1 增量下:重跑 `npx openapi-typescript ../docs/openapi-frozen-v1.4.1.json -o src/lib/api-types.generated.ts`
- 同步点:新增 6 端点 + 4 DTO(QuotaState / DataStatusResponse / PushSubscriptionDTO / VAPIDPublicKeyDTO)
- 上轮 v1.4 freeze 的 `openapi-frozen-v1.4.{json,md}` 保留为历史参考(不删除)

## 九、FE-010 同步说明

### 9.1 FE-010 目标

- 前端零手写 API 类型(改后端契约 → 一处生效)
- `openapi-typescript` 自动消费本 freeze

### 9.2 命令(前端 dev 环境)

```bash
cd frontend
npx openapi-typescript ../docs/openapi-frozen-v1.4.json -o src/lib/api-types.generated.ts
# 自动生成后,src/lib/api.ts 改 import 自 api-types.generated
```

### 9.3 与现前端 api.ts 的关系

- 现 `src/lib/api.ts` 24 DTO + 30+ 方法 + 沙箱降级逻辑(404/501 → null)
- freeze 后:DTO 类型由 `api-types.generated.ts` 提供,`api.ts` 保留方法 + 降级逻辑
- 重复字段(API DTO 与 generated type)出现不一致时,以 **frozen schema 为准**

## 十、已知遗留(M5 启动期)

| ID | 描述 | 状态 | 解决方 |
|---|---|---|---|
| 待办-1 | `/symbols/lookup` 仍 M0 stub,缺 pg_trgm 索引 | 🟡 | BD-077 二期 |
| 待办-2 | 推送通道未实装,`alert_event.delivery_status` 留空 | 🟡 | M5-t3 + m5t4 |
| 待办-3 | X-User-Id 占位 → JWT 替换 | 🟡 | M5-t2 |
| 待办-4 | BD-086 `reviewer_signoff.cr/product` 仍 TBD | 🟡 | 等 CR + 产品补 |
| 待办-5 | 沙箱无法实跑 `/openapi.json` → 静态扫描版 | 🟢 | 本文件 §1.2 + `scripts/m5t1_dump_openapi.py` |
| 待办-6 | OpenAPI 3.1 升级(fastapi ≥ 0.99 支持) | 🟢 | V1.5 接 |

## 十一、如何用本 freeze

### 11.1 业务方(前端 / 机构版)

- 看 §二 找端点路径 + 方法 + 状态码
- 看 §三 找字段类型 + 必含
- 看 §六 找错误码语义
- 调端点前先看 §七 鉴权(无 JWT 时带 X-User-Id 占位 UUID)

### 11.2 维护方(后端工程师)

- 改端点前必读 §八 解除 freeze 流程
- 改字段先 RFC 评审,**不要直接 commit**
- 字段加 nullable 优先于新字段(老客户端兼容)

### 11.3 联调方(QA / SRE)

- 集成 smoke:`scripts/m3_integration_smoke.py`(9 测点)
- m4t8 DSL 自测:`scripts/m4t8_test_dsl.py`(5 测点)
- 端到端:`make up` + `curl http://localhost:8000/docs` 看 swagger UI

### 11.4 解除 freeze 检查清单(可勾选)

- [ ] 提了 RFC 文档
- [ ] CR + 产品双签
- [ ] 本文件顶部标「⏸ freeze 解除」
- [ ] 代码改完
- [ ] `uv run` 跑出新的 `openapi-frozen-v1.4.json`
- [ ] 人读版 §一 / §二 / §三 / §四 / §五 / §六 同步更新
- [ ] FE-010 同步(看 §九)
- [ ] freeze 时点更新到新日期
- [ ] 解除标记去掉,重新打 🧊

---

*本文档为 Hunter Radar V1.4 M5 启动期 OpenAPI freeze。下一位 agent 修改前必读 §八。*
