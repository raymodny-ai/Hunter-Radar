# V1.5.3 OpenAPI Freeze — V1.5.3 接力期 OpenAPI 冻结规范

> V1.5.3 接力期(m11t1 ~ m11t6)全部 COMPLETE。OpenAPI v1.5.3 freeze 已落地。
>
> 关联文档:
> - [V1.5.3-handoff.md](./V1.5.3-handoff.md) — V1.5.3 接力期收尾报告
> - [openapi-frozen-v1.5.3.json](./openapi-frozen-v1.5.3.json) — 机器可读 OpenAPI freeze
> - [openapi-frozen-v1.5.2.md](./openapi-frozen-v1.5.2.md) — V1.5.2 上一 freeze

---

## 一、概述

V1.5.3 接力期聚焦 V1.5.2 评审 7 项待优化项的代码层修复,**不引入新端点**,**不修改现有端点响应 schema**。

| 维度 | V1.5.2 状态 | V1.5.3 状态 |
|---|---|---|
| 端点总数 | 56 | 56(沿用,无变更) |
| fetch_source 规范 | 8 值 | 8 值(沿用) |
| admin 三态鉴权 | 3 态 | 3 态(沿用) |
| 待优化项 | 7 项 | 0 项(全部修复) |
| OpenAPI freeze | v1.5.2 | v1.5.3(代码层 freeze,端点沿用) |

---

## 二、M11 增量(代码层,非端点)

### 2.1 auth.py 内部变更

| 变更项 | 评审 | 详情 |
|---|---|---|
| `__all__` 补 4 admin 鉴权函数导出 | M10-UNPASSED-1 | `Role` / `require_admin_role` / `_check_api_key` / `_check_ip_whitelist` |
| `__all__` 补 4 角色 helper | m11t3 | `VALID_ROLES` / `DEFAULT_ROLE` / `is_valid_role` / `normalize_role` |
| `Role = str` type alias | M10-UNPASSED-3 | 向后兼容 m9t1 历史 `from app.core.auth import Role` |
| `TUser.role: str` | m11t3 | 默认 `"user"`,`is_admin` property 用 `normalize_role` |
| `_parse_jwt_user` 用 `normalize_role` | m11t3 | 不再硬编码 `role not in ("user", "admin")` |
| `require_admin_role` 加 `request: Request` | M10-UNPASSED-2 | JWT / API key 两路径合并 IP 校验 |
| `create_access_token(role: str = "user")` | m11t3 | 兼容扩展 |
| `from fastapi import Header, HTTPException, Request` | m11t2 | 加 `Request` |

### 2.2 admin.py 内部变更

| 变更项 | 评审 | 详情 |
|---|---|---|
| `_resolve_auth_mode` 简化 | M10-UNPASSED-2 副作用 | early return 模式,移除 IP 二次校验 |
| 移除 `_check_ip_whitelist` import | M10-UNPASSED-2 | 避免重复校验 |

### 2.3 脚本变更(非 API)

| 文件 | 变更项 | 评审 |
|---|---|---|
| `m7t2_sign_goldset.py` | runtime 拦截(`HR_ALLOW_LEGACY_SCRIPTS=1` 放行) | M10-UNPASSED-4 |
| `reviewer_cli.py` | `--dry-run` 全局 flag | M10-UNPASSED-5 |
| `reviewer_cli.py` | `TOKEN_HEX_LEN` env 解析(`REVIEWER_TOKEN_HEX_LEN`) | M10-UNPASSED-6 |
| `m10t7_p2_merge.py` | `--json-only` 全局 flag(CI 友好) | M10-UNPASSED-7 |

**说明**:脚本工具的 CLI flag 变更不影响 HTTP API,不触发 OpenAPI freeze 重写。

---

## 三、fetch_source 规范(沿用 V1.5.2)

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

## 四、变更流程(沿用 V1.5.2)

V1.5.3 freeze 解除需走 V1.5.4 接力期,提请 m12t1+ 任务:

1. **新增端点** → m12t1+ 接力期,改 `openapi-frozen-v1.5.4.md` + `.json`
2. **修改端点响应 schema** → m12t1+ 接力期,严格保留向后兼容
3. **删除端点** → m12t1+ 接力期 + 1 版弃用过渡
4. **生产事故回滚** → m12t1+ 接力期紧急 fix,记录事故

**禁止绕过 freeze**(沿用 V1.5.2):
- 不得直接改 `backend/app/api/*` 不经评审
- 不得跳 m8t1 跑 m11 单独脚本
- 不得删 m8t1 测点凑数

---

## 五、freeze 校验

### 5.1 静态校验

`m11t6_test_v153_finalize.py` 25 测点,覆盖:

| 类别 | 测点 |
|---|---|
| 7 项 V1.5.2 评审修复项 | 7 |
| auth.py `__all__` 长度 = 17 | 1 |
| `Role = str` type alias | 1 |
| `require_admin_role` 含 `request: Request` | 1 |
| `require_admin_role` IP 校验合并 | 1 |
| admin.py `_resolve_auth_mode` 简化 | 1 |
| m7t2 runtime 拦截 | 1 |
| reviewer_cli `--dry-run` flag | 1 |
| reviewer_cli `_resolve_token_hex_len` | 1 |
| m10t7_p2_merge `--json-only` flag | 1 |
| V1.5.3 handoff + OpenAPI 文档存在 | 2 |
| m8t1 聚合 runner M11 列表 | 2 |
| 25 测点总数 | 1 |
| 其他兼容校验 | 3 |

### 5.2 校验命令

```powershell
# 静态自测(沙箱走不通,仅纯文本校验)
uv run python -m scripts.m11t6_test_v153_finalize

# 聚合 runner(走通才返 ONLINE-READY)
uv run python -m scripts.m8t1_test_regression

# 实际部署演练(生产前必跑)
uv run fastapi dev backend/app/main.py
curl http://localhost:8000/openapi.json | jq '.paths | keys | length'
# 应返 56 端点
```

### 5.3 freeze 解除条件

- V1.5.4 接力期 m12t1+ 启动
- 新版 OpenAPI freeze 文件落地(`openapi-frozen-v1.5.4.md` + `.json`)
- m8t1 聚合 runner 加 M12_SCRIPTS
- m11t6 25 测点仍全过(向后兼容)

---

*本文档为 V1.5.3 接力期 OpenAPI freeze 规范。沿用 V1.5.2 端点结构,仅记录代码层 7 项评审修复。*
