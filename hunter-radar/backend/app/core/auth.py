"""§6 用户鉴权核心(BD-075 JWT 落地)。

设计:
- 主路径:`Authorization: Bearer <JWT>`(HS256 签发,settings.secret_key)
- 向后兼容:无 JWT 时 `X-User-Id: <UUID>`(M4 接力期占位,M6 退场)
- 沙箱/未登录:无任何 header → 占位 UUID `00000000-0000-0000-0000-000000000000`

JWT payload:
{
  "sub": "<user UUID>",          # 标准 sub
  "tier": "free" | "pro",        # 配额(BD-076)
  "exp": <unix timestamp>,       # 过期(走 settings.jwt_expire_minutes)
  "iat": <unix timestamp>        # 签发时间
}

TUser:
- 解析后 dataclass(user_id: UUID, tier: Literal["free","pro"], exp: datetime)
- 失败抛 HTTPException 401(可观测 5xx 转 4xx)

硬约束:
- 不暴露 secret_key 到任何日志/响应
- 不擅自改 settings.jwt_algorithm(锁定 HS256,M5 末前)
- 沙箱无 jose 时:走手写 HS256 路径(hmac + hashlib + base64)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import Header, HTTPException, Request

from app.core.config import settings

# 优先用 jose,缺则降级到 hmac 手写 HS256(沙箱 / 轻量环境)
try:
    from jose import JWTError, jwt as _jose_jwt  # type: ignore[import-untyped]

    _HAS_JOSE = True
except ImportError:  # noqa: BLE001
    _HAS_JOSE = False

SANDBOX_PLACEHOLDER_USER_ID = UUID("00000000-0000-0000-0000-000000000000")
Tier = Literal["free", "pro"]
# V1.5.3 接力期 m11t3:Role 从 Literal 扩展为 str,避免上枚举不可扩展
# 保留枚举校验供内部使用。后续可扩 super_admin / viewer / operator 等。
# Role 保留为 type alias 向后兼容(m9t1 历史 import Role 仍可用)
Role = str
VALID_ROLES: tuple[str, ...] = ("user", "admin", "super_admin")
DEFAULT_ROLE: str = "user"
# V1.5.4 接力期 m12t1:super_admin 是 admin 的超集(具备 admin 全部能力 + 紧急操作
# 如 reset weights / wipe cache / replay sandbox webhook)。普通 admin 不允许的
# 操作走 require_super_admin_role,默认 admin 端点仍走 require_admin_role(双兼容)。
ADMIN_ROLES: tuple[str, ...] = ("admin", "super_admin")
SUPER_ADMIN_ROLE: str = "super_admin"


def is_valid_role(role: str | None) -> bool:
    """V1.5.3 接力期 m11t3:Role 校验 helper。

    返回 True 表示 role 是有效 role 字符串;None / 空串 / 未知 role 返回 False。
    不区分大小写,统一转为小写比较。
    """
    if not role or not isinstance(role, str):
        return False
    return role.lower() in {r.lower() for r in VALID_ROLES}


def normalize_role(role: str | None) -> str:
    """V1.5.3 接力期 m11t3:Role 规范化。

    输入合法 role → 返规范小写;非合法 → 返 DEFAULT_ROLE("user")。
    用在 _parse_jwt_user / get_current_user 默认值。
    """
    if not role or not isinstance(role, str):
        return DEFAULT_ROLE
    normalized = role.lower()
    if normalized in {r.lower() for r in VALID_ROLES}:
        return normalized
    return DEFAULT_ROLE


def is_admin_role(role: str | None) -> bool:
    """V1.5.4 接力期 m12t1:Role 是否具备 admin 能力(super_admin 也算)。

    用于 TUser.is_admin property 与 require_admin_role 判定。
    """
    return normalize_role(role) in {r.lower() for r in ADMIN_ROLES}


def is_super_admin_role(role: str | None) -> bool:
    """V1.5.4 接力期 m12t1:Role 是否为 super_admin(仅 super_admin 算)。

    用于 TUser.is_super_admin property 与 require_super_admin_role 判定。
    """
    return normalize_role(role) == SUPER_ADMIN_ROLE


# ---- 数据类 ---------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class TUser:
    """JWT 解析后的用户上下文。"""

    user_id: UUID
    tier: Tier
    exp: datetime
    role: str = "user"  # V1.5.3 接力期 m11t3:从 Literal 扩展为 str,默认 DEFAULT_ROLE("user")

    @property
    def is_authenticated(self) -> bool:
        return self.user_id != SANDBOX_PLACEHOLDER_USER_ID

    @property
    def is_pro(self) -> bool:
        return self.tier == "pro"

    @property
    def is_admin(self) -> bool:
        """V1.5.3 接力期 m11t3:admin role 判定(用 normalize_role 规范化)。

        V1.5.4 接力期 m12t1 变更:super_admin 也是 admin(is_admin_role helper 判定)。
        普通 admin 端点(etl/run / backtest/run)允许 super_admin 通过。
        """
        return is_admin_role(self.role)

    @property
    def is_super_admin(self) -> bool:
        """V1.5.4 接力期 m12t1:super_admin 判定(仅 super_admin 算)。

        用于 require_super_admin_role 依赖:webhook 重放 / weight reset / cache wipe
        等紧急 / 危险操作仅 super_admin 可触发。
        """
        return is_super_admin_role(self.role)


# ---- HS256 手写(沙箱 fallback) --------------------------------------------


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def _hs256_sign(secret: str, signing_input: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(sig)


def _manual_encode_jwt(payload: dict, secret: str, alg: str = "HS256") -> str:
    """手写 HS256 编码(无 jose 依赖)。"""
    if alg != "HS256":
        raise ValueError(f"only HS256 supported in fallback, got {alg}")
    header = {"typ": "JWT", "alg": alg}
    h = _b64url_encode(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    p = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signing_input = f"{h}.{p}"
    s = _hs256_sign(secret, signing_input)
    return f"{signing_input}.{s}"


def _manual_decode_jwt(token: str, secret: str, alg: str = "HS256") -> dict:
    """手写 HS256 解码 + 验签 + 过期校验。"""
    if alg != "HS256":
        raise ValueError(f"only HS256 supported in fallback, got {alg}")
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("malformed JWT")
    h_b64, p_b64, sig_b64 = parts
    signing_input = f"{h_b64}.{p_b64}"
    expected_sig = _hs256_sign(secret, signing_input)
    if not hmac.compare_digest(expected_sig, sig_b64):
        raise ValueError("signature mismatch")
    header = json.loads(_b64url_decode(h_b64).decode("utf-8"))
    if header.get("alg") != alg:
        raise ValueError(f"alg mismatch: {header.get('alg')} != {alg}")
    payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
    # exp 校验
    if "exp" in payload and int(payload["exp"]) < int(time.time()):
        raise ValueError("token expired")
    return payload


# ---- 公开 API -------------------------------------------------------------


def create_access_token(
    user_id: UUID | str,
    tier: Tier = "pro",
    *,
    expire_seconds: int | None = None,
    role: str = "user",  # V1.5.3 接力期 m11t3:从 Literal 扩展为 str
) -> str:
    """签发 JWT access token。"""
    if isinstance(user_id, UUID):
        user_id = str(user_id)
    expire = int(time.time()) + (expire_seconds or settings.jwt_expire_minutes * 60)
    payload: dict[str, Any] = {
        "sub": user_id,
        "tier": tier,
        "role": role,  # V1.5 接力期 m9t1 新增
        "iat": int(time.time()),
        "exp": expire,
    }
    if _HAS_JOSE:
        return _jose_jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return _manual_encode_jwt(payload, settings.secret_key, alg=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """解析 + 验签 + 过期校验;失败抛 ValueError。"""
    if _HAS_JOSE:
        try:
            return _jose_jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        except JWTError as e:  # noqa: BLE001
            raise ValueError(f"jose decode failed: {e}") from e
    return _manual_decode_jwt(token, settings.secret_key, alg=settings.jwt_algorithm)


def _parse_jwt_user(token: str) -> TUser:
    """解析 JWT → TUser;失败抛 401。"""
    try:
        payload = decode_token(token)
    except (ValueError, Exception) as e:  # noqa: BLE001
        raise HTTPException(
            status_code=401,
            detail={"message": "invalid bearer token", "error": str(e)},
        ) from e
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail={"message": "missing sub in token"})
    try:
        uid = UUID(str(sub))
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=401, detail={"message": "sub is not UUID"}) from e
    tier = payload.get("tier", "pro")
    if tier not in ("free", "pro"):
        tier = "pro"
    # V1.5.3 接力期 m11t3:role 字段用 normalize_role 规范化
    role = normalize_role(payload.get("role"))
    exp_raw = payload.get("exp")
    if exp_raw is None:
        exp = datetime.now(tz=timezone.utc).replace(microsecond=0)
    else:
        exp = datetime.fromtimestamp(int(exp_raw), tz=timezone.utc)
    return TUser(user_id=uid, tier=tier, exp=exp, role=role)  # type: ignore[arg-type]


def _parse_x_user_id_header(x_user_id: str | None) -> UUID | None:
    """解析 X-User-Id header → UUID;无则返 None;格式错抛 400。"""
    if not x_user_id:
        return None
    try:
        return UUID(x_user_id)
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=400, detail="invalid X-User-Id (must be UUID)"
        ) from e


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> TUser:
    """FastAPI 依赖:取当前用户。

    优先级:
    1. `Authorization: Bearer <JWT>` → 解析 TUser(无 jose 走手写 HS256)
    2. `X-User-Id: <UUID>` → 占位 TUser(tier=free,M6 退场)
    3. 都没有 → 沙箱占位 TUser(tier=free,SANDBOX_PLACEHOLDER_USER_ID)
    """
    # 1) JWT
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            return _parse_jwt_user(token.strip())
        if scheme:  # 非空但不是 bearer
            raise HTTPException(
                status_code=401,
                detail=f"unsupported auth scheme: {scheme!r}(only 'Bearer' supported)",
            )
    # 2) X-User-Id(向后兼容)
    uid = _parse_x_user_id_header(x_user_id)
    if uid is not None:
        return TUser(user_id=uid, tier="pro", exp=datetime.now(tz=timezone.utc), role="user")
    # 3) 沙箱占位
    return TUser(
        user_id=SANDBOX_PLACEHOLDER_USER_ID,
        tier="pro",
        exp=datetime.now(tz=timezone.utc),
        role="user",
    )


def get_current_user_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> UUID:
    """FastAPI 依赖:取当前 user_id(优先 JWT,backward-compat X-User-Id)。"""
    return get_current_user(authorization=authorization, x_user_id=x_user_id).user_id


def require_pro(
    user: TUser = __import__("fastapi").Depends(get_current_user),
) -> TUser:
    """FastAPI 依赖:要求 pro tier,否则 402(便于 M6 Stripe 升级引导)。"""
    if not user.is_pro:
        raise HTTPException(
            status_code=402,
            detail={
                "message": "pro tier required",
                "tier": user.tier,
                "upgrade_url": "/pricing",
            },
        )
    return user


# ---- Admin 鉴权 (V1.5 接力期 m9t1) ----------------------------------------

import os as _os  # 避免在 sandbox 环境下 _os 重名冲突

# 三态显式标注(m9t1):
# - "prod_admin_jwt"  : JWT role=admin 通过
# - "prod_admin_apikey": X-Admin-API-Key 通过(settings.admin_api_key 验证)
# - "sandbox_skip_admin": 未启用鉴权(admin_role_enabled=False)或全部未配


def _check_ip_whitelist(client_host: str | None) -> bool:
    """检查 client_host 是否在 settings.admin_ip_whitelist 中。

    - admin_ip_whitelist 为空 -> 不限
    - client_host 为 None -> False
    - 命中 -> True
    """
    whitelist = settings.admin_ip_whitelist.strip()
    if not whitelist:
        return True  # 空表示不限
    if not client_host:
        return False
    allowed = {ip.strip() for ip in whitelist.split(",") if ip.strip()}
    return client_host in allowed


def _check_api_key(provided: str | None) -> bool:
    """校验 X-Admin-API-Key 与 settings.admin_api_key。

    - admin_api_key 未设 -> False
    - provided 为 None/空 -> False
    - 不匹配 -> False
    - 匹配 -> True
    """
    expected = settings.admin_api_key
    if not expected:
        return False
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


def require_admin_role(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_admin_api_key: str | None = Header(default=None, alias="X-Admin-API-Key"),
) -> TUser:
    """FastAPI 依赖:要求 admin role 或 admin API key,否则 401/403。

    优先级(V1.5 接力期 m9t1):
    1. JWT role=admin → prod_admin_jwt
    2. X-Admin-API-Key 匹配 settings.admin_api_key → prod_admin_apikey
    3. admin_role_enabled=False 或全部未配 → sandbox_skip_admin(显式标注)

    V1.5.3 接力期 m11t2 变更:
    - 内部合并 IP 白名单校验(Request 注入取 client_host)
    - 消除 admin.py _resolve_auth_mode 二次调用 _check_ip_whitelist
    - JWT / API key 路径均校验 IP,白名单不命中 → 403 升级报错(不 mock 200)
    - 沙箱 fallback(admin_role_enabled=False)不校验 IP(便于 CI/sandbox)

    错误码:
    - 401: 鉴权方式错(非 Bearer 头 + 无 API key)
    - 403: 鉴权方式有效但 role 不 admin
    - 403: IP 白名单不命中
    - 403: API key 不匹配
    - 503: admin_role_enabled=True 但既无 role=admin 又无 API key(生产配置缺)
    """
    # 1) JWT role=admin 路径
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            try:
                user = _parse_jwt_user(token.strip())
            except HTTPException:
                # JWT 解析失败,继续尝试 API key
                user = None
            # V1.5.4 接力期 m12t1:is_admin 已自动兼容 super_admin(is_admin_role helper)
            if user and user.is_admin:
                # ---- m11t2:合并 IP 白名单校验 ----
                client_host = request.client.host if request.client else None
                if not _check_ip_whitelist(client_host):
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "message": "client IP not in admin whitelist",
                            "client_host": client_host,
                            "auth_mode": "prod_admin_jwt",
                        },
                    )
                return user
        elif scheme:  # 非空但不是 bearer
            raise HTTPException(
                status_code=401,
                detail={
                    "message": "unsupported auth scheme for admin",
                    "scheme": scheme,
                    "supported": ["Bearer", "X-Admin-API-Key"],
                    "auth_mode": "sandbox_skip_admin",
                },
            )
    # 2) X-Admin-API-Key 路径
    if _check_api_key(x_admin_api_key):
        # ---- m11t2:合并 IP 白名单校验 ----
        client_host = request.client.host if request.client else None
        if not _check_ip_whitelist(client_host):
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "client IP not in admin whitelist",
                    "client_host": client_host,
                    "auth_mode": "prod_admin_apikey",
                },
            )
        return TUser(
            user_id=SANDBOX_PLACEHOLDER_USER_ID,  # API key 用户不需 user_id
            tier="pro",
            exp=datetime.now(tz=timezone.utc),
            role="admin",
        )
    # 3) 沙箱 fallback:admin_role_enabled=False(不校验 IP,便于 CI/sandbox)
    if not settings.admin_role_enabled:
        return TUser(
            user_id=SANDBOX_PLACEHOLDER_USER_ID,
            tier="pro",
            exp=datetime.now(tz=timezone.utc),
            role="admin",  # 沙箱默认 admin,但 auth_mode 标注 sandbox_skip_admin
        )
    # 4) 生产配置缺(无 admin 路径):503(显式标注,不 mock 200)
    raise HTTPException(
        status_code=503,
        detail={
            "message": "admin auth not configured",
            "auth_mode": "sandbox_skip_admin",
            "hint": "set ADMIN_API_KEY env or enable JWT role=admin",
        },
    )


def require_super_admin_role(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_admin_api_key: str | None = Header(default=None, alias="X-Admin-API-Key"),
) -> TUser:
    """FastAPI 依赖:要求 super_admin role 或 admin API key,否则 401/403。

    V1.5.4 接力期 m12t1:为高危操作(webhook 重放 / weight reset / cache wipe)
    单独开设的更严鉴权。仅 super_admin 可通过,普通 admin 返 403。

    优先级(同 require_admin_role):
    1. JWT role=super_admin → prod_admin_jwt(自动过 IP 白名单)
    2. X-Admin-API-Key 匹配 settings.admin_api_key → prod_admin_apikey(自动视为 super_admin)
    3. admin_role_enabled=False → sandbox_skip_super_admin(显式标注)
    4. 生产配置缺 → 503

    错误码:
    - 401: 鉴权方式错(非 Bearer 头 + 无 API key)
    - 403: 鉴权方式有效但 role 不是 super_admin
    - 403: IP 白名单不命中
    - 503: admin_role_enabled=True 但既无 super_admin 又无 API key
    """
    # 1) JWT role=super_admin 路径
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            try:
                user = _parse_jwt_user(token.strip())
            except HTTPException:
                user = None
            if user and user.is_super_admin:
                # m12t1:super_admin 端点也走 IP 白名单(沿用 require_admin_role 逻辑)
                client_host = request.client.host if request.client else None
                if not _check_ip_whitelist(client_host):
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "message": "client IP not in super admin whitelist",
                            "client_host": client_host,
                            "auth_mode": "prod_admin_jwt",
                        },
                    )
                return user
        elif scheme:  # 非空但不是 bearer
            raise HTTPException(
                status_code=401,
                detail={
                    "message": "unsupported auth scheme for super admin",
                    "scheme": scheme,
                    "supported": ["Bearer", "X-Admin-API-Key"],
                    "auth_mode": "sandbox_skip_super_admin",
                },
            )
    # 2) X-Admin-API-Key 路径(API key 一律视为 super_admin,因 API key 需手工配置)
    if _check_api_key(x_admin_api_key):
        client_host = request.client.host if request.client else None
        if not _check_ip_whitelist(client_host):
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "client IP not in super admin whitelist",
                    "client_host": client_host,
                    "auth_mode": "prod_admin_apikey",
                },
            )
        return TUser(
            user_id=SANDBOX_PLACEHOLDER_USER_ID,
            tier="pro",
            exp=datetime.now(tz=timezone.utc),
            role=SUPER_ADMIN_ROLE,
        )
    # 3) 沙箱 fallback(不校验 IP,便于 CI/sandbox)
    if not settings.admin_role_enabled:
        return TUser(
            user_id=SANDBOX_PLACEHOLDER_USER_ID,
            tier="pro",
            exp=datetime.now(tz=timezone.utc),
            role=SUPER_ADMIN_ROLE,
        )
    # 4) 生产配置缺(无 super admin 路径):503
    raise HTTPException(
        status_code=503,
        detail={
            "message": "super admin auth not configured",
            "auth_mode": "sandbox_skip_super_admin",
            "hint": "set ADMIN_API_KEY env or enable JWT role=super_admin",
        },
    )


# ---- 沙箱检测 helper(供 main.py / config.py 用) ---------------------------


def is_sandbox_token(token: str) -> bool:
    """沙箱检测:JWT payload 的 sub 是否是占位 UUID。"""
    try:
        payload = decode_token(token)
    except Exception:  # noqa: BLE001
        return False
    return str(payload.get("sub", "")) == str(SANDBOX_PLACEHOLDER_USER_ID)


def now_utc_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# 显式声明 PyJWT 替代(M6 切换时 import 即可,函数签名一致)
__all__ = [
    "TUser",
    "Tier",
    "SANDBOX_PLACEHOLDER_USER_ID",
    "create_access_token",
    "decode_token",
    "get_current_user",
    "get_current_user_id",
    "require_pro",
    "is_sandbox_token",
    "now_utc_iso",
    # ---- V1.5.3 接力期 m11t1 补 admin 鉴权函数导出 ----
    "Role",  # V1.5.3 接力期 m11t3:从 Literal["user", "admin"] 扩展为 str(类型别名)
    "VALID_ROLES",  # 合法 role 列表(V1.5.3 接力期 m11t3 新增,V1.5.4 接力期 m12t1 加 super_admin)
    "DEFAULT_ROLE",  # 默认 role 字符串("user")(V1.5.3 接力期 m11t3 新增)
    "is_valid_role",  # role 校验 helper(V1.5.3 接力期 m11t3 新增)
    "normalize_role",  # role 规范化 helper(V1.5.3 接力期 m11t3 新增)
    # ---- V1.5.4 接力期 m12t1:super_admin 扩展 ----
    "ADMIN_ROLES",  # 具备 admin 能力的 role 集合("admin" + "super_admin")
    "SUPER_ADMIN_ROLE",  # 超级管理员 role 字符串("super_admin")
    "is_admin_role",  # admin 能力判定 helper(含 super_admin)
    "is_super_admin_role",  # super_admin 判定 helper(仅 super_admin)
    "require_admin_role",  # FastAPI Depends: admin 鉴权主入口
    "require_super_admin_role",  # FastAPI Depends: super admin 鉴权(高危操作)
    "_check_api_key",  # X-Admin-API-Key 校验 helper(从 _check_ip_whitelist 内部调用)
    "_check_ip_whitelist",  # IP 白名单校验 helper(admin.py 二次调用)
]

# 沙箱环境变量短路:HR_AUTH_DEV_SECRET 覆盖 settings.secret_key(便于 CI/dev 沙箱)
if os.environ.get("HR_AUTH_DEV_SECRET"):
    settings.secret_key = os.environ["HR_AUTH_DEV_SECRET"]  # type: ignore[misc]
