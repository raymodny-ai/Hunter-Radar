# Admin Role 公开评审(V1.5.2 接力期 m10t4)

> 版本:v1.5.2-ONLINE-READY / 评审日期:2026-06-15 / 评审人:m10t4 接力期
> 关联:M9-t1 admin 鉴权补全 + V1.5.2 freeze 公开评审
> 适用:`/api/v1/admin/*` 4 端点(etl/run / backtest/run / backtest/result / webhook/replay)

---

## 0. 评审目的

把 M9-t1 落地的 `JWT role + ADMIN_API_KEY + IP 白名单` 三重防护**流程化**为可对外公开的:

1. **JWT claim 字段**——前端 / Ops 必读的 payload 字段定义
2. **admin role 权限矩阵**——role × 端点的可访问性
3. **三态鉴权(auth_mode)**——prod_admin_jwt / prod_admin_apikey / sandbox_skip_admin 显式标注
4. **运维 SOP**——配置、轮换、故障排查、事件溯源

V1.5 production 上线前必读,V1.5.2 freeze 时**不再变更**字段。

---

## 1. 公开 JWT Claim 字段

### 1.1 标准 claim

| 字段 | 类型 | 必须 | 说明 |
|---|---|---|---|
| `sub` | string(UUID) | ✅ | 用户 UUID;生产必须真实用户 UUID;沙箱 fallback 为 `00000000-0000-0000-0000-000000000000` |
| `tier` | `"free"` \| `"pro"` | ✅ | 配额 tier(BD-076);admin role 不影响 tier |
| `role` | `"user"` \| `"admin"` | ✅ | **V1.5 新增**(M9-t1);默认 `"user"`;admin 端点鉴权唯一依据 |
| `iat` | int(unix ts) | ✅ | 签发时间;`create_access_token` 写入 |
| `exp` | int(unix ts) | ✅ | 过期时间;走 `settings.jwt_expire_minutes`(默认 60min) |

### 1.2 role 字段约定(公开)

- **字面量**:`"user"`(默认)/ `"admin"`(M9-t1 新增)
- **类型定义**:`Role = Literal["user", "admin"]`(在 `app/core/auth.py:52`)
- **解析容错**:`_parse_jwt_user` 在 role 字段缺失或非法时降级为 `"user"`(auth.py:188-190)
- **不存 PII**:`role` 是无 PII 标识;admin 用户身份由 `sub` UUID 关联,非 role 字符串

### 1.3 公开 claim 样例

```json
{
  "sub": "5b1f7c3a-1e22-4d59-b7a3-9c8d2e0f1a6b",
  "tier": "pro",
  "role": "admin",
  "iat": 1749990000,
  "exp": 1749993600
}
```

---

## 2. Admin Role 权限矩阵

| 端点 | Method | 必须 role | API key 备选 | IP 白名单 | 鉴权态 |
|---|---|---|---|---|---|
| `/api/v1/admin/etl/run` | POST | `admin` | `X-Admin-API-Key` | 可选 | 三态显式 |
| `/api/v1/admin/backtest/run` | POST | `admin` | `X-Admin-API-Key` | 可选 | 三态显式 |
| `/api/v1/admin/backtest/result` | GET | `admin` | `X-Admin-API-Key` | 可选 | 三态显式 |
| `/api/v1/admin/webhook/replay` | POST | `admin` | `X-Admin-API-Key` | 可选 | 三态显式 |

### 2.1 必须 role 校验来源

- `Depends(require_admin_role)` 在 4 端点 handler 签名中显式声明
- `require_admin_role` 内部判定 `user.is_admin`(即 `user.role == "admin"`)
- 真实用户校验:`_resolve_auth_mode` 检查 `UUID(user.user_id) != SANDBOX_PLACEHOLDER_USER_ID` → 排除沙箱占位被认作 admin

### 2.2 IP 白名单(可选,生产强烈建议开启)

- 配置:`ADMIN_IP_WHITELIST="10.0.0.1,192.168.1.100,..."`(逗号分隔 IPv4/IPv6)
- 行为:
  - 空字符串 → 不限 IP
  - 不命中 → 403 + `client_ip_not_in_admin_whitelist`(`auth_mode` 标注)
  - `_check_ip_whitelist(client_host)` 内部实现
- **应用位置**:`_resolve_auth_mode(request, user, ...)`(admin.py:34-75),不放在 `require_admin_role` 内

> ⚠️ V1.5.2 评审发现:`require_admin_role` 内部**不**调 `_check_ip_whitelist`,而由 admin.py 的 `_resolve_auth_mode` 二次校验。**生产部署必须依赖 admin 路由的统一封装**,新加 admin 端点必须同时挂这两个 hook。

---

## 3. 三态鉴权(auth_mode)

`require_admin_role` 内部按以下顺序判定,最终在响应里 `auth_mode` 字段显式标注:

| 优先级 | 触发条件 | `auth_mode` | 解释 |
|---|---|---|---|
| 1 | `Authorization: Bearer <JWT>` 解析成功 + `role="admin"` | `prod_admin_jwt` | 生产 JWT admin 通过 |
| 2 | `X-Admin-API-Key` header 匹配 `settings.admin_api_key` | `prod_admin_apikey` | 生产 API key 通过(Ops 应急) |
| 3 | `settings.admin_role_enabled=False`(沙箱) | `sandbox_skip_admin` | 沙箱/CI 短路,**显式标注,不静默** |
| 4 | 全部未配 + `admin_role_enabled=True` | 抛 503 | 生产配置缺,**不 mock 200** |

### 3.1 响应字段规范

每个 admin 端点响应 JSON 必须含:

```json
{
  "...": "...",
  "auth_mode": "prod_admin_jwt | prod_admin_apikey | sandbox_skip_admin"
}
```

`auth_mode` 是审计 / 监控的关键字段,Ops 仪表盘必读。

---

## 4. 错误码汇总

| HTTP | 触发场景 | 响应 detail | `auth_mode` 标注 |
|---|---|---|---|
| 401 | `Authorization` 非 `Bearer` 头 + 无 `X-Admin-API-Key` | `unsupported auth scheme for admin` | `sandbox_skip_admin` |
| 401 | JWT 解析失败(sub 缺失/UUID 非法/过期) | `invalid bearer token` | (无,由 require_admin_role 透传) |
| 403 | JWT 有效但 `role != "admin"` | (由 _parse_jwt_user 返 401,后续由 require_admin_role 升级) | — |
| 403 | `X-Admin-API-Key` 不匹配 | (require_admin_role 落到 503 / sandbox) | — |
| 403 | IP 白名单不命中 | `client IP not in admin whitelist` + `client_host` | 当前 mode(api_key/jwt) |
| 503 | 生产配置缺(`admin_role_enabled=True` 但既无 role=admin 又无 API key) | `admin auth not configured` + `hint` | `sandbox_skip_admin`(占位) |

### 4.1 严禁行为

- ❌ **严禁 mock 200 伪装成功** —— 数据缺失返 200+空(本评审:admin 鉴权失败返错误码,不静默)
- ❌ **严禁暴露 `secret_key` / `admin_api_key` 到响应** —— `hmac.compare_digest` 防止 timing attack
- ❌ **严禁 admin 端点降级到 200** —— 生产配置缺必须 503 + 显式 hint

---

## 5. 运维 SOP(V1.5.2 冻结版)

### 5.1 生产配置必填

```bash
# 必填(任选其一即可,生产建议两全)
ADMIN_API_KEY="<32+ 字节随机>"   # Ops 应急通道
ADMIN_IP_WHITELIST="<Ops 出口 IP>"  # 强烈建议

# 角色开关(生产必须 True)
ADMIN_ROLE_ENABLED=true

# 配合
SECRET_KEY="<32+ 字节随机>"      # JWT HS256 签名
JWT_ALGORITHM=HS256              # 锁定,M5 末起不再改
JWT_EXPIRE_MINUTES=60            # 1 小时过期
```

`py scripts/env_check.py --v15` 校验 3 项 V1.5 admin 鉴权:
- V15-1: `ADMIN_API_KEY` 已设 或 `ADMIN_ROLE_ENABLED=false`(沙箱)
- V15-2: `ADMIN_IP_WHITELIST` 格式合法(逗号分隔 IP)
- V15-3: `ADMIN_API_KEY` 长度 ≥32

### 5.2 签发 admin JWT(Ops 临时操作)

```python
from uuid import UUID
from app.core.auth import create_access_token

# Ops 临时一次性 admin token
admin_jwt = create_access_token(
    user_id=UUID("00000000-0000-0000-0000-000000000000"),  # ⚠️ 必须替换为真实 Ops UUID
    tier="pro",
    role="admin",
    expire_seconds=900,  # 15 分钟
)
```

> ⚠️ Ops 临时 admin token 必须挂真实 `sub` UUID,不能是占位 `00000000-...`(会被 `_resolve_auth_mode` 排除)

### 5.3 故障排查清单

| 症状 | 可能原因 | 检查命令 |
|---|---|---|
| admin 端点 401 | JWT role 非 admin / 过期 | `py -c "from app.core.auth import decode_token; print(decode_token('<token>'))"` |
| admin 端点 403 | IP 白名单不命中 | `curl -v -H "X-Forwarded-For: <your_ip>" ...` 看 detail.client_host |
| admin 端点 503 | 生产配置缺(无 ADMIN_API_KEY 也无 role=admin) | `py scripts/env_check.py --v15` |
| sandbox 端点 200 | 正常(显式 sandbox_skip_admin) | 看响应 `auth_mode` 字段确认 |

### 5.4 审计日志

`/api/v1/admin/*` 4 端点响应必含 `auth_mode`,Ops 仪表盘应:

1. 监控 `auth_mode=sandbox_skip_admin` 出现在生产环境的次数(应为 0)
2. 监控 `auth_mode=prod_admin_apikey` 使用频率(应急通道,应低频)
3. 监控 503 错误率(配置缺)
4. 监控 403 IP 拒绝次数(可能为攻击)

---

## 6. V1.5.2 评审通过清单

V1.5.2 freeze 前必须 ✅:

- [x] 公开 JWT claim 字段已写入本文档(role / tier / sub / iat / exp)
- [x] admin role 权限矩阵已写入本文档(4 端点 × 3 鉴权方式)
- [x] 三态鉴权(auth_mode)显式标注 4 端点响应
- [x] 错误码汇总覆盖 401/403/503
- [x] 运维 SOP 5 步走(配置 / 签发 / 排错 / 审计 / check 脚本)
- [x] 严禁行为 3 条写入文档(防 mock 200 / 防密钥泄露 / 防静默降级)
- [x] `m10t4_test_admin_role_audit.py` 25 测点覆盖本文档所有字段
- [x] `m8t1_test_regression.py` M10_SCRIPTS 已加 m10t4(4 脚本 / 100 测点)
- [x] `m9t1_test_admin_auth.py` 25 测点已覆盖 require_admin_role 行为

V1.5.2 评审**未通过**项(需要后续 V1.5.3 修复):

- [ ] `app/core/auth.py` 的 `__all__` 列表**未**包含 `require_admin_role` / `Role` / `_check_api_key` / `_check_ip_whitelist` —— 公共 API 导出不完整(评审项 1)
- [ ] `require_admin_role` 内部**未**调 `_check_ip_whitelist`,IP 校验依赖 admin.py `_resolve_auth_mode` —— 拆双 hook 风险(评审项 2)
- [ ] `Role = Literal["user", "admin"]` 仅 2 种字面量,若需加 `"ops"` / `"auditor"` 需改 Literal 定义(评审项 3)

---

## 7. 评审依据文件

- [auth.py 完整代码](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/backend/app/core/auth.py) —— TUser / Role / require_admin_role 实现
- [config.py 完整代码](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/backend/app/core/config.py) —— admin_api_key / admin_ip_whitelist / admin_role_enabled 3 字段
- [admin.py 完整代码](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/backend/app/api/admin.py) —— 4 端点 + _resolve_auth_mode
- [env_check.py V15](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/scripts/env_check.py) —— V15-1/2/3 admin 鉴权校验
- [m9t1 自测](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/backend/scripts/m9t1_test_admin_auth.py) —— 25 测点
- [m10t4 自测](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/backend/scripts/m10t4_test_admin_role_audit.py) —— 25 测点(本文档字段覆盖)
- [V1.5-handoff §四 4.3](file://d:/Financial%20Project/Hunter%20Radar/hunter-radar/docs/V1.5-handoff.md) —— 候选 8 项列表

---

**评审结论**:V1.5.2 公开评审通过,admin role 防护流程化完成,3 项 V1.5.3 待优化项已记录。

评审人:m10t4 接力期 / 状态:V1.5.2-ONLINE-READY
