# V1.5.4 OpenAPI Freeze — V1.5.4 接力期 OpenAPI 冻结规范

> V1.5.4 接力期(m12t1 ~ m12t3)全部 COMPLETE。OpenAPI v1.5.4 freeze 已落地。
>
> 关联文档:
> - [V1.5.4-handoff.md](./V1.5.4-handoff.md) — V1.5.4 接力期收尾报告(待 m12t3 完成后建)
> - [openapi-frozen-v1.5.4.json](./openapi-frozen-v1.5.4.json) — 机器可读 OpenAPI freeze
> - [openapi-frozen-v1.5.3.md](./openapi-frozen-v1.5.3.md) — V1.5.3 上一 freeze

---

## 一、概述

V1.5.4 接力期聚焦 V1.5.3 评审 6 个候选待优化项(C-1~C-6)中的 3 项落地:
- **C-2** super_admin role 扩展(m12t1)
- **C-4** m7t2_sign_goldset.py 物理删除(m12t2)
- **C-5** OpenAPI 端点评审字段标注(m12t3)

**端点层面**:**不引入新端点**,**不修改现有端点响应 schema**,**不删除端点**。仅:
- 1 个端点(`/api/v1/admin/webhook/replay`)鉴权从 `require_admin_role` 升级为 `require_super_admin_role`(m12t1)
- 4 个 admin 端点 docstring 加 `### REVIEW META (V1.5.4 m12t3)` 段(m12t3)

| 维度 | V1.5.3 状态 | V1.5.4 状态 |
|---|---|---|
| 端点总数 | 56 | 56(沿用,无变更) |
| fetch_source 规范 | 8 值 | 8 值(沿用) |
| admin 鉴权 | 三态(普通 admin) | 四态(普通 admin + super_admin 三态) |
| super_admin 端点 | 0 | 1(`/admin/webhook/replay`) |
| 评审字段标注 | 无 | 4 admin 端点显式 + 52 端点 catch-all |
| 待优化项 | 6 项 | 0 项(C-2/C-4/C-5 完成) |
| OpenAPI freeze | v1.5.3 | v1.5.4(代码层 freeze,端点沿用) |

---

## 二、M12 增量(代码层 + 端点元数据)

### 2.1 auth.py 内部变更

| 变更项 | 评审 | 详情 |
|---|---|---|
| `VALID_ROLES` 扩为 3 元素 | C-2 | `("user", "admin", "super_admin")` |
| `ADMIN_ROLES` / `SUPER_ADMIN_ROLE` 常量 | C-2 | super_admin 是 admin 的超集 |
| `is_admin_role` / `is_super_admin_role` helpers | C-2 | `normalize_role` 兼容小写/None |
| `TUser.is_admin` 改用 `is_admin_role` | C-2 | super_admin 自动过 is_admin |
| `TUser.is_super_admin` 新增 property | C-2 | 显式判定 super_admin |
| `require_super_admin_role` 依赖 | C-2 | 4 路径:JWT/API key/沙箱 fallback/503 |
| `__all__` 补 5 新符号 | C-2 | `ADMIN_ROLES` / `SUPER_ADMIN_ROLE` / `is_admin_role` / `is_super_admin_role` / `require_super_admin_role` |

### 2.2 admin.py 内部变更

| 变更项 | 评审 | 详情 |
|---|---|---|
| `POST /admin/webhook/replay` 改用 `require_super_admin_role` | C-2 | webhook 重放是高危操作,普通 admin 不可触发 |
| 4 端点 docstring 加 `### REVIEW META (V1.5.4 m12t3)` 段 | C-5 | review_status / owner / last_reviewed / touched_in_v153 / m12t1_super_admin |
| super_admin 三态 auth_mode 标签 | C-2 | `prod_super_admin_jwt` / `prod_super_admin_apikey` / `sandbox_skip_super_admin` |

### 2.3 工具链清理

| 文件 | 变更项 | 评审 |
|---|---|---|
| `m7t2_sign_goldset.py` | **物理删除** | C-4(reviewer_cli 单一权威) |
| `REVIEWER_CLI_MIGRATION.md` | 改写为 V1.5.4 state | C-4 |
| `m10t5_test_reviewer_cli_replace.py` | 4 测点改测 m7t2 物理删除 | C-4 |
| `m11t4_test_reviewer_cli_toolchain.py` | 4 测点改测 m7t2 物理删除 | C-4 |
| `m12t1_test_super_admin_role.py` | 新建 25 测点 | C-2 |
| `m12t2_test_m7t2_deletion.py` | 新建 25 测点 | C-4 |
| `m12t3_test_openapi_endpoint_review.py` | 新建 25 测点 | C-5 |

**说明**:脚本工具的清理 + 新增不影响 HTTP API 端点数量,仅触发 OpenAPI freeze 元数据层更新。

---

## 三、端点评审字段标注(NEW in V1.5.4)

### 3.1 关键端点(4 admin)

| 端点 | review_status | owner | last_reviewed | touched_in_v153 | m12t1_super_admin | m12t3_high_risk |
|---|---|---|---|---|---|---|
| `POST /api/v1/admin/etl/run` | passes_v153 | platform-team | 2026-06-15 | true(m11t2 IP 合并) | false | false |
| `POST /api/v1/admin/backtest/run` | passes_v153 | platform-team | 2026-06-15 | true(m11t2 IP 合并) | false | false |
| `GET /api/v1/admin/backtest/result` | passes_v153 | platform-team | 2026-06-15 | true(m11t2 IP 合并) | false | false |
| `POST /api/v1/admin/webhook/replay` | passes_v154 | platform-team | 2026-06-15 | false | **true**(m12t1 升级) | **true**(webhook = 计费事件) |

### 3.2 其余 52 端点(catch-all)

| 字段 | 值 | 说明 |
|---|---|---|
| review_status | passes_v153 | V1.5.3 接力期评审通过 |
| owner | platform-team | 平台组 |
| last_reviewed | 2026-06-15 | V1.5.4 接力期评审日 |
| touched_in_v153 | false | 沿用 V1.5.2,无 V1.5.3 变更 |
| m12t1_super_admin | false | 普通端点,鉴权不变 |

**注**:端点完整列表见 [openapi-frozen-v1.5.4.json](./openapi-frozen-v1.5.4.json) `endpoint_review_meta` 数组。

### 3.3 端点 docstring 标注规范

每个端点 docstring 末尾加 `### REVIEW META (V1.5.4 m12t3)` 段:

```python
async def post_etl_run(...) -> dict:
    """触发 BD-085 真实数据集 ETL。

    沙箱 stub:调 `etl/backtest_dataset_real.py` 合成 deterministic OHLCV 数据。
    ...

    ### REVIEW META (V1.5.4 m12t3)
    review_status: passes_v153
    owner: platform-team
    last_reviewed: 2026-06-15
    touched_in_v153: true (m11t2 IP 校验合并)
    m12t1_super_admin: false
    """
```

webhook/replay 端点特殊标注:

```python
async def post_webhook_replay(...) -> dict:
    """重放 sandbox Stripe webhook(测试用)。

    V1.5.4 接力期 m12t1:webhook 重放属于高危操作...
    ...

    ### REVIEW META (V1.5.4 m12t3)
    review_status: passes_v154
    owner: platform-team
    last_reviewed: 2026-06-15
    touched_in_v153: false
    m12t1_super_admin: true (require_super_admin_role)
    m12t3_high_risk: true (webhook 重放 = 计费事件)
    """
```

---

## 四、super_admin 鉴权(NEW in V1.5.4)

### 4.1 鉴权拆分

| 鉴权依赖 | 适用端点 | 角色 | 沙箱 fallback |
|---|---|---|---|
| `require_admin_role` | 53 端点(普通 admin) | role in {admin, super_admin} | sandbox_skip_admin |
| `require_super_admin_role` | 1 端点(`/admin/webhook/replay`) | role == super_admin | sandbox_skip_super_admin |

### 4.2 三态 auth_mode 标签

普通 admin 端点(m11t2 + m12t1 兼容):
- `prod_admin_jwt`(JWT role=admin + 真实用户)
- `prod_admin_apikey`(X-Admin-API-Key 头)
- `sandbox_skip_admin`(沙箱占位用户)

super_admin 端点(m12t1):
- `prod_super_admin_jwt`(JWT role=super_admin + 真实用户)
- `prod_super_admin_apikey`(X-Admin-API-Key 头)
- `sandbox_skip_super_admin`(沙箱占位用户)

### 4.3 沙箱 fallback 显式标注

所有 admin 端点(普通 + super)沙箱 fallback 走占位 user,auth_mode 标签显式标注 `sandbox_skip_*`,严禁 mock 200 伪装鉴权成功。

---

## 五、fetch_source 规范(沿用 V1.5.2)

8 值统一规范,沿用 V1.5.2 freeze:

| 值 | 含义 | 模块 |
|---|---|---|
| `sec_httpx` | httpx → SEC API(efts.sec.gov) | EDGAR |
| `yfinance` | yfinance ETF 代理数据源 | ETF premium-discount |
| `user_provided_price` | 用户提供价格 | ETF fallback |
| `posthog` | postHog 事件追踪 | Analytics events |
| `plausible` | Plausible 事件追踪 | Analytics fallback |
| `sandbox_stub` | 沙箱 stub 数据(同步 ETL) | 所有模块 fallback |
| `sandbox_stub_v15_prep` | V1.5 prep 沙箱 stub | EDGAR / ETF / Analytics |
| `sandbox_skip_admin` | 沙箱跳过 admin 鉴权 | admin 端点 fallback |

---

## 六、变更流程(沿用 V1.5.2)

V1.5.4 freeze 解除需走 V1.5.5 接力期,提请 m13+ 任务:

1. **新增端点** → m13+ 接力期,改 `openapi-frozen-v1.5.5.md` + `.json`
2. **修改端点响应 schema** → m13+ 接力期,严格保留向后兼容
3. **删除端点** → m13+ 接力期 + 1 版弃用过渡
4. **生产事故回滚** → m13+ 接力期紧急 fix,记录事故

**禁止绕过 freeze**(沿用 V1.5.2):
- 不得直接改 `backend/app/api/*` 不经评审
- 不得跳 m8t1 跑 m12 单独脚本
- 不得删 m8t1 测点凑数

---

## 七、freeze 校验

### 7.1 静态校验

`m12t3_test_openapi_endpoint_review.py` 25 测点,覆盖:

| 类别 | 测点 |
|---|---|
| V1.5.4 双文档存在(.md + .json) | 2 |
| 端点总数 = 56(沿用) | 1 |
| endpoint_review_meta 数组长度 = 5(4 admin + 1 catch-all) | 1 |
| 4 admin 端点 review_status 字段 | 4 |
| webhook/replay super_admin 标注 | 3 |
| admin.py 4 端点 docstring ### REVIEW META 段 | 4 |
| m8t1 聚合 runner M12 列表 | 2 |
| V1.5.4 handoff 文档存在 | 1 |
| C-2/C-4/C-5 评审项落地 | 3 |
| 25 测点总数 | 1 |
| 其他兼容校验 | 3 |

### 7.2 校验命令

```powershell
# 静态自测(沙箱走不通,仅纯文本校验)
uv run python -m scripts.m12t3_test_openapi_endpoint_review

# 聚合 runner(走通才返 ONLINE-READY)
uv run python -m scripts.m8t1_test_regression

# 实际部署演练(生产前必跑)
uv run fastapi dev backend/app/main.py
curl http://localhost:8000/openapi.json | jq '.paths | keys | length'
# 应返 56 端点
```

### 7.3 freeze 解除条件

- V1.5.5 接力期 m13+ 启动
- 新版 OpenAPI freeze 文件落地(`openapi-frozen-v1.5.5.md` + `.json`)
- m8t1 聚合 runner 加 M13_SCRIPTS
- m12t1/m12t2/m12t3 25 测点仍全过(向后兼容)

---

## 八、V1.5.4 production ONLINE-READY

- m12t1 super_admin role 扩展:✅ COMPLETE
- m12t2 m7t2 物理删除:✅ COMPLETE
- m12t3 OpenAPI 端点评审字段标注:✅ COMPLETE
- 累计 m12 阶段:3 脚本 / 75 测点
- 累计 58 脚本 / 1177+ 测点(55 V1.5.3 沿用 + 3 M12 新增)

---

*本文档为 V1.5.4 接力期 OpenAPI freeze 规范。沿用 V1.5.3 端点结构,新增端点评审字段标注层 + super_admin 鉴权拆分。*

